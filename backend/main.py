"""
Arab Dubbing API - Version 9.1 (Model Name Fix)
- FIXED: Changed model alias 'gemini-1.5-flash' to explicit 'gemini-1.5-flash-001'
- PURPOSE: Solves 404 Model Not Found errors on v1beta API
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import os
import asyncio
import uuid
import subprocess
import time
from datetime import datetime
from dotenv import load_dotenv

# Load env
load_dotenv()

# Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

app = FastAPI(title="Arab Dubbing API", version="9.1.0")

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

# ============= DB Helper =============
def get_fresh_supabase():
    try:
        from supabase import create_client
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        print(f"⚠️ Supabase Error: {e}")
        return None

class Status:
    PENDING = "PENDING"
    EXTRACTING = "EXTRACTING"
    TRANSCRIBING = "TRANSCRIBING"
    TRANSLATING = "TRANSLATING"
    GENERATING_AUDIO = "GENERATING_AUDIO"
    MERGING = "MERGING"
    UPLOADING = "UPLOADING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

def db_update(task_id: str, status: str, progress: int, message: str, result: dict = None):
    try:
        sb = get_fresh_supabase()
        if sb:
            data = {"status": status, "progress": progress, "message": message, "updated_at": datetime.now().isoformat()}
            if result: data["result"] = result
            sb.table("projects").update(data).eq("id", task_id).execute()
            print(f"📊 {status} {progress}%: {message}")
    except: pass

def upload_to_storage(file_path: str, bucket: str, dest_name: str, content_type: str) -> str:
    try:
        sb = get_fresh_supabase()
        if not sb: return None
        with open(file_path, "rb") as f:
            sb.storage.from_(bucket).upload(path=dest_name, file=f.read(), file_options={"content-type": content_type, "upsert": "true"})
        return sb.storage.from_(bucket).get_public_url(dest_name)
    except Exception as e:
        print(f"Storage Upload Error: {e}")
        return None

# ============= AI Logic =============

def extract_audio(video_path: str, audio_path: str) -> bool:
    cmd = ["ffmpeg", "-i", video_path, "-vn", "-acodec", "libmp3lame", "-ab", "64k", "-ar", "16000", "-y", audio_path]
    return subprocess.run(cmd, capture_output=True).returncode == 0

def transcribe_groq(audio_path: str):
    try:
        from groq import Groq
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
        else:
            segments.append({"start": 0, "end": 10, "text": transcription.text})
        return segments
    except Exception as e:
        print(f"Groq Error: {e}")
        return []

def translate_with_gemini(text: str, target_lang: str = "ar") -> str:
    if not text.strip(): return ""
    if not GEMINI_API_KEY: return text
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        # FIXED: Using explicit version 'gemini-1.5-flash-001'
        prompt = f"""Translate the following text to {target_lang} (Arabic). 
        Maintain the meaning suitable for video dubbing. 
        Only return the translated text, no explanations.
        Text: {text}"""
        
        response = client.models.generate_content(
            model="gemini-1.5-flash-001", 
            contents=prompt
        )
        translated = response.text.strip()
        print(f"🌐 Gemini Trans: {text[:15]}... -> {translated[:15]}...")
        return translated
    except Exception as e:
        print(f"⚠️ Translation Failed: {e}")
        # LAST RESORT FALLBACK: If API fails, return original text to avoid crashing
        return text

async def generate_tts(text: str, path: str):
    # Using Edge TTS (Stable & Free)
    try:
        import edge_tts
        await edge_tts.Communicate(text, "ar-EG-SalmaNeural").save(path)
        return
    except Exception as e:
        print(f"Edge TTS Error: {e}")

def merge_audio_video(video_path, audio_files, output_path):
    if not audio_files: return
    list_file = "list.txt"
    with open(list_file, "w") as f:
        for a in audio_files: f.write(f"file '{os.path.abspath(a)}'\n")
    
    merged_audio = "merged_audio.mp3"
    subprocess.run(["ffmpeg", "-f", "concat", "-safe", "0", "-i", list_file, "-c", "copy", "-y", merged_audio], check=True)
    subprocess.run(["ffmpeg", "-i", video_path, "-i", merged_audio, "-c:v", "copy", "-map", "0:v:0", "-map", "1:a:0", "-shortest", "-y", output_path], check=True)
    
    try:
        os.remove(list_file)
        os.remove(merged_audio)
    except: pass

# ============= Routes =============

class TaskResponse(BaseModel):
    task_id: str
    status: str

@app.post("/upload", response_model=TaskResponse)
async def upload(background_tasks: BackgroundTasks, file: UploadFile = File(...), mode: str = Form("DUBBING"), target_lang: str = Form("ar")):
    task_id = str(uuid.uuid4())
    path = os.path.join(UPLOAD_FOLDER, f"{task_id}_{file.filename}")
    with open(path, "wb") as f: f.write(await file.read())
    
    # Init DB
    sb = get_fresh_supabase()
    if sb:
        sb.table("projects").insert({
            "id": task_id, "title": file.filename, "status": Status.PENDING, 
            "progress": 0, "mode": mode, "created_at": datetime.now().isoformat()
        }).execute()

    background_tasks.add_task(process_video_task, task_id, path, mode, target_lang, file.filename)
    return TaskResponse(task_id=task_id, status=Status.PENDING)

@app.get("/status/{task_id}")
def status(task_id: str):
    sb = get_fresh_supabase()
    if sb:
        res = sb.table("projects").select("*").eq("id", task_id).execute()
        if res.data: return res.data[0]
    return {"status": "UNKNOWN"}

async def process_video_task(task_id, video_path, mode, target_lang, filename):
    try:
        base = task_id[:8]
        audio_path = os.path.join(AUDIO_FOLDER, f"{base}.mp3")
        
        db_update(task_id, Status.EXTRACTING, 10, "Extracting Audio...")
        extract_audio(video_path, audio_path)
        
        db_update(task_id, Status.TRANSCRIBING, 30, "Transcribing...")
        segments = transcribe_groq(audio_path)
        
        tts_files = []
        total = len(segments)
        
        for i, seg in enumerate(segments):
            progress = 30 + int((i / total) * 50)
            if i % 2 == 0:
                db_update(task_id, Status.GENERATING_AUDIO, progress, f"Dubbing {i+1}/{total}...")
            
            # 1. Translate (Using explicit Gemini model name)
            translated_text = translate_with_gemini(seg["text"], target_lang)
            
            # 2. TTS (Using Edge TTS)
            tts_path = os.path.join(AUDIO_FOLDER, f"tts_{base}_{i}.mp3")
            await generate_tts(translated_text, tts_path)
            tts_files.append(tts_path)
            
        db_update(task_id, Status.MERGING, 90, "Merging...")
        output_path = os.path.join(OUTPUT_FOLDER, f"dubbed_{base}.mp4")
        merge_audio_video(video_path, tts_files, output_path)
        
        db_update(task_id, Status.UPLOADING, 95, "Uploading...")
        url = upload_to_storage(output_path, "videos", f"dubbed/final_{base}.mp4", "video/mp4")
        
        result = {"dubbed_video_url": url, "title": filename}
        db_update(task_id, Status.COMPLETED, 100, "Done!", result=result)
        
    except Exception as e:
        print(f"🔥 FATAL ERROR: {e}")
        db_update(task_id, Status.FAILED, 0, f"Error: {str(e)[:100]}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=10000)