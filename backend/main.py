"""
Arab Dubbing API - Production Version v5.0
AI-powered video dubbing and translation platform

FEATURES:
- Groq API for Whisper transcription (whisper-large-v3)
- Supabase Storage for video/subtitle hosting
- Conditional processing based on mode (TRANSLATION/DUBBING/BOTH)
- Edge-TTS for Arabic speech synthesis
- Argos Translate for translation
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

load_dotenv()

# Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

app = FastAPI(title="Arab Dubbing API", version="5.0.0")

# CORS
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

app.mount("/output", StaticFiles(directory=OUTPUT_FOLDER), name="output")

# ============= Clients =============
_supabase = None
_groq = None

def get_supabase():
    global _supabase
    if _supabase is None:
        try:
            from supabase import create_client
            _supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        except Exception as e:
            print(f"⚠️ Supabase: {e}")
    return _supabase

def get_groq():
    global _groq
    if _groq is None:
        try:
            from groq import Groq
            _groq = Groq(api_key=GROQ_API_KEY)
        except Exception as e:
            print(f"⚠️ Groq: {e}")
    return _groq

# ============= Task Status =============
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
    try:
        sb = get_supabase()
        if sb:
            sb.table("projects").insert({
                "id": task_id,
                "title": filename,
                "status": Status.PENDING,
                "progress": 0,
                "message": "جاري البدء...",
                "stage": "PENDING",
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

# ============= Storage Functions =============

def upload_to_supabase_storage(file_path: str, bucket: str, dest_name: str, content_type: str) -> str:
    """Upload file to Supabase Storage and return public URL"""
    try:
        sb = get_supabase()
        if not sb:
            raise Exception("Supabase not available")
        
        with open(file_path, "rb") as f:
            file_data = f.read()
        
        # Upload to bucket
        sb.storage.from_(bucket).upload(
            path=dest_name,
            file=file_data,
            file_options={"content-type": content_type, "upsert": "true"}
        )
        
        # Get public URL
        public_url = sb.storage.from_(bucket).get_public_url(dest_name)
        print(f"✅ Uploaded to Supabase: {dest_name}")
        return public_url
        
    except Exception as e:
        print(f"❌ Storage upload error: {e}")
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
    cmd = ["ffmpeg", "-i", video_path, "-vn", "-acodec", "libmp3lame", "-ab", "64k", "-ar", "16000", "-y", audio_path]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=300)
        return True
    except:
        return False

def transcribe_groq(audio_path: str) -> tuple:
    """Transcribe using Groq API"""
    try:
        client = get_groq()
        if not client:
            raise Exception("Groq not available")
        
        with open(audio_path, "rb") as f:
            transcription = client.audio.transcriptions.create(
                file=(os.path.basename(audio_path), f.read()),
                model="whisper-large-v3",
                response_format="verbose_json"
            )
        
        segments = []
        lang = "en"
        
        if hasattr(transcription, 'segments') and transcription.segments:
            for seg in transcription.segments:
                segments.append({
                    "start": seg.get("start", 0),
                    "end": seg.get("end", 0),
                    "text": seg.get("text", "").strip()
                })
            lang = getattr(transcription, 'language', 'en') or 'en'
        elif hasattr(transcription, 'text'):
            segments.append({"start": 0, "end": 60, "text": transcription.text.strip()})
        
        return segments, lang
    except Exception as e:
        print(f"❌ Groq: {e}")
        raise

def translate_text(text: str, src: str = "en", tgt: str = "ar") -> str:
    if not text.strip():
        return text
    try:
        import argostranslate.translate
        return argostranslate.translate.translate(text, src, tgt)
    except:
        return text

async def tts_edge(text: str, path: str, voice: str = "ar-EG-SalmaNeural"):
    import edge_tts
    c = edge_tts.Communicate(text, voice)
    await c.save(path)

def merge_audio(files: list, output: str) -> bool:
    if not files:
        return False
    list_file = os.path.join(AUDIO_FOLDER, "merge.txt")
    with open(list_file, "w") as f:
        for a in files:
            f.write(f"file '{os.path.abspath(a)}'\n")
    cmd = ["ffmpeg", "-f", "concat", "-safe", "0", "-i", list_file, "-c", "copy", "-y", output]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=120)
        os.remove(list_file)
        return True
    except:
        return False

def combine_video_audio(video: str, audio: str, output: str) -> bool:
    cmd = ["ffmpeg", "-i", video, "-i", audio, "-c:v", "copy", "-map", "0:v:0", "-map", "1:a:0", "-shortest", "-y", output]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=600)
        return True
    except:
        return False

def generate_srt(segments: list, lang: str, tgt: str) -> str:
    """Generate SRT content from segments"""
    srt = ""
    for i, seg in enumerate(segments, 1):
        text = seg.get("text", "").strip()
        if not text:
            continue
        
        translated = translate_text(text, lang, tgt)
        
        def fmt(s):
            h, m = int(s // 3600), int((s % 3600) // 60)
            sec, ms = int(s % 60), int((s - int(s)) * 1000)
            return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"
        
        srt += f"{i}\n{fmt(seg['start'])} --> {fmt(seg['end'])}\n{translated}\n\n"
    
    return srt

# ============= API Endpoints =============

@app.get("/")
def root():
    return {"status": "active", "version": "5.0.0"}

@app.get("/health")
def health():
    return {"status": "healthy"}

MAX_SIZE = 25 * 1024 * 1024  # 25MB

@app.post("/upload", response_model=TaskResponse)
async def upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    mode: str = Form(default="DUBBING"),
    target_lang: str = Form(default="ar")
):
    task_id = str(uuid.uuid4())
    
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ['.mp4', '.mkv', '.webm', '.mov', '.avi']:
        raise HTTPException(400, "نوع الملف غير مدعوم")
    
    # Validate mode
    if mode not in ["DUBBING", "SUBTITLES", "BOTH"]:
        mode = "DUBBING"
    
    path = os.path.join(UPLOAD_FOLDER, f"{task_id}{ext}")
    with open(path, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            f.write(chunk)
    
    size = os.path.getsize(path)
    if size > MAX_SIZE:
        os.remove(path)
        raise HTTPException(400, f"الحد الأقصى {MAX_SIZE//1024//1024}MB")
    
    db_create(task_id, file.filename, mode)
    background_tasks.add_task(process_video, task_id, path, mode, target_lang, file.filename)
    
    return TaskResponse(task_id=task_id, status=Status.PENDING, progress=0, message="جاري المعالجة...", stage="PENDING")

# ============= MAIN PROCESSING (Conditional Logic) =============

async def process_video(task_id: str, video_path: str, mode: str, target_lang: str, filename: str):
    """
    CONDITIONAL PROCESSING PIPELINE:
    
    ALWAYS: Extract Audio -> Transcribe (Groq) -> Translate Text
    
    IF mode == SUBTITLES or BOTH:
        -> Generate SRT -> Upload SRT to Supabase
    
    IF mode == DUBBING or BOTH:
        -> Generate TTS -> Merge Audio -> Upload Video to Supabase
    """
    try:
        print(f"🎬 Processing [{mode}]: {task_id[:8]}")
        base = task_id[:8]
        audio_path = os.path.join(AUDIO_FOLDER, f"{base}.mp3")
        result = {"title": filename, "mode": mode}
        
        # ========== STEP 1: Extract Audio (ALWAYS) ==========
        db_update(task_id, Status.EXTRACTING, 10, "استخراج الصوت...", "EXTRACTING")
        
        if not extract_audio(video_path, audio_path):
            raise Exception("فشل استخراج الصوت")
        
        # ========== STEP 2: Transcribe with Groq (ALWAYS) ==========
        db_update(task_id, Status.TRANSCRIBING, 25, "تحليل الصوت (Groq AI)...", "TRANSCRIBING")
        
        segments, detected_lang = transcribe_groq(audio_path)
        result["detected_language"] = detected_lang
        result["segments_count"] = len(segments)
        
        db_update(task_id, Status.TRANSCRIBING, 40, f"تم استخراج {len(segments)} جملة ✓", "TRANSCRIBING")
        gc.collect()
        
        # ========== STEP 3: Setup Translation (ALWAYS) ==========
        db_update(task_id, Status.TRANSLATING, 45, "تجهيز الترجمة...", "TRANSLATING")
        
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
        
        # ========== STEP 4: CONDITIONAL - Generate Subtitles ==========
        if mode in ["SUBTITLES", "BOTH"]:
            db_update(task_id, Status.GENERATING_SRT, 50, "إنشاء ملف الترجمة...", "GENERATING_SRT")
            
            srt_content = generate_srt(segments, detected_lang, target_lang)
            
            # Save locally first
            srt_filename = f"{base}_{target_lang}.srt"
            srt_local = os.path.join(OUTPUT_FOLDER, srt_filename)
            with open(srt_local, "w", encoding="utf-8") as f:
                f.write(srt_content)
            
            # Upload to Supabase Storage
            srt_url = upload_to_supabase_storage(
                srt_local, 
                "videos", 
                f"subtitles/{srt_filename}",
                "text/plain; charset=utf-8"
            )
            
            if srt_url:
                result["srt_url"] = srt_url
            else:
                result["srt_url"] = f"/output/{srt_filename}"  # Fallback to local
            
            db_update(task_id, Status.GENERATING_SRT, 55, "تم إنشاء ملف الترجمة ✓", "GENERATING_SRT")
        
        # ========== STEP 5: CONDITIONAL - Generate Dubbed Audio ==========
        if mode in ["DUBBING", "BOTH"]:
            db_update(task_id, Status.GENERATING_AUDIO, 55, "توليد الدبلجة...", "GENERATING_AUDIO")
            
            import nest_asyncio
            nest_asyncio.apply()
            
            tts_files = []
            total = len(segments)
            
            for i, seg in enumerate(segments):
                text = seg.get("text", "").strip()
                if not text:
                    continue
                
                if i % 3 == 0:
                    prog = 55 + int((i / total) * 25)
                    db_update(task_id, Status.GENERATING_AUDIO, prog, f"توليد الصوت {i+1}/{total}...", "GENERATING_AUDIO")
                
                translated = translate_text(text, detected_lang, target_lang)
                tts_path = os.path.join(AUDIO_FOLDER, f"tts_{base}_{i}.mp3")
                
                try:
                    asyncio.get_event_loop().run_until_complete(tts_edge(translated, tts_path))
                    tts_files.append(tts_path)
                except Exception as e:
                    print(f"TTS {i}: {e}")
            
            # ========== STEP 6: Merge Audio & Video ==========
            if tts_files:
                db_update(task_id, Status.MERGING, 82, "دمج الصوت...", "MERGING")
                
                merged_audio = os.path.join(AUDIO_FOLDER, f"merged_{base}.mp3")
                
                if merge_audio(tts_files, merged_audio):
                    db_update(task_id, Status.MERGING, 88, "دمج مع الفيديو...", "MERGING")
                    
                    output_name = f"dubbed_{base}.mp4"
                    output_local = os.path.join(OUTPUT_FOLDER, output_name)
                    
                    if combine_video_audio(video_path, merged_audio, output_local):
                        
                        # ========== STEP 7: Upload to Supabase Storage ==========
                        db_update(task_id, Status.UPLOADING, 92, "رفع الفيديو...", "UPLOADING")
                        
                        video_url = upload_to_supabase_storage(
                            output_local,
                            "videos",
                            f"dubbed/{output_name}",
                            "video/mp4"
                        )
                        
                        if video_url:
                            result["dubbed_video_url"] = video_url
                        else:
                            result["dubbed_video_url"] = f"/output/{output_name}"  # Fallback
                        
                        result["dubbed_video_path"] = output_local
                    
                    # Cleanup
                    for f in tts_files:
                        try: os.remove(f)
                        except: pass
                    try: os.remove(merged_audio)
                    except: pass
            
            gc.collect()
        
        # ========== COMPLETE ==========
        db_update(task_id, Status.COMPLETED, 100, "تمت العملية بنجاح! 🎉", "COMPLETED", result)
        print(f"✅ Done [{mode}]: {task_id[:8]}")
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        db_update(task_id, Status.FAILED, 0, f"فشل: {str(e)[:100]}", "FAILED")
    finally:
        gc.collect()

# ============= Status & Download =============

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

@app.get("/download/{task_id}/{file_type}")
def download(task_id: str, file_type: Literal["video", "srt"]):
    task = db_get(task_id)
    if not task:
        raise HTTPException(404, "لم يتم العثور على المهمة")
    
    result = task.get("result") or {}
    
    if file_type == "video":
        path = result.get("dubbed_video_path")
        if path and os.path.exists(path):
            return FileResponse(path, filename="dubbed_video.mp4", media_type="video/mp4")
    elif file_type == "srt":
        url = result.get("srt_url", "")
        if "/output/" in url:
            srt_path = os.path.join(OUTPUT_FOLDER, os.path.basename(url))
            if os.path.exists(srt_path):
                return FileResponse(srt_path, filename="subtitles.srt", media_type="text/plain")
    
    raise HTTPException(404, "الملف غير متوفر")

# ============= Startup =============

@app.on_event("startup")
async def startup():
    print("🚀 Arab Dubbing API v5.0")
    print(f"🧠 Whisper: Groq Cloud")
    print(f"💾 Storage: Supabase (bucket: videos)")
    
    if not GROQ_API_KEY:
        print("⚠️ GROQ_API_KEY missing!")
    if not SUPABASE_URL:
        print("⚠️ SUPABASE_URL missing!")
    
    print("✅ Ready!")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
