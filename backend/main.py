"""
Arab Dubbing API - Production Version v4.0
AI-powered video dubbing and translation platform

CLOUD-BASED ARCHITECTURE:
- Groq API for Whisper transcription (whisper-large-v3)
- Supabase for task persistence
- Edge-TTS for Arabic speech synthesis
- Argos Translate for translation
- FFmpeg for audio/video processing
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
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

app = FastAPI(
    title="Arab Dubbing API",
    description="AI-powered video dubbing - دبلجة العرب",
    version="4.0.0"
)

# ============= CORS =============
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Directories
AUDIO_FOLDER = "audio"
OUTPUT_FOLDER = "output"
UPLOAD_FOLDER = "uploads"

for folder in [AUDIO_FOLDER, OUTPUT_FOLDER, UPLOAD_FOLDER]:
    os.makedirs(folder, exist_ok=True)

# Mount static files
app.mount("/output", StaticFiles(directory=OUTPUT_FOLDER), name="output")

# ============= Supabase Client =============
_supabase = None

def get_supabase():
    global _supabase
    if _supabase is None:
        try:
            from supabase import create_client
            _supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
            print("✅ Supabase connected")
        except Exception as e:
            print(f"⚠️ Supabase error: {e}")
    return _supabase

# ============= Groq Client =============
_groq = None

def get_groq():
    global _groq
    if _groq is None:
        try:
            from groq import Groq
            _groq = Groq(api_key=GROQ_API_KEY)
            print("✅ Groq client ready")
        except Exception as e:
            print(f"⚠️ Groq error: {e}")
    return _groq

# ============= Task Status =============
class TaskStatus:
    PENDING = "PENDING"
    DOWNLOADING = "DOWNLOADING"
    TRANSCRIBING = "TRANSCRIBING"
    TRANSLATING = "TRANSLATING"
    GENERATING_AUDIO = "GENERATING_AUDIO"
    MERGING = "MERGING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

def db_create(task_id: str, filename: str, mode: str):
    try:
        sb = get_supabase()
        if sb:
            sb.table("projects").insert({
                "id": task_id,
                "title": filename,
                "status": TaskStatus.PENDING,
                "progress": 0,
                "message": "جاري البدء...",
                "stage": "PENDING",
                "source": "upload",
                "mode": mode,
                "created_at": datetime.now().isoformat(),
            }).execute()
    except Exception as e:
        print(f"⚠️ DB create: {e}")

def db_update(task_id: str, status: str, progress: int, message: str, stage: str = None, result: dict = None):
    try:
        sb = get_supabase()
        if sb:
            data = {
                "status": status,
                "progress": progress,
                "message": message,
                "stage": stage or status,
                "updated_at": datetime.now().isoformat()
            }
            if result:
                data["result"] = result
            sb.table("projects").update(data).eq("id", task_id).execute()
            print(f"📊 {task_id[:8]}: {status} {progress}%")
    except Exception as e:
        print(f"⚠️ DB update: {e}")

def db_get(task_id: str) -> dict:
    try:
        sb = get_supabase()
        if sb:
            res = sb.table("projects").select("*").eq("id", task_id).execute()
            if res.data and len(res.data) > 0:
                return res.data[0]
    except Exception as e:
        print(f"⚠️ DB get: {e}")
        return {"status": "PROCESSING", "progress": 10, "message": "جاري المعالجة..."}
    return None

# ============= Models =============
class TaskResponse(BaseModel):
    task_id: str
    status: str
    progress: int
    message: str
    stage: Optional[str] = None
    result: Optional[dict] = None

# ============= Helper Functions =============

def extract_audio(video_path: str, audio_path: str) -> bool:
    """Extract audio using ffmpeg"""
    cmd = [
        "ffmpeg", "-i", video_path,
        "-vn", "-acodec", "libmp3lame", "-ab", "64k", "-ar", "16000",
        "-y", audio_path
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=300)
        return True
    except Exception as e:
        print(f"❌ Extract audio: {e}")
        return False

def transcribe_with_groq(audio_path: str) -> tuple:
    """Transcribe audio using Groq API (whisper-large-v3)"""
    try:
        client = get_groq()
        if not client:
            raise Exception("Groq client not available")
        
        with open(audio_path, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                file=(os.path.basename(audio_path), audio_file.read()),
                model="whisper-large-v3",
                response_format="verbose_json",
                language="en"  # Auto-detect would be: None
            )
        
        # Extract segments with timestamps
        segments = []
        detected_lang = "en"
        
        if hasattr(transcription, 'segments') and transcription.segments:
            for seg in transcription.segments:
                segments.append({
                    "start": seg.get("start", 0),
                    "end": seg.get("end", 0),
                    "text": seg.get("text", "").strip()
                })
            detected_lang = getattr(transcription, 'language', 'en') or 'en'
        elif hasattr(transcription, 'text'):
            # Fallback: single segment
            segments.append({
                "start": 0,
                "end": 60,
                "text": transcription.text.strip()
            })
        
        print(f"✅ Groq transcribed: {len(segments)} segments, lang={detected_lang}")
        return segments, detected_lang
        
    except Exception as e:
        print(f"❌ Groq transcription error: {e}")
        raise

def translate_text(text: str, src: str = "en", tgt: str = "ar") -> str:
    """Translate using argostranslate"""
    if not text.strip():
        return text
    try:
        import argostranslate.translate
        return argostranslate.translate.translate(text, src, tgt)
    except:
        return text

async def generate_tts(text: str, output_path: str, voice: str = "ar-EG-SalmaNeural"):
    """Generate TTS using edge-tts"""
    import edge_tts
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_path)

def merge_audio_ffmpeg(audio_files: list, output: str) -> bool:
    """Merge audio files"""
    if not audio_files:
        return False
    
    list_file = os.path.join(AUDIO_FOLDER, "merge.txt")
    with open(list_file, "w") as f:
        for a in audio_files:
            f.write(f"file '{os.path.abspath(a)}'\n")
    
    cmd = ["ffmpeg", "-f", "concat", "-safe", "0", "-i", list_file, "-c", "copy", "-y", output]
    
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=120)
        os.remove(list_file)
        return True
    except:
        return False

def combine_video_audio(video_path: str, audio_path: str, output_path: str) -> bool:
    """Combine video with new audio"""
    cmd = [
        "ffmpeg", "-i", video_path, "-i", audio_path,
        "-c:v", "copy", "-map", "0:v:0", "-map", "1:a:0",
        "-shortest", "-y", output_path
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=600)
        return True
    except Exception as e:
        print(f"❌ Combine: {e}")
        return False

# ============= API Endpoints =============

@app.get("/")
def root():
    return {"status": "active", "version": "4.0.0", "whisper": "Groq Cloud"}

@app.get("/health")
def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

# ============= Upload Endpoint =============
MAX_SIZE = 25 * 1024 * 1024  # 25MB (Groq limit)

@app.post("/upload", response_model=TaskResponse)
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    mode: str = Form(default="DUBBING"),
    target_lang: str = Form(default="ar")
):
    """Upload video for processing"""
    task_id = str(uuid.uuid4())
    
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ['.mp4', '.mkv', '.webm', '.mov', '.avi', '.m4v']:
        raise HTTPException(400, "نوع الملف غير مدعوم")
    
    path = os.path.join(UPLOAD_FOLDER, f"{task_id}{ext}")
    try:
        with open(path, "wb") as f:
            while chunk := await file.read(1024 * 1024):
                f.write(chunk)
        
        size = os.path.getsize(path)
        if size > MAX_SIZE:
            os.remove(path)
            raise HTTPException(400, f"حجم الملف كبير (الحد {MAX_SIZE//1024//1024}MB)")
        
        print(f"📤 Uploaded: {file.filename} ({size/1024/1024:.1f}MB)")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"فشل الرفع: {e}")
    
    db_create(task_id, file.filename, mode)
    background_tasks.add_task(process_video, task_id, path, mode, target_lang, file.filename)
    
    return TaskResponse(
        task_id=task_id,
        status=TaskStatus.PENDING,
        progress=0,
        message="تم رفع الفيديو، جاري المعالجة...",
        stage="PENDING"
    )

# ============= Processing =============

async def process_video(task_id: str, video_path: str, mode: str, target_lang: str, filename: str):
    """Main processing pipeline using Groq API"""
    try:
        print(f"🎬 Processing: {task_id[:8]}")
        
        base = task_id[:8]
        audio_path = os.path.join(AUDIO_FOLDER, f"{base}.mp3")
        
        # STEP 1: Extract Audio
        db_update(task_id, TaskStatus.DOWNLOADING, 10, "استخراج الصوت...", "DOWNLOAD")
        
        if not extract_audio(video_path, audio_path):
            raise Exception("فشل استخراج الصوت")
        
        # STEP 2: Transcribe with Groq
        db_update(task_id, TaskStatus.TRANSCRIBING, 20, "تحليل الصوت (Groq AI)...", "TRANSCRIPTION")
        
        segments, detected_lang = transcribe_with_groq(audio_path)
        
        db_update(task_id, TaskStatus.TRANSCRIBING, 40, f"تم استخراج {len(segments)} جملة ✓", "TRANSCRIPTION")
        
        result = {"title": filename, "detected_language": detected_lang}
        gc.collect()
        
        # STEP 3: Setup translation
        try:
            import argostranslate.package
            argostranslate.package.update_package_index()
            avail = argostranslate.package.get_available_packages()
            pkg = next((p for p in avail if p.from_code == "en" and p.to_code == "ar"), None)
            if pkg:
                inst = argostranslate.package.get_installed_packages()
                if not any(p.from_code == "en" and p.to_code == "ar" for p in inst):
                    argostranslate.package.install_from_path(pkg.download())
        except Exception as e:
            print(f"Argos: {e}")
        
        # STEP 4: Generate TTS
        if mode in ["DUBBING", "BOTH"]:
            db_update(task_id, TaskStatus.GENERATING_AUDIO, 45, "ترجمة وتوليد الصوت...", "VOICE")
            
            import nest_asyncio
            nest_asyncio.apply()
            
            tts_files = []
            total = len(segments)
            
            for i, seg in enumerate(segments):
                text = seg.get("text", "").strip()
                if not text:
                    continue
                
                if i % 3 == 0:
                    prog = 45 + int((i / total) * 35)
                    db_update(task_id, TaskStatus.GENERATING_AUDIO, prog, f"توليد الصوت {i+1}/{total}...", "VOICE")
                
                translated = translate_text(text, detected_lang or "en", target_lang)
                
                tts_path = os.path.join(AUDIO_FOLDER, f"tts_{base}_{i}.mp3")
                try:
                    asyncio.get_event_loop().run_until_complete(generate_tts(translated, tts_path))
                    tts_files.append(tts_path)
                except Exception as e:
                    print(f"TTS {i}: {e}")
            
            # STEP 5: Merge TTS
            if tts_files:
                db_update(task_id, TaskStatus.MERGING, 85, "دمج الصوت...", "MERGING")
                
                merged_audio = os.path.join(AUDIO_FOLDER, f"merged_{base}.mp3")
                
                if merge_audio_ffmpeg(tts_files, merged_audio):
                    db_update(task_id, TaskStatus.MERGING, 90, "دمج مع الفيديو...", "MERGING")
                    
                    output_name = f"dubbed_{base}.mp4"
                    output_path = os.path.join(OUTPUT_FOLDER, output_name)
                    
                    if combine_video_audio(video_path, merged_audio, output_path):
                        result["dubbed_video_url"] = f"/output/{output_name}"
                        result["dubbed_video_path"] = output_path
                    
                    # Cleanup
                    for f in tts_files:
                        try: os.remove(f)
                        except: pass
                    try: os.remove(merged_audio)
                    except: pass
            
            gc.collect()
        
        # STEP 6: Subtitles
        if mode in ["SUBTITLES", "BOTH"]:
            srt = ""
            for i, seg in enumerate(segments, 1):
                text = seg.get("text", "").strip()
                if not text:
                    continue
                
                translated = translate_text(text, detected_lang or "en", target_lang)
                
                def fmt(s):
                    h, m = int(s // 3600), int((s % 3600) // 60)
                    sec, ms = int(s % 60), int((s - int(s)) * 1000)
                    return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"
                
                srt += f"{i}\n{fmt(seg['start'])} --> {fmt(seg['end'])}\n{translated}\n\n"
            
            srt_name = f"{base}_{target_lang}.srt"
            srt_path = os.path.join(OUTPUT_FOLDER, srt_name)
            with open(srt_path, "w", encoding="utf-8") as f:
                f.write(srt)
            
            result["srt_url"] = f"/output/{srt_name}"
        
        # DONE
        db_update(task_id, TaskStatus.COMPLETED, 100, "تمت العملية بنجاح! 🎉", "COMPLETED", result)
        print(f"✅ Done: {task_id[:8]}")
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        db_update(task_id, TaskStatus.FAILED, 0, f"فشل: {str(e)[:100]}", "FAILED")
        print(f"❌ Failed: {task_id[:8]} - {e}")
    finally:
        gc.collect()

# ============= Status =============

@app.get("/status/{task_id}", response_model=TaskResponse)
def get_status(task_id: str):
    task = db_get(task_id)
    if not task:
        raise HTTPException(404, "لم يتم العثور على المهمة")
    
    return TaskResponse(
        task_id=task_id,
        status=task.get("status", "UNKNOWN"),
        progress=task.get("progress", 0),
        message=task.get("message", ""),
        stage=task.get("stage"),
        result=task.get("result")
    )

# ============= Download =============

@app.get("/download/{task_id}/{file_type}")
def download(task_id: str, file_type: Literal["video", "srt"]):
    task = db_get(task_id)
    if not task:
        raise HTTPException(404, "لم يتم العثور على المهمة")
    
    result = task.get("result") or {}
    
    if file_type == "video" and result.get("dubbed_video_path"):
        return FileResponse(result["dubbed_video_path"], filename="dubbed_video.mp4", media_type="video/mp4")
    elif file_type == "srt" and result.get("srt_url"):
        srt_path = os.path.join(OUTPUT_FOLDER, os.path.basename(result["srt_url"]))
        if os.path.exists(srt_path):
            return FileResponse(srt_path, filename="subtitles.srt", media_type="text/plain")
    
    raise HTTPException(404, "الملف غير متوفر")

# ============= Startup =============

@app.on_event("startup")
async def startup():
    print("🚀 Arab Dubbing API v4.0")
    print(f"🧠 Whisper: Groq Cloud (whisper-large-v3)")
    print(f"💾 Storage: Supabase")
    
    if not GROQ_API_KEY:
        print("⚠️ GROQ_API_KEY not set!")
    else:
        get_groq()
    
    if SUPABASE_URL:
        get_supabase()
    
    print("✅ Ready!")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
