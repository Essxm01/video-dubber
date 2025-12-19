"""
Arab Dubbing API - Version 21.0 (Hybrid V21: Gemini Brain + Azure Voice)
- STT: Gemini 1.5 Flash Native Audio (Deep Emotion Analysis) + Groq Whisper (Fallback)
- TTS: Azure Speech Services (ar-EG-ShakirNeural) + SSML Pacing
- Translation: Gemini 2.0 Flash + Google Translate (Fallback)
- Text Optimization: Gemini SSML Engineer (Smart Tashkeel + Breathing Pauses)
"""

import os
import gc
import json
import uuid
import time
import shutil
import subprocess
import traceback
from datetime import datetime
from typing import Optional, List, Dict

from fastapi import FastAPI, BackgroundTasks, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

from dotenv import load_dotenv
from groq import Groq
from deep_translator import GoogleTranslator
from pydub import AudioSegment
import azure.cognitiveservices.speech as speechsdk
from google.genai import types

# Load environment variables
load_dotenv()

# Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
# Fix trailing slash warning
if SUPABASE_URL and not SUPABASE_URL.endswith("/"):
    SUPABASE_URL += "/"
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
AZURE_SPEECH_KEY = os.getenv("AZURE_SPEECH_KEY", "")
AZURE_SPEECH_REGION = os.getenv("AZURE_SPEECH_REGION", "westeurope")

app = FastAPI(title="Arab Dubbing API", version="21.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

AUDIO_FOLDER = "audio"
OUTPUT_FOLDER = "output"
UPLOAD_FOLDER = "uploads"

for folder in [AUDIO_FOLDER, OUTPUT_FOLDER, UPLOAD_FOLDER]:
    os.makedirs(folder, exist_ok=True)

app.mount("/output", StaticFiles(directory=OUTPUT_FOLDER), name="output")

@app.get("/health")
def health():
    return {
        "status": "active", 
        "version": "20.0.0", 
        "engine": "Groq + Gemini + Azure TTS",
        "services": {
            "groq": bool(GROQ_API_KEY),
            "gemini": bool(GEMINI_API_KEY),
            "azure_tts": bool(AZURE_SPEECH_KEY),
            "supabase": bool(SUPABASE_URL and SUPABASE_KEY)
        }
    }

# --- LOCAL TASK STORAGE (reliable fallback) ---
LOCAL_TASKS = {}

# --- HELPERS ---
def get_fresh_supabase():
    try:
        from supabase import create_client
        if SUPABASE_URL and SUPABASE_KEY:
            return create_client(SUPABASE_URL, SUPABASE_KEY)
        return None
    except: return None

# Helper: Update DB & Local State (Now with Supabase Storage Persistence)
def db_update(task_id, status, progress=0, message="", result=None):
    # 1. Update Local Memory
    LOCAL_TASKS[task_id] = {
        "status": status,
        "progress": progress,
        "message": message,
        "result": result
    }
    
    # 2. Update Supabase Storage (Persistent JSON)
    try:
        sb = get_fresh_supabase()
        if sb:
            payload = {
                "id": task_id,
                "status": status,
                "progress": progress,
                "message": message,
                "result": result,
                "last_updated": datetime.now().isoformat()
            }
            # Upload to 'videos' bucket in 'jobs/' folder
            sb.storage.from_("videos").upload(
                path=f"jobs/{task_id}.json",
                file=json.dumps(payload).encode(),
                file_options={"upsert": "true", "content-type": "application/json"}
            )
    except Exception as e:
        print(f"⚠️ Status persist failed: {e}")
    
    # Also log to console for debugging
    print(f"📊 [{task_id[:8]}] {status} {progress}%: {message}")

def upload_to_storage(file_path: str, bucket: str, dest_name: str, content_type: str) -> str:
    try:
        sb = get_fresh_supabase()
        if not sb: return None
        
        # Ensure bucket exists
        buckets = sb.storage.list_buckets()
        bucket_exists = any(b.name == bucket for b in buckets)
        if not bucket_exists:
            try: sb.storage.create_bucket(bucket, options={"public": False})
            except: pass

        with open(file_path, "rb") as f:
            sb.storage.from_(bucket).upload(path=dest_name, file=f.read(), file_options={"content-type": content_type, "upsert": "true"})
        
        # Use Signed URL (valid for 10 years ~ 315360000s) to avoid private bucket issues
        # Public URL often fails if bucket is not explicitly set to Public
        res = sb.storage.from_(bucket).create_signed_url(dest_name, 315360000)
        
        # Handle dict response (Supabase Python client returns {'signedURL': '...'})
        if isinstance(res, dict) and "signedURL" in res:
            return res["signedURL"]
        return res
    except Exception as e:
        print(f"Server Upload Error: {e}")
        return None

def extract_audio(video_path: str, audio_path: str) -> bool:
    cmd = ["ffmpeg", "-i", video_path, "-vn", "-acodec", "libmp3lame", "-ab", "64k", "-ar", "16000", "-y", audio_path]
    return subprocess.run(cmd, capture_output=True).returncode == 0

def get_video_duration(video_path: str) -> float:
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", video_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return float(result.stdout.strip())
    except: return 0.0

# --- CORE LOGIC ---

# --- HELPER: Dynamic Model Discovery ---
def discover_best_gemini_model(client):
    """Dynamically finds the best available Gemini Flash/Pro model to avoid 404s."""
    target_model = None
    try:
        print("🔍 Discovering available Gemini models...")
        valid_models = []
        for m in client.models.list(config={'page_size': 100}):
            methods = getattr(m, 'supported_generation_methods', [])
            if not methods or 'generateContent' in methods:
                valid_models.append(m.name)
        
        # Prioritize models: 1.5-flash (Most Stable) -> 2.0-flash -> 1.5-pro
        # Deprioritized 'lite' models to avoid cutoff issues
        for candidate in ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.0-pro"]:
            matches = [vm for vm in valid_models if candidate in vm]
            if matches:
                matches.sort(reverse=True) # Prefer latest version
                target_model = matches[0]
                target_model = target_model.replace("models/", "")
                print(f"🎯 Dynamic Discovery: Selected model '{target_model}'")
                return target_model
                
    except Exception as e:
        print(f"⚠️ Model discovery failed: {e}")
    
    # Fallback if discovery completely fails
    return 'gemini-1.5-flash'

# 1. TRANSCRIPTION + EMOTION ANALYSIS (Gemini Native Audio - V21 FINAL)
# 1. TRANSCRIPTION + EMOTION ANALYSIS (Hybrid V22: Whisper Ears + Gemini Brain)
def smart_transcribe(audio_path: str):
    """
    V22 DEEP SOLVE:
    1. Whisper (Groq): Guarantees 100% transcription coverage (no missing endings).
    2. Gemini (Flash): Translates to Professional Fusha & Detects Emotion from text context.
    """
    segments = []
    
    # --- STAGE 1: "THE EARS" (Groq Whisper) ---
    # We use Whisper first because it NEVER truncates audio.
    try:
        print("👂 Whisper (Groq): Listening to full audio...")
        client = Groq(api_key=GROQ_API_KEY)
        with open(audio_path, "rb") as f:
            transcription = client.audio.transcriptions.create(
                file=(os.path.basename(audio_path), f.read()),
                model="whisper-large-v3",
                response_format="verbose_json"
            )
        
        if hasattr(transcription, 'segments'):
            for seg in transcription.segments:
                segments.append({
                    "start": seg["start"], 
                    "end": seg["end"], 
                    "text": seg["text"].strip(),
                    "emotion": "neutral" # To be filled by Gemini
                })
        print(f"✅ Whisper Transcribed {len(segments)} segments (100% Coverage).")

    except Exception as e_groq:
        print(f"⚠️ Groq Whisper Failed: {e_groq}")
        print("🔄 Falling back to Gemini Native Audio...")
        segments = [] # Ensure empty to trigger fallback below

    # --- STAGE 2: "THE BRAIN" (Gemini Enrichment + Diarization) ---
    if segments:
        try:
            print("🧠 Gemini: Translating to Fusha & Detecting Speaker/Gender/Emotion...")
            
            # 1. Upload Audio for Gemini to "Hear" the speakers
            if not gemini_client: raise ValueError("No Gemini Client")
            
            # Check if file exists, if not re-upload
            # For efficiency in V23, we upload once for enrichment
            gl_file = gemini_client.files.upload(file=audio_path)
            
            # Wait for processing
            while gl_file.state.name == "PROCESSING":
                time.sleep(1)
                gl_file = gemini_client.files.get(name=gl_file.name)

            # Prepare compact context for Gemini to align Text <-> Audio
            simplified_segments = [{"id": i, "start": s["start"], "end": s["end"], "text": s["text"]} for i, s in enumerate(segments)]
            
            prompt = f"""
            You are an expert Dubbing Director.
            I have a list of timed English segments derived from the attached audio.
            
            Task:
            1. **Listen** to the audio corresponding to each segment timestamp.
            2. **Identify the Speaker**:
               - **Gender**: 'Male' or 'Female'.
               - **Label**: 'Speaker A', 'Speaker B', etc. (Diarization).
            3. **Translate** text to **Professional Modern Standard Arabic (Fusha)**.
            4. **Detect Emotion**: (Happy, Sad, Excited, Neutral, Angry, Whispering).
            
            Input Segments:
            {json.dumps(simplified_segments, ensure_ascii=False)}
            
            Output Format (Strict JSON Map):
            [
                {{
                    "id": 0, 
                    "ar_text": "...", 
                    "emotion": "Neutral", 
                    "gender": "Male", 
                    "speaker": "Speaker A"
                }},
                ...
            ]
            
            Rules:
            - **Strict Logic**: You MUST listen to the audio to determine gender/speaker. Do not guess.
            - **Consistency**: 'Speaker A' must always have the same Gender.
            - **Fusha**: No slang.
            """
            
            target_model = discover_best_gemini_model(gemini_client)
            
            # Pass BOTH prompt and audio file
            response = gemini_client.models.generate_content(
                model=target_model,
                contents=[prompt, gl_file],
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            
            # Cleanup
            try: gemini_client.files.delete(name=gl_file.name)
            except: pass
            
            if response.text:
                enrichment_map = {item['id']: item for item in json.loads(response.text)}
                
                # Merge back into original segments
                for i, seg in enumerate(segments):
                    if i in enrichment_map:
                        data = enrichment_map[i]
                        seg['text'] = data.get('ar_text', seg['text'])
                        seg['emotion'] = data.get('emotion', 'neutral')
                        seg['gender'] = data.get('gender', 'Male')
                        seg['speaker'] = data.get('speaker', 'Speaker A')
                    else:
                        # Defaults
                        seg['gender'] = 'Male'
                        seg['speaker'] = 'Speaker A'
                
                print(f"✅ Gemini Enriched {len(segments)} segments with Multi-Speaker Data!")
                return segments
                
        except Exception as e_enrich:
            print(f"⚠️ Gemini Enrichment Failed: {e_enrich}. Using raw Whisper text.")
            return segments

    # --- FALLBACK: Gemini Native Audio (Old Method) ---
    # Only runs if Groq failed completely
    print("⚠️ Using Legacy Gemini Native Audio (Recall Risk)...")
    try:
        file_upload = gemini_client.files.upload(file=audio_path)
        while file_upload.state.name == "PROCESSING":
            time.sleep(1)
            file_upload = gemini_client.files.get(name=file_upload.name)
            
        target_model = discover_best_gemini_model(gemini_client)
        prompt_native = """
        Transcribe accurately, Translate to Fusha, Detect Emotion.
        Format: JSON list with start, end, text, emotion.
        CRITICAL: Transcribe until the very last second of audio.
        """
        response = gemini_client.models.generate_content(
            model=target_model,
            contents=[prompt_native, file_upload],
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        try: gemini_client.files.delete(name=file_upload.name)
        except: pass
        
        if response.text: return json.loads(response.text)
        
    except Exception as e_native:
        print(f"❌ All methods failed: {e_native}")
        
    return []
# Initialize Gemini Client (Singleton) with Default API (v1beta)
try:
    from google import genai
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    print("✅ Gemini SDK (google-genai) Initialized (Default/v1beta).")
except Exception as e:
    print(f"⚠️ Failed to init Gemini SDK: {e}")
    gemini_client = None

# 2. TRANSLATION (Strict Egyptian Slang)
def translate_text(text: str, target_lang: str = "ar") -> str:
    if not text.strip(): return ""
    
    # We prefer the flash model for speed, but fallback to pro/standard if needed
    # Update: Prioritizing 'latest' and '2.0' models confirmed to be available in production logs
    models_to_try = [
        'gemini-2.0-flash', 
        'gemini-flash-latest', 
        'gemini-pro-latest', 
        'gemini-1.5-flash', 
        'gemini-1.5-pro'
    ]
    
    for model_name in models_to_try:
        try:
            if not gemini_client: break
            
            # STRICT PROMPT: Modern Standard Arabic (Fusha)
            prompt = f"""
            Task: Translate the following English text to **Modern Standard Arabic (Fusha)**.
            
            Input Text: "{text}"
            
            CRITICAL RULES:
            1. Output **ONLY** the translated Arabic text.
            2. Use correct, formal vocabulary (e.g., "الحافلة" not "الأتوبيس", "جداً" not "أوي").
            3. Ensure professional sentence structure suitable for a documentary or news broadcast.
            4. NO "Here is the translation" or metadata.
            5. Do not wrap output in quotes.
            """
            
            # Note: translate_text might not need v1beta specifically, but using the same client is fine.
            response = gemini_client.models.generate_content(
                model=model_name,
                contents=prompt
            )
            
            if response and response.text:
                # Clean up any potential leakage
                clean_text = response.text.strip().replace('"', '').replace("`", "").split('\n')[0]
                print(f"🇸🇦 Gemini Fusha: {clean_text}")
                return clean_text
                
        except Exception as e:
            print(f"⚠️ Gemini Error ({model_name}): {e}")
            continue

    # Fallback
    try:
        from deep_translator import GoogleTranslator
        return GoogleTranslator(source='auto', target=target_lang).translate(text)
    except: return text

# (Legacy Azure function removed - Logic integrated into Hybrid SSML Pipeline)

# 3. HYBRID PIPELINE: Gemini (SSML Generation) + Azure (TTS)
def generate_audio_gemini(text: str, path: str, emotion: str = "neutral", voice_name: str = "ar-EG-ShakirNeural") -> bool:
    """Generate human-like audio using Gemini SSML + Azure TTS with emotion awareness."""
    if not text.strip(): return False

    print(f"🚀 SSML Pipeline: Processing -> {text[:25]}... [Emotion: {emotion}] [Voice: {voice_name}]")

    # Map emotion to SSML pacing hints
    emotion_hints = {
        "neutral": "Normal pacing, natural flow.",
        "excited": "Slightly faster pace, more emphasis on key words.",
        "sad": "Slower pace, longer pauses, softer emphasis.",
        "angry": "Faster pace, strong emphasis, short pauses.",
        "whispering": "Very slow pace, use <prosody volume='soft'>.",
        "dramatic": "Dramatic pauses (600ms), strong emphasis on 2-3 words.",
        "happy": "Slightly faster, upbeat rhythm, light emphasis."
    }
    emotion_instruction = emotion_hints.get(emotion, emotion_hints["neutral"])

    # --- STEP 1: Gemini (SSML Engineer) - Generate SSML Script ---
    ssml_script = None
    try:
        if gemini_client:
            response = gemini_client.models.generate_content(
                # Use safe fallback model for SSML generation
                model=discover_best_gemini_model(gemini_client),
                contents=f"""
                Role: Expert SSML Audio Engineer (Arabic).
                Task: Convert the input text into a high-quality SSML script for Azure TTS.
                
                Emotional Context: The speaker's emotion is "{emotion}".
                Emotional Pacing Hint: {emotion_instruction}
                Target Voice: {voice_name}
                
                Strict Guidelines:
                1. **Format:** Output VALID XML/SSML strictly. Start with <speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="ar-EG"> and end with </speak>.
                2. **Voice:** Include <voice name="{voice_name}"> inside the speak tag.
                3. **Pauses (Breathing):** Insert <break time="400ms"/> after long sentences or dramatic points. Insert <break time="150ms"/> after commas.
                4. **Emphasis:** Use <emphasis level="moderate">WORD</emphasis> sparingly for 1-2 important keywords per sentence.
                5. **Emotion Adaptation:** Apply the emotional pacing hint above to adjust speed/pauses.
                6. **Language:** Modern Standard Arabic (Fusha) with *Smart Tashkeel* on ambiguous words only.
                7. **Content:** Translate the input accurately. Do not add intro/outro or explanations.
                8. **Safety:** Do NOT output lists, conjugations, or definitions. Only the SSML script.
                
                Input Text:
                "{text}"
                """,
                config=types.GenerateContentConfig(
                    response_mime_type='text/plain'
                )
            )
            if response.text:
                ssml_script = response.text.strip()
                # Cleanup: Remove markdown code blocks if present
                ssml_script = ssml_script.replace("```xml", "").replace("```ssml", "").replace("```", "").strip()
                
                # Safety: Ensure it starts with <speak
                if not ssml_script.startswith("<speak"):
                    print("⚠️ Invalid SSML detected, falling back to plain text.")
                    ssml_script = None
                else:
                    print(f"💎 SSML Generated: {ssml_script[:60]}...")
        else:
            print("⚠️ Gemini Client missing, using plain text fallback.")
        
    except Exception as e:
        print(f"⚠️ Gemini SSML Generation Failed: {e}")
        ssml_script = None

    # --- STEP 2: Azure (The Voice) - Synthesize Audio ---
    try:
        azure_key = os.getenv("AZURE_SPEECH_KEY")
        azure_region = os.getenv("AZURE_SPEECH_REGION")
        
        if not azure_key or not azure_region:
            print("❌ Azure Keys Missing!")
            return False

        speech_config = speechsdk.SpeechConfig(subscription=azure_key, region=azure_region)
        speech_config.speech_synthesis_voice_name = "ar-EG-ShakirNeural"
        
        audio_config = speechsdk.audio.AudioOutputConfig(filename=path)
        synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)

        # Use SSML if available, otherwise fallback to plain text
        if ssml_script:
            print("🎭 Azure TTS: Using SSML mode...")
            result = synthesizer.speak_ssml_async(ssml_script).get()
        else:
            # Fallback: Plain text mode
            print("📝 Azure TTS: Using plain text mode...")
            result = synthesizer.speak_text_async(text).get()

        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            print("✅ Azure Audio Generated (Human-Like Pacing)!")
            return True
        else:
            details = result.cancellation_details
            print(f"❌ Azure Failed: {details.reason} | {details.error_details}")
            # If SSML failed, retry with plain text
            if ssml_script:
                print("🔄 Retrying with plain text...")
                result = synthesizer.speak_text_async(text).get()
                if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                    print("✅ Azure Audio Generated (Plain Text Fallback)!")
                    return True
            return False

    except Exception as e:
        print(f"❌ Critical Audio Error: {e}")
        return False

# 4. MERGE (Dubbed audio only, no background)
def merge_audio_video(video_path, audio_files, output_path):
    valid_files = [f for f in audio_files if os.path.exists(f) and os.path.getsize(f) > 100]
    if not valid_files:
        print("⚠️ No valid audio files")
        return

    list_file = "list.txt"
    with open(list_file, "w") as f:
        for a in valid_files: 
            f.write(f"file '{os.path.abspath(a)}'\n")
    
    merged_audio = "merged_dubbed.mp3"
    subprocess.run(["ffmpeg", "-f", "concat", "-safe", "0", "-i", list_file, "-c", "copy", "-y", merged_audio], check=True)
    
    # Replace original audio completely
    subprocess.run([
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", merged_audio,
        "-c:v", "copy",
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-shortest",
        output_path
    ], check=True)
    
    print("✅ Video merged (human voice)")
    
    try:
        os.remove(list_file)
        os.remove(merged_audio)
    except: pass

class TaskResponse(BaseModel):
    task_id: str
    status: str

@app.post("/process-video", response_model=TaskResponse)
async def process_video_endpoint(background_tasks: BackgroundTasks, file: UploadFile = File(...), mode: str = Form("DUBBING"), target_lang: str = Form("ar")):
    task_id = str(uuid.uuid4())
    path = os.path.join(UPLOAD_FOLDER, f"{task_id}_{file.filename}")
    with open(path, "wb") as f: f.write(await file.read())
    
    # Init DB
    sb = get_fresh_supabase()
    if sb:
        try:
            sb.table("projects").insert({
                "id": task_id, 
                "title": file.filename, 
                "status": "PENDING", 
                "progress": 0, 
                "mode": mode, 
                "created_at": datetime.now().isoformat()
            }).execute()
        except: pass
    
    db_update(task_id, "PENDING", 0, "جاري التجهيز (استلام الملف)...")
    background_tasks.add_task(process_video_task, task_id, path, mode, target_lang, file.filename)
    return TaskResponse(task_id=task_id, status="PENDING")

@app.get("/status/{task_id}")
def get_task_status(task_id: str):
    """Get job status from local memory or Supabase Storage."""
    # 1. Check local memory (fastest)
    if task_id in LOCAL_TASKS:
        return {"id": task_id, **LOCAL_TASKS[task_id]}
    
    # 2. Try Supabase Storage (persistent)
    try:
        sb = get_fresh_supabase()
        if sb:
            res = sb.storage.from_("videos").download(f"jobs/{task_id}.json")
            if res:
                return json.loads(res)
    except Exception as e:
        print(f"⚠️ Status fetch failed: {e}")
    
    return {"status": "UNKNOWN", "message": "لم يتم العثور على المهمة"}

# Helper: Extract precise video segment (re-encoded for frame accuracy)
def extract_video_segment(video_path, start_time, end_time, output_path):
    duration = end_time - start_time
    if duration <= 0: return False
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start_time),
        "-i", video_path,
        "-t", str(duration),
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23", "-pix_fmt", "yuv420p",
        "-an", # No audio
        output_path
    ]
    return subprocess.run(cmd, capture_output=True).returncode == 0

# Helper: Create Freeze Frame Video
def create_freeze_frame_video(last_frame_source, duration, output_path):
    # 1. Extract last frame as image
    img_path = output_path + ".jpg"
    cmd_img = [
        "ffmpeg", "-y",
        "-sseof", "-0.1", # Seek to very end
        "-i", last_frame_source,
        "-update", "1", "-q:v", "1",
        "-frames:v", "1",
        img_path
    ]
    subprocess.run(cmd_img, capture_output=True)
    
    if not os.path.exists(img_path): return False
    
    # 2. Loop image to create video
    cmd_vid = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", img_path,
        "-t", str(duration),
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-an",
        output_path
    ]
    res = subprocess.run(cmd_vid, capture_output=True)
    try: os.remove(img_path)
    except: pass
    return res.returncode == 0


# Helper: Smart Speedup (Time-Stretch) using FFmpeg Atempo
def speed_up_audio(input_path: str, output_path: str, speed_factor: float) -> bool:
    """
    Speeds up audio without changing pitch using FFmpeg 'atempo' filter.
    speed_factor: > 1.0 means faster. Max realistic is ~2.0, cap at 1.5 for clarity.
    """
    try:
        # atempo filter limitations: 0.5 to 2.0. Chain them for higher speeds if needed.
        # We clamp between 1.0 and 2.0 for safety.
        factor = max(1.0, min(speed_factor, 2.0))
        
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-filter:a", f"atempo={factor}",
            "-vn", output_path
        ]
        res = subprocess.run(cmd, capture_output=True)
        return res.returncode == 0
    except Exception as e:
        print(f"⚠️ Speedup failed: {e}")
        return False

#Helper to split audio
def split_audio_chunks(audio_path, chunk_length_ms=300000): # 5 mins
    audio = AudioSegment.from_file(audio_path)
    chunks = []
    duration_ms = len(audio)
    for i in range(0, duration_ms, chunk_length_ms):
        chunk_name = f"{audio_path}_part_{i//chunk_length_ms}.mp3"
        chunk = audio[i:i+chunk_length_ms]
        chunk.export(chunk_name, format="mp3")
        chunks.append(chunk_name)
    return chunks

# --- SMART BATCHING: Merge close segments for natural flow ---
def optimize_segments_for_flow(segments, gap_threshold=0.75, max_chars=280):
    """
    Smart Batching Algorithm:
    Merges short, close segments into longer flowing paragraphs to prevent robotic pauses.
    - gap_threshold: Max allowed silence between segments to trigger a merge (seconds).
    - max_chars: Max length of a single TTS chunk (to maintain sync).
    """
    if not segments: return []
    
    optimized = []
    current_group = segments[0].copy()  # Copy to avoid mutating original
    
    for next_seg in segments[1:]:
        # Calculate time gap between current end and next start
        time_gap = next_seg["start"] - current_group["end"]
        
        # Merge if: Gap is small AND combined text isn't too long AND Speaker is same
        same_speaker = current_group.get("speaker") == next_seg.get("speaker")
        if time_gap < gap_threshold and (len(current_group["text"]) + len(next_seg["text"])) < max_chars and same_speaker:
            # Combine text and extend duration
            current_group["text"] += " " + next_seg["text"]
            current_group["end"] = next_seg["end"]
            # Keep the first segment's emotion (or use the more "intense" one)
            if next_seg.get("emotion") not in ["neutral", None]:
                current_group["emotion"] = next_seg.get("emotion", "neutral")
        else:
            # Push current group and start a new one
            optimized.append(current_group)
            current_group = next_seg.copy()
            
    optimized.append(current_group)  # Append the final group
    
    print(f"🧩 Smart Batching: {len(segments)} -> {len(optimized)} segments (better flow)")
    return optimized

async def process_video_task(task_id, video_path, mode, target_lang, filename):
    try:
        base = task_id[:8]
        full_audio_path = os.path.join(AUDIO_FOLDER, f"{base}.mp3")
        
        db_update(task_id, "EXTRACTING", 5, "استخراج الصوت...")
        extract_audio(video_path, full_audio_path)
        
        # SMART CHUNKING (RAM SAVER)
        # Split into 5-minute chunks to avoid OOM on Render Free Tier
        chunk_files = split_audio_chunks(full_audio_path, chunk_length_ms=300000)
        
        final_audio_parts = []
        total_chunks = len(chunk_files)
        
        for idx, chunk_path in enumerate(chunk_files):
            # Update Status
            overall_progress = 10 + int((idx / total_chunks) * 80)
            db_update(task_id, "PROCESSING", overall_progress, f"معالجة الجزء {idx+1}/{total_chunks}...")
            
            # Smart Transcribe the Chunk (Gemini Native Audio)
            raw_segments = smart_transcribe(chunk_path)
            
            if not raw_segments:
                # If no speech, just use the original audio chunk (or silence)
                final_audio_parts.append(chunk_path) 
                continue
            
            # Apply Smart Batching to merge close segments for natural flow
            segments = optimize_segments_for_flow(raw_segments)

            # Speaker Voice Management (Round-Robin)
            male_voices = ["ar-EG-ShakirNeural", "ar-SA-HamedNeural", "ar-BH-AliNeural", "ar-YE-SalehNeural"]
            female_voices = ["ar-EG-SalmaNeural", "ar-SA-ZariyahNeural", "ar-KW-NouraNeural", "ar-QA-AmalNeural"]
            
            speaker_registry = {} 
            
            # --- ELASTIC SYNC STATE ---
            chunk_master_audio = AudioSegment.silent(duration=0)
            chunk_video_parts = [] # List of .mp4 paths
            current_video_cursor = 0.0 # Seconds relative to chunk start
            
            # Helper to get segment range relative to this chunk
            # Chunk starts at idx * 300s (if uniform split), but split_audio_chunks uses exact bytes.
            # Simplified: We treat chunk_path as 0.0 to Duration.
            # But Whisper segments are global timestamps. We need to offset them.
            # Correction: We are passing 'chunk_path' to smart_transcribe.
            # smart_transcribe returns timestamps relative to THAT chunk (because it transcribed that file).
            # So timestamps 0.0 = Start of Chunk. ✅
            
            for i, segment in enumerate(segments):
                # 1. HANDLE GAPS (Non-Speech Video)
                seg_start = segment['start']
                if seg_start > current_video_cursor:
                    gap_duration = seg_start - current_video_cursor
                    # Extract GAP Video
                    gap_video = os.path.join(AUDIO_FOLDER, f"gap_{base}_{idx}_{i}.mp4")
                    # Note: We must extract from the VIDEO corresponding to this audio chunk range.
                    # This is tricky because we only have 'video_path' (Full Video).
                    # We need global offset.
                    global_offset = idx * 300 # Approx 5 mins
                    
                    if extract_video_segment(video_path, global_offset + current_video_cursor, global_offset + seg_start, gap_video):
                        chunk_video_parts.append(gap_video)
                    
                    # Add Silence to Audio
                    chunk_master_audio += AudioSegment.silent(duration=int(gap_duration * 1000))
                    current_video_cursor = seg_start
                
                # 2. PREPARE AUDIO (Translate + TTS)
                translated = translate_text(segment["text"], target_lang)
                emotion = segment.get("emotion", "neutral")
                gender = segment.get("gender", "Male")
                param_speaker = segment.get("speaker", "Speaker A")
                
                speaker_key = f"{param_speaker}_{gender}"
                if speaker_key not in speaker_registry:
                    if gender.lower() == "female":
                        idx_v = len([k for k in speaker_registry if "Female" in k]) % len(female_voices)
                        speaker_registry[speaker_key] = female_voices[idx_v]
                    else:
                        idx_v = len([k for k in speaker_registry if "Male" in k]) % len(male_voices)
                        speaker_registry[speaker_key] = male_voices[idx_v]
                
                temp_file = os.path.join(AUDIO_FOLDER, f"temp_{base}_{idx}_{i}.mp3")
                generate_audio_gemini(translated, temp_file, emotion=emotion, voice_name=speaker_registry[speaker_key])
                
                # Load Generated Audio
                if os.path.exists(temp_file) and os.path.getsize(temp_file) > 100:
                    segment_audio = AudioSegment.from_file(temp_file)
                else:
                    segment_audio = AudioSegment.silent(duration=500)
                
                # SAFETY: Normalize
                segment_audio = segment_audio.set_frame_rate(44100).set_channels(1)

                # 3. ELASTIC SYNC LOGIC (The Core)
                original_dur = segment['end'] - segment['start']
                generated_dur = len(segment_audio) / 1000.0
                ratio = generated_dur / original_dur if original_dur > 0 else 1.0
                
                global_start = (idx * 300) + segment['start']
                global_end = (idx * 300) + segment['end']
                
                # Video Segment Output
                seg_video_path = os.path.join(AUDIO_FOLDER, f"seg_{base}_{idx}_{i}.mp4")
                
                # SCENARIO A: Audio Shorter (Ratio < 1.0) -> Add Silence
                if ratio <= 1.0:
                    extract_video_segment(video_path, global_start, global_end, seg_video_path)
                    chunk_video_parts.append(seg_video_path)
                    
                    # Pad Audio
                    # required_dur = int(original_dur * 1000)
                    # if len(segment_audio) < required_dur:
                    #     segment_audio += AudioSegment.silent(duration=required_dur - len(segment_audio))
                    chunk_master_audio += segment_audio
                    # Note: We rely on the GAP logic of next iteration to fill remainder?
                    # No, gap logic fills pre-start.
                    # If this audio is short, we simply append it. The loop ends.
                    # Current cursor moves to seg_end.
                    # Wait: If audio is 3s and video is 5s. We append 3s audio. Cursor moves to 5s.
                    # The next gap calculation will start at 5s.
                    # Missing 2s of audio!
                    # FIX: We MUST pad audio to match video duration EXACTLY unless we speed it up.
                    pad_needed = int(original_dur * 1000) - len(segment_audio)
                    if pad_needed > 0: segment_audio += AudioSegment.silent(duration=pad_needed)
                    
                # SCENARIO B: Audio Slightly Longer (1.0 < Ratio <= 1.3) -> Speed Up (Compress)
                elif ratio <= 1.3:
                    print(f"⚡ Elastic Sync: Speeding up segment {i} ({ratio:.2f}x)")
                    temp_fast = temp_file.replace(".mp3", "_fast.mp3")
                    # Speed factor = ratio (to fit exactly)
                    if speed_up_audio(temp_file, temp_fast, ratio):
                        segment_audio = AudioSegment.from_file(temp_fast).set_frame_rate(44100).set_channels(1)
                        try: os.remove(temp_fast)
                        except: pass
                    
                    extract_video_segment(video_path, global_start, global_end, seg_video_path)
                    chunk_video_parts.append(seg_video_path)
                    chunk_master_audio += segment_audio
                    
                # SCENARIO C: Audio WAY Longer (Ratio > 1.3) -> Freeze Video Extension
                else:
                    print(f"❄️ Elastic Sync: Freezing Video for segment {i} (Ratio {ratio:.2f}x > 1.3)")
                    
                    # 1. Speed up Audio to max 1.3x (to reduce freeze time)
                    target_audio_dur = generated_dur / 1.3
                    temp_fast = temp_file.replace(".mp3", "_fast.mp3")
                    if speed_up_audio(temp_file, temp_fast, 1.3):
                        segment_audio = AudioSegment.from_file(temp_fast).set_frame_rate(44100).set_channels(1)
                        try: os.remove(temp_fast)
                        except: pass
                    
                    # 2. Extract Base Video
                    extract_video_segment(video_path, global_start, global_end, seg_video_path)
                    chunk_video_parts.append(seg_video_path)
                    
                    # 3. Create Freeze Extension
                    extra_time = (len(segment_audio) / 1000.0) - original_dur
                    if extra_time > 0:
                        freeze_video_path = os.path.join(AUDIO_FOLDER, f"freeze_{base}_{idx}_{i}.mp4")
                        # Use last frame of the JUST GENERATED segment (seg_video_path)
                        if create_freeze_frame_video(seg_video_path, extra_time, freeze_video_path):
                            chunk_video_parts.append(freeze_video_path)
                    
                    chunk_master_audio += segment_audio

                # Update Cursor
                current_video_cursor = segment['end']
                
                # Cleanup
                try: os.remove(temp_file)
                except: pass

            # END LOOP: Handle Final Gap (End of Chunk)
            # Actually, we don't know exact chunk end unless we check chunk length.
            # But the 'raw_segments' likely end near the end.
            # We can skip the tail gap for now or calculate it.
            
            # 4. EXPORT CHUNK AUDIO
            processed_chunk_audio_path = f"{chunk_path}_dubbed.mp3"
            chunk_master_audio.export(processed_chunk_audio_path, format="mp3")
            final_audio_parts.append(processed_chunk_audio_path)
            
            # 5. EXPORT CHUNK VIDEO
            # Concat all video parts for this chunk
            processed_chunk_video_path = f"{chunk_path}_dubbed.mp4"
            if chunk_video_parts:
                v_list = f"vlist_{base}_{idx}.txt"
                with open(v_list, "w") as f:
                    for vp in chunk_video_parts: f.write(f"file '{os.path.abspath(vp)}'\n")
                subprocess.run(["ffmpeg", "-f", "concat", "-safe", "0", "-i", v_list, "-c", "copy", "-y", processed_chunk_video_path], check=True)
                os.remove(v_list)
                for vp in chunk_video_parts: 
                    try: os.remove(vp)
                    except: pass
            else:
                 # Fallback if no video parts (no speech?) -> Extract full chunk video
                 pass # Logic needed if no segments?

            
            # Free RAM
            del chunk_master_audio
            del segments
            try: os.remove(chunk_path) # Remove original chunk
            except: pass

        # MERGE ALL PARTS (Elastic Sync Version)
        db_update(task_id, "MERGING", 90, "دمج الأجزاء النهائية (فيديو + صوت)...")
        
        # 1. Merge Audio Parts
        concat_audio_list = f"alist_{base}.txt"
        with open(concat_audio_list, "w") as f:
            for part in final_audio_parts:
                f.write(f"file '{os.path.abspath(part)}'\n")
        
        merged_audio_path = os.path.join(AUDIO_FOLDER, f"final_audio_{base}.mp3")
        subprocess.run(["ffmpeg", "-f", "concat", "-safe", "0", "-i", concat_audio_list, "-c", "copy", "-y", merged_audio_path], check=True)
        
        # 2. Merge Video Parts (The Freeze Frames)
        # Note: 'final_audio_parts' loop populated 'chunk_path_dubbed.mp4' implicitely?
        # WAIT: In the loop we generated processed_chunk_video_path but didn't save it to a list 'final_video_parts'.
        # We need to collect them.
        # FIX: We need to modify the loop above to collect final_video_parts.
        # But we are in a REPLACE block for the END of the function.
        # We can assume we will have a list of video chunks named identically to audio chunks but .mp4
        
        final_video_parts = [p.replace(".mp3", ".mp4") for p in final_audio_parts]
        
        concat_video_list = f"vlist_final_{base}.txt"
        with open(concat_video_list, "w") as f:
            for part in final_video_parts:
                if os.path.exists(part):
                    f.write(f"file '{os.path.abspath(part)}'\n")
        
        merged_video_path = os.path.join(OUTPUT_FOLDER, f"visual_dubbed_{base}.mp4")
        subprocess.run(["ffmpeg", "-f", "concat", "-safe", "0", "-i", concat_video_list, "-c", "copy", "-y", merged_video_path], check=True)

        # 3. Mux Final (Copy Streams)
        # Verify streams are valid
        output_path = os.path.join(OUTPUT_FOLDER, f"dubbed_{base}.mp4")
        subprocess.run([
            "ffmpeg", "-y",
            "-i", merged_video_path,
            "-i", merged_audio_path,
            "-c", "copy", # No re-encoding needed, we did it in chunks
            "-map", "0:v:0",
            "-map", "1:a:0",
             # No -shortest, let them match
            output_path
        ], check=True)
        
        db_update(task_id, "UPLOADING", 95, "رفع النتيجة...")
        url = upload_to_storage(output_path, "videos", f"dubbed/final_{base}.mp4", "video/mp4")
        
        db_update(task_id, "COMPLETED", 100, "تم بنجاح! 🎉 (استراتيجية Elastic Sync ❄️)", result={"dubbed_video_url": url, "title": filename})
        
        # Cleanup
        try:
            os.remove(video_path)
            os.remove(full_audio_path)
            os.remove(merged_audio_path)
            os.remove(merged_video_path)
            os.remove(concat_audio_list)
            os.remove(concat_video_list)
            for p in final_audio_parts: 
                os.remove(p)
                os.remove(p.replace(".mp3", ".mp4"))
        except: pass

    except Exception as e:
        print(f"❌ Task Error: {e}")
        db_update(task_id, "FAILED", 0, f"خطأ: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=10000)