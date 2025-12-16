"""
Arab Dubbing API - Version 18.0 (Replicate XTTS - Human Voice)
- TTS: Replicate XTTS v2 (Human Quality) → Edge TTS (Fallback)
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
import time
from datetime import datetime
from dotenv import load_dotenv
from groq import Groq
from deep_translator import GoogleTranslator

load_dotenv()

# Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN", "")

app = FastAPI(title="Arab Dubbing API", version="18.0.0")

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
    return {"status": "active", "version": "18.0.0", "tts_engine": "Replicate XTTS (Human Voice)"}

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

# 2. TRANSLATION (Google Translate - Fast & Reliable)
def translate_text(text: str, target_lang: str = "ar") -> str:
    if not text.strip(): return ""
    try:
        result = GoogleTranslator(source='auto', target=target_lang).translate(text)
        print(f"🌐 {text[:20]}... → {result[:20]}...")
        return result
    except Exception as e:
        print(f"⚠️ Translation Error: {e}")
        return text

# 3. VOICE GENERATION (Replicate XTTS Dynamic -> Fallback Edge TTS)
def generate_tts_replicate(text: str, path: str) -> bool:
    if not text.strip(): return False
    
    # Try Replicate (High Quality)
    if REPLICATE_API_TOKEN:
        try:
            import replicate
            print(f"💎 Text: {text[:20]}...")
            
            # DYNAMIC VERSION FETCHING:
            # Instead of hardcoding the hash, we ask Replicate for the latest version.
            # This prevents "422 Invalid Version" errors when the model is updated.
            model = replicate.models.get("lucataco/xtts-v2")
            latest_version = model.versions.list()[0]
            print(f"🔹 Using latest XTTS version: {latest_version.id[:8]}...")

            output = replicate.run(
                f"lucataco/xtts-v2:{latest_version.id}",
                input={
                    "text": text,
                    "speaker": "Maysandra",
                    "language": "ar",
                    "cleanup_voice": True
                }
            )
            
            response = requests.get(output)
            if response.status_code == 200:
                with open(path, 'wb') as f:
                    f.write(response.content)
                print("✅ Replicate Success!")
                return True
        except Exception as e:
            print(f"⚠️ Replicate Failed (Switching to Fallback): {e}")

    # Fallback: Edge TTS (Free & Stable)
    return generate_tts_edge(text, path)

def generate_tts_edge(text: str, path: str) -> bool:
    """Fallback: Edge TTS (Salma voice)"""
    if not text.strip(): 
        return False
    try:
        print(f"🗣️ Edge TTS Fallback: {text[:30]}...")
        cmd = ["edge-tts", "--text", text, "--write-media", path, "--voice", "ar-EG-SalmaNeural", "--rate=-3%"]
        subprocess.run(cmd, check=True, capture_output=True)
        return os.path.exists(path) and os.path.getsize(path) > 100
    except Exception as e:
        print(f"❌ Edge TTS Failed: {e}")
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
    
    db_update(task_id, "PENDING", 0, "جاري التجهيز...")
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
        
        db_update(task_id, "EXTRACTING", 10, "استخراج الصوت...")
        extract_audio(video_path, audio_path)
        
        db_update(task_id, "TRANSCRIBING", 20, "تحليل الكلام...")
        segments = smart_transcribe(audio_path)
        
        if not segments:
            db_update(task_id, "FAILED", 0, "فشل تحليل الكلام")
            return

        tts_files = []
        total = len(segments)
        
        for i, seg in enumerate(segments):
            progress = 20 + int((i / total) * 60)
            
            if i % 2 == 0:
                db_update(task_id, "GENERATING_AUDIO", progress, f"توليد الصوت البشري {i+1}/{total}...")
            
            # 1. Translate
            translated = translate_text(seg["text"], target_lang)
            
            # 2. TTS (Replicate XTTS → Edge Fallback)
            tts_path = os.path.join(AUDIO_FOLDER, f"tts_{base}_{i}.mp3")
            if generate_tts_replicate(translated, tts_path):
                tts_files.append(tts_path)
            
        db_update(task_id, "MERGING", 90, "دمج الفيديو...")
        output_path = os.path.join(OUTPUT_FOLDER, f"dubbed_{base}.mp4")
        merge_audio_video(video_path, tts_files, output_path)
        
        db_update(task_id, "UPLOADING", 95, "رفع النتيجة...")
        url = upload_to_storage(output_path, "videos", f"dubbed/final_{base}.mp4", "video/mp4")
        
        db_update(task_id, "COMPLETED", 100, "تم بنجاح! 🎉", result={"dubbed_video_url": url, "title": filename})
        
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
        db_update(task_id, "FAILED", 0, f"خطأ: {str(e)[:100]}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=10000)