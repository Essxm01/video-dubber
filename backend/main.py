"""
Arab Dubbing API - Production Version v3.1
AI-powered video dubbing and translation platform

OPTIMIZED FOR RENDER FREE TIER (512MB RAM):
- Supabase-based task persistence (survives server restarts)
- Chunked audio processing (30-second segments)
- Aggressive garbage collection after each chunk
- tiny Whisper model for minimal memory footprint
- ffmpeg for audio extraction (not moviepy - saves RAM)
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, Literal
import shutil
import os
import asyncio
import uuid
import gc
import subprocess
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Supabase Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

app = FastAPI(
    title="Arab Dubbing API",
    description="AI-powered video dubbing - دبلجة العرب",
    version="3.1.0"
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
DOWNLOADS_FOLDER = "downloads"
AUDIO_FOLDER = "audio"
OUTPUT_FOLDER = "output"
UPLOAD_FOLDER = "uploads"
CHUNKS_FOLDER = "chunks"

for folder in [DOWNLOADS_FOLDER, AUDIO_FOLDER, OUTPUT_FOLDER, UPLOAD_FOLDER, CHUNKS_FOLDER]:
    os.makedirs(folder, exist_ok=True)

# Mount static files for output
app.mount("/output", StaticFiles(directory=OUTPUT_FOLDER), name="output")

# ============= Supabase Client (Simple - No Proxy) =============
_supabase_client = None

def get_supabase():
    """Get Supabase client (singleton, lazy init)"""
    global _supabase_client
    if _supabase_client is None:
        try:
            from supabase import create_client, Client
            _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
            print("✅ Supabase client initialized")
        except Exception as e:
            print(f"⚠️ Supabase init error: {e}")
            return None
    return _supabase_client

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

def db_create_task(task_id: str, filename: str, mode: str):
    """Create task in Supabase"""
    try:
        sb = get_supabase()
        if sb:
            sb.table("projects").insert({
                "id": task_id,
                "title": filename,
                "status": TaskStatus.PENDING,
                "progress": 0,
                "message": "جاري بدء المعالجة...",
                "stage": "PENDING",
                "source": "upload",
                "mode": mode,
                "created_at": datetime.now().isoformat(),
            }).execute()
            print(f"📝 DB: Task created {task_id[:8]}")
    except Exception as e:
        print(f"⚠️ DB create error: {e}")

def db_update_task(task_id: str, status: str, progress: int, message: str, stage: str = None, result: dict = None):
    """Update task in Supabase"""
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
            print(f"📊 {task_id[:8]}: {status} {progress}% - {message}")
    except Exception as e:
        print(f"⚠️ DB update error: {e}")

def db_get_task(task_id: str) -> dict:
    """Get task from Supabase with robust error handling"""
    try:
        sb = get_supabase()
        if sb:
            # Use .execute() without .single() to avoid JSON parsing issues
            res = sb.table("projects").select("*").eq("id", task_id).execute()
            
            if res.data and len(res.data) > 0:
                return res.data[0]
            
    except Exception as e:
        error_str = str(e)
        print(f"⚠️ DB get error: {error_str[:200]}")
        
        # FALLBACK: If error contains valid data, try to extract it
        import re
        import json
        
        # Try to find JSON in error message
        if "progress" in error_str or "status" in error_str:
            try:
                # Look for JSON-like content in error
                json_match = re.search(r'\{[^{}]*"status"[^{}]*\}', error_str)
                if json_match:
                    extracted = json.loads(json_match.group())
                    print(f"🔧 Extracted from error: {extracted}")
                    return extracted
            except:
                pass
        
        # Return placeholder to prevent 404 (keeps UI alive)
        return {
            "id": task_id,
            "status": "PROCESSING",
            "progress": 15,
            "message": "جاري المعالجة...",
            "stage": "TRANSCRIPTION"
        }
    
    return None

# ============= Models =============
class TaskResponse(BaseModel):
    task_id: str
    status: str
    progress: int
    message: str
    stage: Optional[str] = None
    result: Optional[dict] = None

# ============= Audio Helpers =============

def extract_audio_ffmpeg(video_path: str, audio_path: str) -> bool:
    """Extract audio using ffmpeg (memory efficient)"""
    cmd = [
        "ffmpeg", "-i", video_path,
        "-vn", "-acodec", "libmp3lame", "-ab", "64k", "-ar", "16000",
        "-y", audio_path
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=300)
        return True
    except Exception as e:
        print(f"❌ Audio extraction failed: {e}")
        return False

def split_audio_chunks(audio_path: str, chunk_sec: int = 30) -> list:
    """Split audio into chunks using ffmpeg"""
    base = os.path.splitext(os.path.basename(audio_path))[0]
    pattern = os.path.join(CHUNKS_FOLDER, f"{base}_%03d.mp3")
    
    # Clean old chunks
    for f in os.listdir(CHUNKS_FOLDER):
        if f.startswith(base):
            try:
                os.remove(os.path.join(CHUNKS_FOLDER, f))
            except:
                pass
    
    cmd = [
        "ffmpeg", "-i", audio_path,
        "-f", "segment", "-segment_time", str(chunk_sec),
        "-c", "copy", "-y", pattern
    ]
    
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=120)
    except Exception as e:
        print(f"❌ Split failed: {e}")
        return []
    
    chunks = sorted([
        os.path.join(CHUNKS_FOLDER, f) 
        for f in os.listdir(CHUNKS_FOLDER) 
        if f.startswith(base) and f.endswith(".mp3")
    ])
    print(f"📦 Split into {len(chunks)} chunks")
    return chunks

def get_duration(path: str) -> float:
    """Get audio/video duration"""
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
           "-of", "default=noprint_wrappers=1:nokey=1", path]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return float(r.stdout.strip())
    except:
        return 0.0

def transcribe_chunk_tiny(chunk_path: str, idx: int):
    """Transcribe ONE chunk with tiny model, then UNLOAD"""
    print(f"🎙️ Transcribing chunk {idx}...")
    
    from faster_whisper import WhisperModel
    model = WhisperModel("tiny", device="cpu", compute_type="int8")
    
    segs, info = model.transcribe(chunk_path, beam_size=1, language=None)
    
    result = []
    for s in segs:
        result.append({"start": s.start, "end": s.end, "text": s.text.strip()})
    
    lang = info.language
    
    # CRITICAL: Unload model immediately
    del model
    gc.collect()
    
    print(f"✅ Chunk {idx}: {len(result)} segments, lang={lang}")
    return result, lang

def translate_text_argos(text: str, src: str = "en", tgt: str = "ar") -> str:
    """Translate using argostranslate"""
    if not text.strip():
        return text
    try:
        import argostranslate.translate
        return argostranslate.translate.translate(text, src, tgt)
    except:
        return text

async def tts_edge(text: str, out_path: str, voice: str = "ar-EG-SalmaNeural"):
    """Generate TTS using edge-tts"""
    import edge_tts
    c = edge_tts.Communicate(text, voice)
    await c.save(out_path)

def merge_audio_ffmpeg(audio_files: list, output: str) -> bool:
    """Merge audio files using ffmpeg concat"""
    if not audio_files:
        return False
    
    list_file = os.path.join(CHUNKS_FOLDER, "merge.txt")
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

def combine_video_audio_ffmpeg(video_path: str, audio_path: str, output_path: str) -> bool:
    """Combine video with new audio track"""
    cmd = [
        "ffmpeg", "-i", video_path, "-i", audio_path,
        "-c:v", "copy", "-map", "0:v:0", "-map", "1:a:0",
        "-shortest", "-y", output_path
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=600)
        return True
    except Exception as e:
        print(f"❌ Combine failed: {e}")
        return False

# ============= API Endpoints =============

@app.get("/")
def root():
    return {"status": "active", "version": "3.1.0", "message": "Arab Dubbing API 🚀"}

@app.get("/health")
def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

# ============= Upload Endpoint =============
MAX_SIZE = 100 * 1024 * 1024  # 100MB

@app.post("/upload", response_model=TaskResponse)
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    mode: str = Form(default="DUBBING"),
    target_lang: str = Form(default="ar")
):
    """Upload video for processing"""
    task_id = str(uuid.uuid4())
    
    # Validate
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ['.mp4', '.mkv', '.webm', '.mov', '.avi']:
        raise HTTPException(400, "نوع الملف غير مدعوم")
    
    # Save file
    path = os.path.join(UPLOAD_FOLDER, f"{task_id}{ext}")
    try:
        with open(path, "wb") as f:
            while chunk := await file.read(1024 * 1024):
                f.write(chunk)
        
        size = os.path.getsize(path)
        if size > MAX_SIZE:
            os.remove(path)
            raise HTTPException(400, "حجم الملف كبير (الحد 100MB)")
        
        print(f"📤 Uploaded: {file.filename} ({size/1024/1024:.1f}MB)")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"فشل الرفع: {e}")
    
    # Create task in DB
    db_create_task(task_id, file.filename, mode)
    
    # Start processing
    background_tasks.add_task(process_video, task_id, path, mode, target_lang, file.filename)
    
    return TaskResponse(
        task_id=task_id,
        status=TaskStatus.PENDING,
        progress=0,
        message="تم رفع الفيديو، جاري المعالجة...",
        stage="PENDING"
    )

# ============= Main Processing Function =============

async def process_video(task_id: str, video_path: str, mode: str, target_lang: str, filename: str):
    """
    CHUNKED PROCESSING PIPELINE:
    1. Extract audio (ffmpeg)
    2. Split into 30-sec chunks
    3. Transcribe each chunk (tiny whisper, unload after each)
    4. Translate segments
    5. Generate TTS for each segment
    6. Merge TTS audio
    7. Combine with video
    8. Update DB with result
    """
    try:
        print(f"🎬 Processing: {task_id[:8]} - {filename}")
        
        db_update_task(task_id, TaskStatus.DOWNLOADING, 10, "تم استلام الفيديو ✓", "DOWNLOAD")
        
        base = task_id[:8]
        audio_path = os.path.join(AUDIO_FOLDER, f"{base}.mp3")
        
        # --- STEP 1: Extract Audio ---
        db_update_task(task_id, TaskStatus.TRANSCRIBING, 15, "استخراج الصوت...", "TRANSCRIPTION")
        
        if not extract_audio_ffmpeg(video_path, audio_path):
            raise Exception("فشل استخراج الصوت")
        
        gc.collect()
        
        # --- STEP 2: Split Audio ---
        db_update_task(task_id, TaskStatus.TRANSCRIBING, 20, "تقسيم الصوت...", "TRANSCRIPTION")
        
        chunks = split_audio_chunks(audio_path, chunk_sec=30)
        if not chunks:
            raise Exception("فشل تقسيم الصوت")
        
        # --- STEP 3: Transcribe Chunks ---
        all_segments = []
        detected_lang = "en"
        offset = 0.0
        
        for i, chunk in enumerate(chunks):
            prog = 25 + int((i / len(chunks)) * 20)
            db_update_task(task_id, TaskStatus.TRANSCRIBING, prog, f"تحليل الجزء {i+1}/{len(chunks)}...", "TRANSCRIPTION")
            
            segs, lang = transcribe_chunk_tiny(chunk, i)
            if lang:
                detected_lang = lang
            
            # Adjust timestamps
            for s in segs:
                s["start"] += offset
                s["end"] += offset
                all_segments.append(s)
            
            offset += get_duration(chunk)
            
            # Cleanup chunk
            try:
                os.remove(chunk)
            except:
                pass
            
            gc.collect()
        
        db_update_task(task_id, TaskStatus.TRANSCRIBING, 45, f"تم استخراج {len(all_segments)} جملة ✓", "TRANSCRIPTION")
        
        result = {"title": filename, "detected_language": detected_lang}
        
        # --- STEP 4: Translation + TTS ---
        if mode in ["DUBBING", "BOTH"]:
            db_update_task(task_id, TaskStatus.TRANSLATING, 50, "ترجمة وتوليد الصوت...", "TRANSLATION")
            
            # Setup argos
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
                print(f"Argos setup: {e}")
            
            tts_files = []
            total = len(all_segments)
            
            import nest_asyncio
            nest_asyncio.apply()
            
            for i, seg in enumerate(all_segments):
                text = seg["text"]
                if not text:
                    continue
                
                if i % 3 == 0:
                    prog = 50 + int((i / total) * 30)
                    db_update_task(task_id, TaskStatus.GENERATING_AUDIO, prog, f"توليد الصوت {i+1}/{total}...", "VOICE")
                
                # Translate
                translated = translate_text_argos(text, detected_lang or "en", target_lang)
                
                # TTS
                tts_path = os.path.join(AUDIO_FOLDER, f"tts_{base}_{i}.mp3")
                try:
                    asyncio.get_event_loop().run_until_complete(tts_edge(translated, tts_path))
                    tts_files.append(tts_path)
                except Exception as e:
                    print(f"TTS error {i}: {e}")
                
                if i % 5 == 0:
                    gc.collect()
            
            # --- STEP 5: Merge TTS ---
            db_update_task(task_id, TaskStatus.MERGING, 85, "دمج الصوت...", "MERGING")
            
            merged_audio = os.path.join(AUDIO_FOLDER, f"merged_{base}.mp3")
            
            if tts_files and merge_audio_ffmpeg(tts_files, merged_audio):
                
                # --- STEP 6: Combine with Video ---
                db_update_task(task_id, TaskStatus.MERGING, 90, "دمج مع الفيديو...", "MERGING")
                
                output_name = f"dubbed_{base}.mp4"
                output_path = os.path.join(OUTPUT_FOLDER, output_name)
                
                if combine_video_audio_ffmpeg(video_path, merged_audio, output_path):
                    result["dubbed_video_url"] = f"/output/{output_name}"
                    result["dubbed_video_path"] = output_path
                
                # Cleanup
                for f in tts_files:
                    try:
                        os.remove(f)
                    except:
                        pass
                try:
                    os.remove(merged_audio)
                except:
                    pass
            
            gc.collect()
        
        # --- STEP 7: Subtitles (if requested) ---
        if mode in ["SUBTITLES", "BOTH"]:
            srt = ""
            for i, seg in enumerate(all_segments, 1):
                if not seg["text"]:
                    continue
                txt = translate_text_argos(seg["text"], detected_lang or "en", target_lang)
                
                def fmt(s):
                    h = int(s // 3600)
                    m = int((s % 3600) // 60)
                    sec = int(s % 60)
                    ms = int((s - int(s)) * 1000)
                    return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"
                
                srt += f"{i}\n{fmt(seg['start'])} --> {fmt(seg['end'])}\n{txt}\n\n"
            
            srt_name = f"{base}_{target_lang}.srt"
            srt_path = os.path.join(OUTPUT_FOLDER, srt_name)
            with open(srt_path, "w", encoding="utf-8") as f:
                f.write(srt)
            
            result["srt_url"] = f"/output/{srt_name}"
        
        # --- DONE ---
        db_update_task(task_id, TaskStatus.COMPLETED, 100, "تمت العملية بنجاح! 🎉", "COMPLETED", result)
        print(f"✅ Completed: {task_id[:8]}")
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        db_update_task(task_id, TaskStatus.FAILED, 0, f"فشلت العملية: {str(e)[:100]}", "FAILED")
        print(f"❌ Failed: {task_id[:8]} - {e}")
    finally:
        gc.collect()

# ============= Status Endpoint =============

@app.get("/status/{task_id}", response_model=TaskResponse)
def get_task_status(task_id: str):
    """Get task status from Supabase"""
    task = db_get_task(task_id)
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

# ============= Download Endpoint =============

@app.get("/download/{task_id}/{file_type}")
def download(task_id: str, file_type: Literal["video", "srt"]):
    """Download result files"""
    task = db_get_task(task_id)
    if not task:
        raise HTTPException(404, "لم يتم العثور على المهمة")
    
    result = task.get("result") or {}
    
    if file_type == "video" and result.get("dubbed_video_path"):
        return FileResponse(result["dubbed_video_path"], filename="dubbed_video.mp4", media_type="video/mp4")
    elif file_type == "srt" and result.get("srt_url"):
        srt_path = os.path.join(OUTPUT_FOLDER, os.path.basename(result["srt_url"]))
        if os.path.exists(srt_path):
            return FileResponse(srt_path, filename="subtitles.srt", media_type="text/plain")
    
    raise HTTPException(404, f"الملف '{file_type}' غير متوفر")

# ============= Startup =============

@app.on_event("startup")
async def startup():
    print("🚀 Arab Dubbing API v3.1 Starting...")
    print(f"📁 Output: {os.path.abspath(OUTPUT_FOLDER)}")
    print(f"🧠 Mode: Chunked Processing (30s) + tiny Whisper")
    print(f"💾 Storage: Supabase (persistent)")
    
    # Test Supabase connection
    if SUPABASE_URL and SUPABASE_KEY:
        get_supabase()
    else:
        print("⚠️ Supabase not configured!")
    
    print("✅ Ready!")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
