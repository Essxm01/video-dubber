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

# 1. TRANSCRIPTION + EMOTION ANALYSIS (Gemini Native Audio - V21 FINAL)
def smart_transcribe(audio_path: str):
    """
    V21 FINAL FIX: Uses Gemini (New SDK) to transcribe & translate to Professional Fusha.
    Strictly enforces Standard Arabic (No Slang).
    """
    print("🧠 Gemini Native: Uploading audio for Professional Fusha Analysis...")
    
    try:
        if not gemini_client:
            raise ValueError("Gemini Client not initialized.")

        # 1. Upload File (Using google-genai SDK)
        # Note: The new SDK manages uploads via client.files
        file_upload = gemini_client.files.upload(file=audio_path)
        print(f"📤 Uploaded file: {file_upload.name}")
        
        # Wait for processing
        while file_upload.state.name == "PROCESSING":
            time.sleep(1)
            file_upload = gemini_client.files.get(name=file_upload.name)
            print("⏳ Processing audio...")

        if file_upload.state.name == "FAILED":
            raise ValueError("Gemini failed to process audio file.")
        
        print("✅ Audio uploaded successfully!")

        # 2. The Prompt (Strictly Fusha / Documentary Style)
        prompt = """
        You are an expert Documentary Dubbing Director.
        Listen to this audio file carefully.
        
        Task:
        1. Transcribe the speech accurately.
        2. Translate it to **Modern Standard Arabic (Fusha/MSA)**.
        3. **Style**: Use professional, flowing, and narrative Arabic (like National Geographic documentaries). 
        4. **CRITICAL**: Detect the EMOTION (Happy, Sad, Excited, Neutral) for each segment.
        
        Format:
        [
            {"start": 0.0, "end": 2.5, "text": "النص بالعربية الفصحى السليمة هنا", "emotion": "Neutral"},
            ...
        ]
        
        Rules:
        - **STRICTLY FORBIDDEN**: Do NOT use Egyptian Slang or any local dialect.
        - **Avoid Robotic Phrasing**: Do not translate word-for-word. Use proper Arabic conjunctions (و، ف، حيث، بينما) to ensure flow.
        - Merge short, choppy sentences into meaningful, complete phrases.
        - Return ONLY the JSON.
        """

        # --- DYNAMIC MODEL DISCOVERY (The "Anti-404" Strategy) ---
        target_model = None
        
        # 1. Try to list models dynamically to find a valid 'flash' model
        try:
            print("🔍 Discovering available Gemini models...")
            # Paging through list_models to find a match
            valid_models = []
            for m in gemini_client.models.list(config={'page_size': 100}):
                # Check for supported methods if attribute exists, else assume valid
                methods = getattr(m, 'supported_generation_methods', [])
                if not methods or 'generateContent' in methods:
                    valid_models.append(m.name)
            
            # Prioritize models: 1.5-flash -> 1.5-pro -> 2.0-flash
            for candidate in ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash", "gemini-1.0-pro"]:
                matches = [vm for vm in valid_models if candidate in vm]
                if matches:
                    matches.sort(reverse=True) 
                    target_model = matches[0] 
                    target_model = target_model.replace("models/", "")
                    print(f"🎯 Dynamic Discovery: Selected model '{target_model}'")
                    break
                    
        except Exception as e_discover:
            print(f"⚠️ Model discovery failed: {e_discover}")

        # 2. Fallback Hardcoded List if Discovery Failed
        if not target_model:
            print("⚠️ Dynamic discovery failed, using fallback list.")
            target_model = 'gemini-1.5-flash' 

        print(f"🧠 Generating content using model: {target_model}...")
        
        # Pass file_upload directly (SDK handles the rest)
        response = gemini_client.models.generate_content(
            model=target_model,
            contents=[prompt, file_upload],
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        
        # Cleanup uploaded file
        try:
            gemini_client.files.delete(name=file_upload.name)
        except: pass
        
        # Parse response
        if response.text:
            segments = json.loads(response.text)
            print(f"✅ Gemini Analyzed {len(segments)} segments (Professional Fusha + Emotion)!")
            return segments
        else:
             print("⚠️ Gemini response empty.")
             return []

    except Exception as e:
        print(f"⚠️ Gemini Native Audio Failed: {e}")
        print("🔄 Falling back to Groq Whisper...")
        
        # --- FALLBACK: Groq Whisper ---
        try:
            client = Groq(api_key=GROQ_API_KEY)
            with open(audio_path, "rb") as f:
                transcription = client.audio.transcriptions.create(
                    file=(os.path.basename(audio_path), f.read()),
                    model="whisper-large-v3",
                    response_format="verbose_json"
                )
            segments = []
            if hasattr(transcription, 'segments'):
                for seg in transcription.segments:
                    segments.append({
                        "start": seg["start"], 
                        "end": seg["end"], 
                        "text": seg["text"].strip(),
                        "emotion": "neutral"  # Default emotion for Groq fallback
                    })
            print(f"✅ Groq Fallback: Transcribed {len(segments)} segments")
            return segments
        except Exception as e2:
            print(f"❌ Groq Fallback also failed: {e2}")
from google import genai
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

def generate_audio_azure(text: str, path: str):
    try:
        # Get keys from environment
        azure_key = os.getenv("AZURE_SPEECH_KEY")
        azure_region = os.getenv("AZURE_SPEECH_REGION")

        if not azure_key or not azure_region:
            print("⚠️ Azure keys missing in environment variables!")
            return False

        print(f"☁️ Azure TTS: Synthesizing -> {text[:20]}...")

        # Configure Azure
        speech_config = speechsdk.SpeechConfig(subscription=azure_key, region=azure_region)
        # Set Voice to Egyptian/Arabic Neural (Professional)
        speech_config.speech_synthesis_voice_name = "ar-EG-ShakirNeural" 

        # Output config
        audio_config = speechsdk.audio.AudioOutputConfig(filename=path)

        # Synthesizer
        synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)

        # Synthesize
        # Azure handles text cleaning better, but stripping brackets is safer
        clean_text = text.replace("[", "").replace("]", "")
        result = synthesizer.speak_text_async(clean_text).get()

        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            print("✅ Azure TTS Success!")
            return True
        elif result.reason == speechsdk.ResultReason.Canceled:
            cancellation_details = result.cancellation_details
            print(f"❌ Azure Canceled: {cancellation_details.reason}")
            return False

    except Exception as e:
        print(f"❌ Azure Error: {e}")
        return False

# 3. HYBRID PIPELINE: Gemini (SSML Generation) + Azure (TTS)
def generate_audio_gemini(text: str, path: str, emotion: str = "neutral") -> bool:
    """Generate human-like audio using Gemini SSML + Azure TTS with emotion awareness."""
    if not text.strip(): return False

    print(f"🚀 SSML Pipeline: Processing -> {text[:25]}... [Emotion: {emotion}]")

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
                model='gemini-1.5-flash',
                contents=f"""
                Role: Expert SSML Audio Engineer (Arabic).
                Task: Convert the input text into a high-quality SSML script for Azure TTS.
                
                Emotional Context: The speaker's emotion is "{emotion}".
                Emotional Pacing Hint: {emotion_instruction}
                
                Strict Guidelines:
                1. **Format:** Output VALID XML/SSML strictly. Start with <speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="ar-EG"> and end with </speak>.
                2. **Voice:** Include <voice name="ar-EG-ShakirNeural"> inside the speak tag.
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

# Helper to split audio
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
        
        # Merge if: Gap is small AND combined text isn't too long
        if time_gap < gap_threshold and (len(current_group["text"]) + len(next_seg["text"])) < max_chars:
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

            # Process Dubbing for this Chunk
            chunk_master_audio = AudioSegment.silent(duration=0)
            
            for i, segment in enumerate(segments):
                # Translate
                translated = translate_text(segment["text"], target_lang)
                
                # Get emotion from Gemini analysis (V21 feature)
                emotion = segment.get("emotion", "neutral")
                
                # TTS with emotion-aware SSML
                temp_file = os.path.join(AUDIO_FOLDER, f"temp_{base}_{idx}_{i}.mp3")
                generate_audio_gemini(translated, temp_file, emotion=emotion)
                
                # Sync
                start_time_ms = int(segment['start'] * 1000)
                # end_time_ms = int(segment['end'] * 1000)
                
                if os.path.exists(temp_file) and os.path.getsize(temp_file) > 100:
                    segment_audio = AudioSegment.from_file(temp_file)
                else:
                    segment_audio = AudioSegment.silent(duration=500) # Fallback duration

                # Handle Gaps
                current_duration = len(chunk_master_audio)
                gap = start_time_ms - current_duration
                if gap > 0: chunk_master_audio += AudioSegment.silent(duration=gap)
                
                chunk_master_audio += segment_audio
                
                # GC
                try: os.remove(temp_file)
                except: pass

            # Export Processed Chunk
            processed_chunk_path = f"{chunk_path}_dubbed.mp3"
            chunk_master_audio.export(processed_chunk_path, format="mp3")
            final_audio_parts.append(processed_chunk_path)
            
            # Free RAM
            del chunk_master_audio
            del segments
            try: os.remove(chunk_path) # Remove original chunk
            except: pass

        # MERGE ALL PARTS
        db_update(task_id, "MERGING", 90, "دمج الأجزاء النهائية...")
        
        concat_list_file = f"list_{base}.txt"
        with open(concat_list_file, "w") as f:
            for part in final_audio_parts:
                f.write(f"file '{os.path.abspath(part)}'\n")
        
        merged_audio_path = os.path.join(AUDIO_FOLDER, f"final_audio_{base}.mp3")
        subprocess.run(["ffmpeg", "-f", "concat", "-safe", "0", "-i", concat_list_file, "-c", "copy", "-y", merged_audio_path], check=True)
        
        # Merge with Video
        output_path = os.path.join(OUTPUT_FOLDER, f"dubbed_{base}.mp4")
        subprocess.run([
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", merged_audio_path,
            "-c:v", "copy",
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-shortest",
            output_path
        ], check=True)
        
        db_update(task_id, "UPLOADING", 95, "رفع النتيجة...")
        url = upload_to_storage(output_path, "videos", f"dubbed/final_{base}.mp4", "video/mp4")
        
        db_update(task_id, "COMPLETED", 100, "تم بنجاح! 🎉", result={"dubbed_video_url": url, "title": filename})
        
        # Cleanup
        try:
            os.remove(video_path)
            os.remove(full_audio_path)
            os.remove(merged_audio_path)
            os.remove(concat_list_file)
            for p in final_audio_parts: os.remove(p)
        except: pass

    except Exception as e:
        print(f"❌ Task Error: {e}")
        db_update(task_id, "FAILED", 0, f"خطأ: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=10000)