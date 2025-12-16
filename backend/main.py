"""
Arab Dubbing API - Version 14.0 (Smart Cloud Core)
- PRIMARY: Replicate (Whisper v3 + XTTS v2) -> Studio Quality
- FALLBACK: Edge TTS + Groq -> Free & Fast
- LOGIC: Auto-switch if Replicate fails (Billing/Quota limits)
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import os
import uuid
import subprocess
import time
import requests
import replicate
from datetime import datetime
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

# Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

app = FastAPI(title="Arab Dubbing API", version="14.0.0")

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
    return {"status": "active", "engine": "Hybrid (Cloud/Free)"}

# --- HELPERS ---
def get_fresh_supabase():
    try:
        from supabase import create_client
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except: return None

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
    except: return None

def extract_audio(video_path: str, audio_path: str) -> bool:
    cmd = ["ffmpeg", "-i", video_path, "-vn", "-acodec", "libmp3lame", "-ab", "64k", "-ar", "16000", "-y", audio_path]
    return subprocess.run(cmd, capture_output=True).returncode == 0

# --- SMART AI LAYERS ---

# 1. TRANSCRIPTION (Replicate -> Fallback to Groq)
def smart_transcribe(audio_path: str):
    # Try Replicate First (Best Quality)
    if REPLICATE_API_TOKEN:
        print("🎙️ Attempting Replicate Whisper (Large-v3)...")
        try:
            output = replicate.run(
                "openai/whisper:4d50797290df275329f2727f9324b90714c4c10425c2763f3394747719632832",
                input={"audio": open(audio_path, "rb"), "model": "large-v3", "timestamp_granularity": "segment"}
            )
            segments = []
            if 'segments' in output:
                for seg in output['segments']:
                    segments.append({"start": seg["start"], "end": seg["end"], "text": seg["text"].strip()})
            if segments: return segments
        except Exception as e:
            print(f"⚠️ Replicate Whisper Failed: {e}")

    # Fallback to Groq (Fast & Free)
    print("🔄 Falling back to Groq Whisper...")
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
        print(f"❌ Groq Failed: {e}")
        return []

# 2. TRANSLATION (Gemini Slang)
def translate_with_gemini(text: str, target_lang: str = "ar") -> str:
    if not text.strip(): return ""
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"""
        Translate to Egyptian Arabic (Slang/Ammiya). 
        Make it sound like a real person. Keep it concise.
        Original: "{text}"
        """
        response = model.generate_content(prompt)
        return response.text.strip()
    except: return text

# 3. VOICE GENERATION (Replicate -> Fallback to Edge)
def smart_tts_generate(text: str, path: str):
    if not text.strip(): return
    
    # Try Replicate XTTS (Human Quality)
    if REPLICATE_API_TOKEN:
        try:
            # Using 'Male Cal' as base, optimized for Arabic reading
            output_url = replicate.run(
                "lucataco/xtts-v2:684bc3855b37866c9c65add50fb7c579e667f7c5279bd28afb79873d93b957fd",
                input={"text": text, "speaker": "Male Cal", "language": "ar", "cleanup_voice": True, "temperature": 0.7}
            )
            if output_url:
                with open(path, "wb") as f:
                    f.write(requests.get(output_url).content)
                return True
        except Exception as e:
            print(f"⚠️ Replicate XTTS Failed: {e}")

    # Fallback to Edge TTS (Shakir - High Quality Free)
    try:
        import edge_tts
        # Running via subprocess to handle async in sync context safely
        cmd = ["edge-tts", "--text", text, "--write-media", path, "--voice", "ar-EG-ShakirNeural", "--rate=-5%"]
        subprocess.run(cmd, check=True)
        return True
    except: return False

def merge_audio_video(video_path, audio_files, output_path):
    valid_files = [f for f in audio_files if os.path.exists(f)]
    if not valid_files: return

    list_file = "list.txt"
    with open(list_file, "w") as f:
        for a in valid_files: f.write(f"file '{os.path.abspath(a)}'\n")
    
    merged_tts = "merged_tts.mp3"
    subprocess.run(["ffmpeg", "-f", "concat", "-safe", "0", "-i", list_file, "-c", "copy", "-y", merged_tts], check=True)
    
    # Background Ducking (Audio Mixing)
    cmd = [
        "ffmpeg", "-i", video_path, "-i", merged_tts, 
        "-filter_complex", "[0:a]volume=0.15[bg];[1:a]volume=1.4[fg];[bg][fg]amix=inputs=2:duration=first[a]", 
        "-map", "0:v", "-map", "[a]", 
        "-c:v", "copy", "-c:a", "aac", 
        "-shortest", "-y", output_path
    ]
    try:
        subprocess.run(cmd, check=True)
    except:
        subprocess.run(["ffmpeg", "-i", video_path, "-i", merged_tts, "-c:v", "copy", "-map", "0:v:0", "-map", "1:a:0", "-shortest", "-y", output_path], check=True)
    
    try:
        os.remove(list_file)
        os.remove(merged_tts)
    except: pass

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
    
    db_update(task_id, "PENDING", 0, "Initializing Cloud Engine...")
    background_tasks.add_task(process_video_task, task_id, path, mode, target_lang, file.filename)
    return TaskResponse(task_id=task_id, status="PENDING")

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
        
        db_update(task_id, "EXTRACTING", 10, "Extracting Audio...")
        extract_audio(video_path, audio_path)
        
        db_update(task_id, "TRANSCRIBING", 20, "Transcribing Audio...")
        # ✅ Smart Transcribe (Replicate -> Groq)
        segments = smart_transcribe(audio_path)
        
        if not segments:
             db_update(task_id, "FAILED", 0, "Transcription Failed")
             return

        tts_files = []
        total = len(segments)
        
        for i, seg in enumerate(segments):
            progress = 20 + int((i / total) * 60)
            if i % 2 == 0: db_update(task_id, "GENERATING_AUDIO", progress, f"Dubbing {i+1}/{total}...")
            
            # 1. Translate (Gemini Slang)
            translated = translate_with_gemini(seg["text"], target_lang)
            
            # 2. Generate Voice (Replicate -> Edge)
            tts_path = os.path.join(AUDIO_FOLDER, f"tts_{base}_{i}.mp3")
            smart_tts_generate(translated, tts_path)
            tts_files.append(tts_path)
            
        db_update(task_id, "MERGING", 90, "Mixing Final Video...")
        output_path = os.path.join(OUTPUT_FOLDER, f"dubbed_{base}.mp4")
        merge_audio_video(video_path, tts_files, output_path)
        
        db_update(task_id, "UPLOADING", 95, "Uploading Result...")
        url = upload_to_storage(output_path, "videos", f"dubbed/final_{base}.mp4", "video/mp4")
        
        db_update(task_id, "COMPLETED", 100, "Done! 🎉", result={"dubbed_video_url": url, "title": filename})
        
        # Cleanup
        try:
            os.remove(video_path)
            os.remove(audio_path)
            for f in tts_files:
                if os.path.exists(f): os.remove(f)
        except: pass
            
    except Exception as e:
        print(f"🔥 FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        db_update(task_id, "FAILED", 0, f"Error: {str(e)[:100]}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=10000)