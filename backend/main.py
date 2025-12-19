"""
Arab Dubbing API - Version 19.0 (Google Cloud TTS / Gemini)
- TTS: Google Cloud TTS (Neural/Wavenet) → Edge TTS (Fallback)
- STT: Groq Whisper
- Translation: Google Translate (fast & reliable)
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import os
import uuid
import subprocess
import requests
from datetime import datetime
from dotenv import load_dotenv
from groq import Groq
from deep_translator import GoogleTranslator
from pydub import AudioSegment
import math
import azure.cognitiveservices.speech as speechsdk

# Load environment variables
load_dotenv()

# Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")  # Uses Google Cloud TTS API Key
AZURE_SPEECH_KEY = os.getenv("AZURE_SPEECH_KEY", "")
AZURE_SPEECH_REGION = os.getenv("AZURE_SPEECH_REGION", "westeurope")

app = FastAPI(title="Arab Dubbing API", version="19.0.0")

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
    return {"status": "active", "version": "19.0.0", "engine": "Groq + Google Cloud TTS (Gemini)"}

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

def db_update(task_id: str, status: str, progress: int, message: str, result: dict = None):
    data = {"status": status, "progress": progress, "message": message, "updated_at": datetime.now().isoformat()}
    if result: data["result"] = result
    
    # Always update local storage (reliable)
    if task_id not in LOCAL_TASKS:
        LOCAL_TASKS[task_id] = {}
    LOCAL_TASKS[task_id].update(data)
    print(f"📊 {status} {progress}%: {message}")
    
    # Also try Supabase
    try:
        sb = get_fresh_supabase()
        if sb:
            sb.table("projects").update(data).eq("id", task_id).execute()
    except: pass

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

# 1. TRANSCRIPTION (Groq Whisper)
def smart_transcribe(audio_path: str):
    print("🎙️ Using Groq Whisper...")
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
                segments.append({"start": seg["start"], "end": seg["end"], "text": seg["text"].strip()})
        print(f"✅ Transcribed {len(segments)} segments")
        return segments
    except Exception as e:
        print(f"❌ Groq Failed: {e}")
        return []

from google import genai
from google.genai import types

# Initialize Gemini Client
client = None
client = None
# Initialize Gemini Client
client = None
if GEMINI_API_KEY:
    try:
        # Standard Client Init (v1/v1beta automatic) compatible with Text Generation
        client = genai.Client(api_key=GEMINI_API_KEY)
        print("🔍 Gemini SDK (google-genai) Initialized.")
    except Exception as e:
        print(f"⚠️ Failed to init Gemini SDK: {e}")

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
            if not client: break
            
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
            response = client.models.generate_content(
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

# 3. HYBRID PIPELINE: Gemini (Text Opt) + Azure (TTS)
def generate_audio_gemini(text: str, path: str) -> bool:
    if not text.strip(): return False

    print(f"🚀 Hybrid Pipeline: Processing segment -> {text[:20]}...")

    # --- STEP 1: Gemini (The Director) - Optimize Text ---
    # We ask Gemini to ensure the text is perfect Fusha and ready for TTS
    optimized_text = text
    try:
        if client:
            response = client.models.generate_content(
                model='gemini-2.0-flash', # Use the fast, smart text model
                contents=f"""
                Role: Expert Arabic Linguist & Tashkeel Specialist.
                Task: Prepare the following text for a Text-to-Speech engine.
                
                Strict Rules:
                1. **Language:** Convert to high-quality Modern Standard Arabic (Fusha).
                2. **Diacritics (CRITICAL):** Add FULL Tashkeel (Vowel Marks) to EVERY letter. Do not leave any word without vowels.
                   - Ensure correct grammar (I'rab) for accurate pronunciation.
                3. **Simplification:** If a word is archaic or hard to pronounce, replace it with a clearer synonym.
                4. **Clean:** Remove all acting cues (e.g., [laugh], [sigh]). Output ONLY the vocalized Arabic text.
                
                Input: "{text}"
                """,
                config={'response_mime_type': 'text/plain'} # Explicitly ask for TEXT
            )
            if response.text:
                optimized_text = response.text.strip()
                print(f"💎 Gemini Refined Text: {optimized_text[:30]}...")
        else:
             print("⚠️ Gemini Client missing, skipping optimization.")
        
    except Exception as e:
        print(f"⚠️ Gemini Text Optimization Failed: {e}")
        optimized_text = text # Fallback to original text

    # --- STEP 2: Azure (The Voice) - Generate Audio ---
    try:
        azure_key = os.getenv("AZURE_SPEECH_KEY")
        azure_region = os.getenv("AZURE_SPEECH_REGION")
        
        if not azure_key or not azure_region:
            print("❌ Azure Keys Missing!")
            return False

        speech_config = speechsdk.SpeechConfig(subscription=azure_key, region=azure_region)
        # "ar-EG-ShakirNeural" is the industry standard for Fusha/Documentary
        speech_config.speech_synthesis_voice_name = "ar-EG-ShakirNeural" 
        
        audio_config = speechsdk.audio.AudioOutputConfig(filename=path)
        synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)

        # Synthesize the Gemini-Optimized Text
        result = synthesizer.speak_text_async(optimized_text).get()

        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            print("✅ Azure Audio Generated (Powered by Gemini Text)!")
            return True
        else:
            details = result.cancellation_details
            print(f"❌ Azure Failed: {details.reason} | {details.error_details}")
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
            
            # Smart Transcribe the Chunk
            segments = smart_transcribe(chunk_path)
            
            if not segments:
                # If no speech, just use the original audio chunk (or silence)
                final_audio_parts.append(chunk_path) 
                continue

            # Process Dubbing for this Chunk
            chunk_master_audio = AudioSegment.silent(duration=0)
            
            for i, segment in enumerate(segments):
                # Translate
                translated = translate_text(segment["text"], target_lang)
                
                # TTS
                temp_file = os.path.join(AUDIO_FOLDER, f"temp_{base}_{idx}_{i}.mp3")
                generate_audio_gemini(translated, temp_file)
                
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
                os.remove(temp_file)
            except: pass
            
        # Final Padding to match video duration
        video_duration_ms = int(original_video_duration * 1000)
        current_total = len(master_audio)

        if current_total < video_duration_ms:
            master_audio += AudioSegment.silent(duration=video_duration_ms - current_total)

        # Export Final Audio
        merged_audio_path = os.path.join(AUDIO_FOLDER, f"merged_dubbed_{base}.mp3")
        master_audio.export(merged_audio_path, format="mp3")
        print("✅ Smart Audio Timeline created with Synchronization.")
            
        db_update(task_id, "MERGING", 90, "دمج الفيديو...")
        output_path = os.path.join(OUTPUT_FOLDER, f"dubbed_{base}.mp4")
        
        # Merge using FFmpeg (Simple audio replace since we have a full track now)
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
        
        if not url:
            # If upload fails, try to fallback to local URL (for inspection) but warn
            print("⚠️ Upload failed, falling back to local URL")
            url = f"/output/{os.path.basename(output_path)}"
            if not os.path.exists(output_path):
                 raise Exception("فشل رفع الملف إلى السحابة (Supabase Storage Failed)")

        db_update(task_id, "COMPLETED", 100, "تم بنجاح! 🎉", result={"dubbed_video_url": url, "title": filename})
        
        # Cleanup (ONLY if upload successful to keep local debug file)
        if url.startswith("http"):
             try:
                os.remove(video_path)
                os.remove(audio_path)
                os.remove(merged_audio_path)
                # os.remove(output_path) # Keep output for now just in case
             except: pass
            
    except Exception as e:
        print(f"🔥 FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        db_update(task_id, "FAILED", 0, f"خطأ: {str(e)[:100]}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=10000)