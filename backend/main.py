"""
Arab Dubbing API - Production Version v7.0 (The Fix)
- FIXED: Translation using deep-translator (Google Translate)
- FIXED: Gemini TTS re-enabled
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, Literal
import os
import asyncio
import uuid
import gc
import subprocess
import time
from datetime import datetime
from dotenv import load_dotenv
from deep_translator import GoogleTranslator  # <--- New Hero Library

load_dotenv()

# Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

app = FastAPI(title="Arab Dubbing API", version="7.0.0")

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

def get_fresh_supabase():
    try:
        from supabase import create_client
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        print(f"⚠️ Supabase init error: {e}")
        return None

def get_groq():
    try:
        from groq import Groq
        return Groq(api_key=GROQ_API_KEY)
    except Exception as e:
        print(f"⚠️ Groq: {e}")
        return None

# ============= DB Operations =============
class Status:
    PENDING = "PENDING"
    EXTRACTING = "EXTRACTING"
    TRANSCRIBING = "TRANSCRIBING"
    TRANSLATING = "TRANSLATING"
    GENERATING_SRT = "GENERATING_SRT"
    GENERATING_AUDIO = "GENERATING_AUDIO"
    MERGING = "MERGING"
    UPLOADING = "UPLOADING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

def db_create(task_id: str, filename: str, mode: str):
    for attempt in range(3):
        try:
            sb = get_fresh_supabase()
            if sb:
                sb.table("projects").insert({
                    "id": task_id,
                    "title": filename,
                    "status": Status.PENDING,
                    "progress": 0,
                    "mode": mode,
                    "created_at": datetime.now().isoformat(),
                }).execute()
                return
        except: time.sleep(1)

def db_update(task_id: str, status: str, progress: int, message: str, stage: str = None, result: dict = None):
    for attempt in range(3):
        try:
            sb = get_fresh_supabase()
            if sb:
                data = {"status": status, "progress": progress, "message": message, "updated_at": datetime.now().isoformat()}
                if stage: data["stage"] = stage
                if result: data["result"] = result
                sb.table("projects").update(data).eq("id", task_id).execute()
                print(f"📊 {status} {progress}%: {message}")
                return
        except: time.sleep(1)

def db_get(task_id: str):
    try:
        sb = get_fresh_supabase()
        if sb:
            res = sb.table("projects").select("*").eq("id", task_id).execute()
            if res.data: return res.data[0]
    except: pass
    return None

def upload_to_storage(file_path: str, bucket: str, dest_name: str, content_type: str) -> str:
    for attempt in range(3):
        try:
            sb = get_fresh_supabase()
            with open(file_path, "rb") as f:
                sb.storage.from_(bucket).upload(path=dest_name, file=f.read(), file_options={"content-type": content_type, "upsert": "true"})
            return sb.storage.from_(bucket).get_public_url(dest_name)
        except Exception as e:
            print(f"Storage error: {e}")
            time.sleep(1)
    return None

# ============= AI & Logic =============

def extract_audio(video_path: str, audio_path: str) -> bool:
    cmd = ["ffmpeg", "-i", video_path, "-vn", "-acodec", "libmp3lame", "-ab", "64k", "-ar", "16000", "-y", audio_path]
    return subprocess.run(cmd, capture_output=True).returncode == 0

def transcribe_groq(audio_path: str):
    client = get_groq()
    with open(audio_path, "rb") as f:
        transcription = client.audio.transcriptions.create(file=(os.path.basename(audio_path), f.read()), model="whisper-large-v3", response_format="verbose_json")
    
    segments = []
    for seg in transcription.segments:
        segments.append({"start": seg["start"], "end": seg["end"], "text": seg["text"].strip()})
    return segments, "en" # Assume EN source for now

def translate_text(text: str, src: str = "auto", tgt: str = "ar") -> str:
    if not text.strip(): return ""
    try:
        # Using deep-translator (Google Translate) - Much more reliable
        translated = GoogleTranslator(source=src, target=tgt).translate(text)
        print(f"🌐 Translated: {text[:20]}... -> {translated[:20]}...")
        return translated
    except Exception as e:
        print(f"⚠️ Translation Error: {e}")
        return text # Fallback

def tts_gemini_25(text: str, output_path: str) -> bool:
    if not GEMINI_API_KEY: return False
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        # Enhanced Prompt for Arabic
        prompt = f"Say this in natural Egyptian Arabic: {text}"
        
        response = client.models.generate_content(
            model="gemini-2.5-flash-preview-tts",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Zephyr"))
                )
            )
        )
        if response.candidates[0].content.parts[0].inline_data:
            with open(output_path, 'wb') as f:
                f.write(response.candidates[0].content.parts[0].inline_data.data)
            print(f"🎙️ Gemini TTS Success: {output_path}")
            return True
    except Exception as e:
        print(f"Gemini TTS Failed: {e}")
    return False

async def tts_edge(text: str, path: str):
    import edge_tts
    # Use a better Arabic voice for fallback
    await edge_tts.Communicate(text, "ar-EG-SalmaNeural").save(path)

async def generate_tts(text: str, path: str):
    # 1. Try Gemini (High Quality)
    if tts_gemini_25(text, path):
        return
    # 2. Fallback to Edge (Standard)
    print("⚠️ Using Fallback TTS")
    await tts_edge(text, path)

def merge_audio_video(video_path, audio_files, output_path):
    # 1. Concat audio
    list_file = "list.txt"
    with open(list_file, "w") as f:
        for a in audio_files: f.write(f"file '{os.path.abspath(a)}'\n")
    
    merged_audio = "merged_audio.mp3"
    subprocess.run(["ffmpeg", "-f", "concat", "-safe", "0", "-i", list_file, "-c", "copy", "-y", merged_audio], check=True)
    
    # 2. Merge with Video
    subprocess.run(["ffmpeg", "-i", video_path, "-i", merged_audio, "-c:v", "copy", "-map", "0:v:0", "-map", "1:a:0", "-shortest", "-y", output_path], check=True)
    
    os.remove(list_file)
    os.remove(merged_audio)
    return True

# ============= Main Process =============

class TaskResponse(BaseModel):
    task_id: str
    status: str
    progress: int
    message: str

@app.get("/")
def root():
    return {"status": "active", "version": "7.0.0", "tts": "Gemini 2.5 + Edge Fallback"}

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.post("/upload", response_model=TaskResponse)
async def upload(background_tasks: BackgroundTasks, file: UploadFile = File(...), mode: str = Form("DUBBING"), target_lang: str = Form("ar")):
    task_id = str(uuid.uuid4())
    path = os.path.join(UPLOAD_FOLDER, f"{task_id}_{file.filename}")
    with open(path, "wb") as f: f.write(await file.read())
    
    db_create(task_id, file.filename, mode)
    background_tasks.add_task(process_video_task, task_id, path, mode, target_lang, file.filename)
    return TaskResponse(task_id=task_id, status=Status.PENDING, progress=0, message="Started")

@app.get("/status/{task_id}")
def status(task_id: str):
    task = db_get(task_id)
    if task: return task
    return {"status": "UNKNOWN", "progress": 0}

async def process_video_task(task_id, video_path, mode, target_lang, filename):
    try:
        base = task_id[:8]
        audio_path = os.path.join(AUDIO_FOLDER, f"{base}.mp3")
        
        # 1. Extract
        db_update(task_id, Status.EXTRACTING, 10, "Extracting Audio...")
        extract_audio(video_path, audio_path)
        
        # 2. Transcribe
        db_update(task_id, Status.TRANSCRIBING, 30, "Listening (Groq)...")
        segments, src_lang = transcribe_groq(audio_path)
        
        # 3. Translate & Dub
        tts_files = []
        total = len(segments)
        
        import nest_asyncio
        nest_asyncio.apply()
        
        for i, seg in enumerate(segments):
            prog = 30 + int((i/total)*50)
            db_update(task_id, Status.GENERATING_AUDIO, prog, f"Dubbing segment {i+1}/{total}...")
            
            # TRANSLATE
            translated_text = translate_text(seg["text"], src="auto", tgt=target_lang)
            
            # TTS
            tts_path = os.path.join(AUDIO_FOLDER, f"tts_{base}_{i}.mp3")
            asyncio.run(generate_tts(translated_text, tts_path))
            tts_files.append(tts_path)
        
        # 4. Merge
        db_update(task_id, Status.MERGING, 90, "Merging Final Video...")
        output_path = os.path.join(OUTPUT_FOLDER, f"dubbed_{base}.mp4")
        merge_audio_video(video_path, tts_files, output_path)
        
        # 5. Upload
        db_update(task_id, Status.UPLOADING, 95, "Uploading...")
        url = upload_to_storage(output_path, "videos", f"dubbed/final_{base}.mp4", "video/mp4")
        
        result = {
            "title": filename,
            "mode": mode,
            "dubbed_video_url": url,
            "dubbed_video_path": output_path
        }
        
        db_update(task_id, Status.COMPLETED, 100, "Done!", result=result)
        
    except Exception as e:
        print(f"🔥 ERROR: {e}")
        import traceback
        traceback.print_exc()
        db_update(task_id, Status.FAILED, 0, f"Error: {str(e)[:50]}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=10000)
