"""
Arab Dubbing API - Production Version
AI-powered video dubbing and translation platform

OPTIMIZED FOR RENDER FREE TIER:
- Lazy loading for AI models (no global initialization)
- CORS configured for all origins
- Proper health check endpoint
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, Dict, Literal
import shutil
import uvicorn
import yt_dlp
import os
import asyncio
import uuid
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = FastAPI(
    title="Arab Dubbing API",
    description="AI-powered video dubbing and translation platform - دبلجة العرب",
    version="2.0.0"
)

# ============= CORS - ALLOW ALL ORIGINS =============
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

for folder in [DOWNLOADS_FOLDER, AUDIO_FOLDER, OUTPUT_FOLDER]:
    os.makedirs(folder, exist_ok=True)

# Mount static files
app.mount("/output", StaticFiles(directory=OUTPUT_FOLDER), name="output")

# ============= Task Management =============
tasks: Dict[str, dict] = {}

# ============= AI Models - LAZY LOADING =============
# IMPORTANT: Models are NOT loaded globally to save memory on Free Tier
# They will be loaded only when needed inside the processing function

class TaskStatus:
    PENDING = "PENDING"
    DOWNLOADING = "DOWNLOADING"
    TRANSCRIBING = "TRANSCRIBING"
    TRANSLATING = "TRANSLATING"
    GENERATING_AUDIO = "GENERATING_AUDIO"
    GENERATING_SUBTITLES = "GENERATING_SUBTITLES"
    MERGING = "MERGING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

# ============= Models =============
class VideoRequest(BaseModel):
    url: str
    target_lang: str = "ar"
    mode: Literal["DUBBING", "SUBTITLES", "BOTH"] = "DUBBING"

class TextRequest(BaseModel):
    text: str
    target_lang: str = "ar"

class TTSRequest(BaseModel):
    text: str
    lang: str = "ar"

class TaskResponse(BaseModel):
    task_id: str
    status: str
    progress: int
    message: str
    stage: Optional[str] = None
    result: Optional[dict] = None

# ============= Helper Functions =============
def update_task(task_id: str, status: str, progress: int, message: str, stage: str = None, result: dict = None):
    """Update task status in memory"""
    if task_id in tasks:
        tasks[task_id].update({
            "status": status,
            "progress": progress,
            "message": message,
            "stage": stage or status,
            "updated_at": datetime.now().isoformat()
        })
        if result:
            tasks[task_id]["result"] = result
        print(f"📊 Task {task_id[:8]}... - {status}: {progress}% - {message}")

def _download_video(url: str, task_id: str = None):
    """
    Download video from YouTube using yt-dlp with ADVANCED bot-bypass techniques.
    
    Strategies:
    1. Android client (most stable for servers)
    2. Audio-only fallback (then convert)
    3. Force IPv4 to bypass IPv6 blocks
    """
    if task_id:
        update_task(task_id, TaskStatus.DOWNLOADING, 5, "جاري تحميل الفيديو من يوتيوب...", "DOWNLOAD")
    
    # Common robust headers to mimic real browser
    BROWSER_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 13; SM-S908B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.210 Mobile Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
    }
    
    # ============= STRATEGY 1: Android Client (Primary) =============
    primary_opts = {
        "outtmpl": f"{DOWNLOADS_FOLDER}/%(id)s.%(ext)s",
        "format": "best[height<=720][ext=mp4]/best[height<=720]/best",
        "overwrites": True,
        "quiet": False,
        "no_warnings": False,
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web"],
                "player_skip": ["configs", "js"],
            }
        },
        "http_headers": BROWSER_HEADERS,
        # Force IPv4 to bypass potential IPv6 blocks on Render
        "source_address": "0.0.0.0",
        "retries": 10,
        "fragment_retries": 10,
        "file_access_retries": 5,
        "socket_timeout": 60,
        "extractor_retries": 5,
        # Bypass age restrictions
        "age_limit": None,
        # Don't check SSL (sometimes helps)
        "nocheckcertificate": True,
    }
    
    # ============= STRATEGY 2: Audio-Only Fallback =============
    audio_fallback_opts = {
        "outtmpl": f"{DOWNLOADS_FOLDER}/%(id)s.%(ext)s",
        "format": "bestaudio[ext=m4a]/bestaudio/best",
        "overwrites": True,
        "quiet": False,
        "extractor_args": {
            "youtube": {
                "player_client": ["android"],
            }
        },
        "http_headers": BROWSER_HEADERS,
        "source_address": "0.0.0.0",
        "retries": 5,
        "socket_timeout": 60,
        "nocheckcertificate": True,
        # Post-process to mp4 if needed
        "postprocessors": [{
            "key": "FFmpegVideoConvertor",
            "preferedformat": "mp4",
        }] if False else [],  # Disabled for now
    }
    
    # ============= STRATEGY 3: Minimal Options =============
    minimal_opts = {
        "outtmpl": f"{DOWNLOADS_FOLDER}/%(id)s.%(ext)s",
        "format": "worst[ext=mp4]/worst",  # Get smallest file
        "overwrites": True,
        "quiet": False,
        "source_address": "0.0.0.0",
        "retries": 3,
        "socket_timeout": 30,
        "nocheckcertificate": True,
    }
    
    strategies = [
        {"name": "Android Client (Primary)", "opts": primary_opts},
        {"name": "Audio Fallback", "opts": audio_fallback_opts},
        {"name": "Minimal Config", "opts": minimal_opts},
    ]
    
    last_error = None
    
    for i, strategy in enumerate(strategies):
        try:
            print(f"\n{'='*50}")
            print(f"🔄 [{i+1}/{len(strategies)}] Trying: {strategy['name']}")
            print(f"{'='*50}")
            
            if task_id:
                update_task(task_id, TaskStatus.DOWNLOADING, 5 + (i * 3), 
                           f"محاولة التحميل ({strategy['name']})...", "DOWNLOAD")
            
            with yt_dlp.YoutubeDL(strategy["opts"]) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                
                # Find the actual file
                base = os.path.splitext(filename)[0]
                for ext in ['.mp4', '.webm', '.mkv', '.m4a', '.mp3']:
                    if os.path.exists(base + ext):
                        filename = base + ext
                        break
                
                if not os.path.exists(filename):
                    # Try to find any file with the video ID
                    video_id = info.get('id', '')
                    for f in os.listdir(DOWNLOADS_FOLDER):
                        if video_id in f:
                            filename = os.path.join(DOWNLOADS_FOLDER, f)
                            break
                
                if os.path.exists(filename):
                    if task_id:
                        update_task(task_id, TaskStatus.DOWNLOADING, 15, 
                                   f"✅ تم التحميل بنجاح ({strategy['name']})", "DOWNLOAD")
                    
                    print(f"✅ SUCCESS with strategy: {strategy['name']}")
                    print(f"📁 File: {filename}")
                    return filename, info.get("title", "Unknown"), info.get("thumbnail", "")
                else:
                    raise Exception(f"File not found after download: {filename}")
                    
        except Exception as e:
            last_error = str(e)
            print(f"❌ Strategy '{strategy['name']}' FAILED:")
            print(f"   Error: {last_error[:150]}")
            continue
    
    # ============= ALL STRATEGIES FAILED =============
    print(f"\n{'='*50}")
    print(f"❌ ALL {len(strategies)} STRATEGIES FAILED")
    print(f"Last error: {last_error}")
    print(f"{'='*50}\n")
    
    # Provide user-friendly error message
    error_lower = str(last_error).lower()
    if any(x in error_lower for x in ["sign in", "bot", "confirm", "verify"]):
        raise HTTPException(
            status_code=500, 
            detail="⚠️ يوتيوب يحظر هذا الفيديو من السيرفر. جرب فيديو آخر (قديم أو من قناة صغيرة)."
        )
    elif "unavailable" in error_lower or "private" in error_lower:
        raise HTTPException(status_code=500, detail="❌ هذا الفيديو خاص أو غير متاح.")
    elif "age" in error_lower:
        raise HTTPException(status_code=500, detail="🔞 هذا الفيديو للكبار فقط ويتطلب تسجيل دخول.")
    elif "copyright" in error_lower:
        raise HTTPException(status_code=500, detail="⚖️ هذا الفيديو محمي بحقوق الطبع والنشر.")
    else:
        raise HTTPException(status_code=500, detail=f"❌ فشل التحميل: {str(last_error)[:100]}")

# ============= LAZY LOADING FUNCTIONS =============
def load_whisper_model():
    """Load faster-whisper model (LAZY - only when needed)"""
    print("🎙️ Loading faster-whisper model (base)...")
    from faster_whisper import WhisperModel
    model = WhisperModel("base", device="cpu", compute_type="int8")
    print("✅ Whisper model loaded")
    return model

def load_argos_translator():
    """Load argostranslate (LAZY - only when needed)"""
    print("📦 Loading Argos Translate...")
    import argostranslate.package
    import argostranslate.translate
    
    try:
        argostranslate.package.update_package_index()
        available_packages = argostranslate.package.get_available_packages()
        
        package_to_install = next(
            (pkg for pkg in available_packages 
             if pkg.from_code == "en" and pkg.to_code == "ar"),
            None
        )
        
        if package_to_install:
            installed = argostranslate.package.get_installed_packages()
            already_installed = any(
                pkg.from_code == "en" and pkg.to_code == "ar" 
                for pkg in installed
            )
            
            if not already_installed:
                print("📥 Installing en->ar translation package...")
                argostranslate.package.install_from_path(package_to_install.download())
        
        print("✅ Argos Translate ready")
    except Exception as e:
        print(f"⚠️ Argos setup warning: {e}")
    
    return argostranslate.translate

def translate_text_lazy(text: str, translator_module, source_lang: str = "en", target_lang: str = "ar") -> str:
    """Translate text using loaded argostranslate module"""
    try:
        return translator_module.translate(text, source_lang, target_lang)
    except Exception as e:
        print(f"⚠️ Translation error: {e}")
        return text

async def generate_tts_lazy(text: str, output_path: str, voice: str = "ar-EG-SalmaNeural"):
    """Generate TTS using edge-tts (LAZY import)"""
    import edge_tts
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_path)

# ============= API Endpoints =============

@app.get("/")
def root():
    """Health check - Root endpoint for Render"""
    return {
        "status": "active",
        "message": "Arab Dubbing API is running 🚀",
        "version": "2.0.0"
    }

@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "whisper_model": os.getenv("WHISPER_MODEL", "base"),
        "active_tasks": len([t for t in tasks.values() if t.get("status") not in ["COMPLETED", "FAILED"]])
    }

@app.post("/process", response_model=TaskResponse)
async def start_processing(req: VideoRequest, background_tasks: BackgroundTasks):
    """Start video processing job"""
    task_id = str(uuid.uuid4())
    
    # Validate YouTube URL
    if not any(domain in req.url for domain in ['youtube.com', 'youtu.be']):
        raise HTTPException(status_code=400, detail="الرجاء إدخال رابط يوتيوب صالح")
    
    # Initialize task
    tasks[task_id] = {
        "task_id": task_id,
        "status": TaskStatus.PENDING,
        "progress": 0,
        "message": "تم استلام الطلب، جاري بدء المعالجة...",
        "stage": "PENDING",
        "url": req.url,
        "mode": req.mode,
        "target_lang": req.target_lang,
        "created_at": datetime.now().isoformat(),
        "result": None
    }
    
    print(f"🚀 New task: {task_id} - Mode: {req.mode}")
    
    # Start background processing
    background_tasks.add_task(process_video_task, task_id, req)
    
    return TaskResponse(
        task_id=task_id,
        status=TaskStatus.PENDING,
        progress=0,
        message="تم بدء المعالجة",
        stage="PENDING"
    )

async def process_video_task(task_id: str, req: VideoRequest):
    """Background task for video processing pipeline with LAZY model loading"""
    try:
        print(f"📹 Starting processing for task: {task_id[:8]}...")
        
        # STEP 1: Download Video
        video_path, title, thumbnail = _download_video(req.url, task_id)
        update_task(task_id, TaskStatus.DOWNLOADING, 20, "تم تحميل الفيديو بنجاح ✓", "DOWNLOAD")
        
        # STEP 2: Extract Audio (using moviepy - lazy import)
        update_task(task_id, TaskStatus.TRANSCRIBING, 22, "جاري استخراج الصوت...", "TRANSCRIPTION")
        from moviepy.editor import VideoFileClip, AudioFileClip, CompositeAudioClip
        import moviepy.audio.fx.all as afx
        
        base_name = os.path.basename(video_path).split('.')[0]
        audio_path = os.path.join(AUDIO_FOLDER, f"{base_name}.mp3")
        
        clip = VideoFileClip(video_path)
        if clip.audio is None:
            raise ValueError("لا يوجد صوت في هذا الفيديو")
        clip.audio.write_audiofile(audio_path, verbose=False, logger=None)
        clip.close()
        
        # STEP 3: LAZY LOAD Whisper and Transcribe
        update_task(task_id, TaskStatus.TRANSCRIBING, 25, "تحليل الصوت باستخدام Whisper AI...", "TRANSCRIPTION")
        whisper_model = load_whisper_model()
        
        segments_gen, info = whisper_model.transcribe(audio_path, beam_size=5, language=None)
        
        segments = []
        full_text = ""
        for segment in segments_gen:
            segments.append({
                "start": segment.start,
                "end": segment.end,
                "text": segment.text
            })
            full_text += segment.text + " "
        
        detected_lang = info.language
        update_task(task_id, TaskStatus.TRANSCRIBING, 45, f"تم استخراج النص (اللغة: {detected_lang}) ✓", "TRANSCRIPTION")
        
        # Free memory
        del whisper_model
        
        result = {
            "title": title,
            "thumbnail": thumbnail,
            "original_text": full_text[:500] + "..." if len(full_text) > 500 else full_text,
            "video_path": video_path,
            "detected_language": detected_lang
        }
        
        # STEP 4: Process based on mode
        
        # --- SUBTITLES MODE ---
        if req.mode in ["SUBTITLES", "BOTH"]:
            update_task(task_id, TaskStatus.GENERATING_SUBTITLES, 50, "إنشاء ملف الترجمة...", "SUBTITLE_GENERATION")
            
            # LAZY LOAD Argos
            translator = load_argos_translator()
            
            srt_content = ""
            for i, segment in enumerate(segments, 1):
                start_time = segment['start']
                end_time = segment['end']
                text = segment['text'].strip()
                
                if not text:
                    continue
                
                translated_text = translate_text_lazy(text, translator, "en", req.target_lang)
                
                def format_time(seconds):
                    hours = int(seconds // 3600)
                    minutes = int((seconds % 3600) // 60)
                    secs = int(seconds % 60)
                    millis = int((seconds - int(seconds)) * 1000)
                    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
                
                srt_content += f"{i}\n"
                srt_content += f"{format_time(start_time)} --> {format_time(end_time)}\n"
                srt_content += f"{translated_text}\n\n"
            
            srt_filename = f"{base_name}_{req.target_lang}.srt"
            srt_path = os.path.join(OUTPUT_FOLDER, srt_filename)
            
            with open(srt_path, 'w', encoding='utf-8') as f:
                f.write(srt_content)
            
            result["srt_path"] = srt_path
            result["srt_url"] = f"/output/{srt_filename}"
            update_task(task_id, TaskStatus.GENERATING_SUBTITLES, 60, "تم إنشاء ملف الترجمة ✓", "SUBTITLE_GENERATION")
        
        # --- DUBBING MODE ---
        if req.mode in ["DUBBING", "BOTH"]:
            update_task(task_id, TaskStatus.TRANSLATING, 55, "ترجمة النص إلى العربية...", "TRANSLATION")
            
            # LAZY LOAD Argos (if not already loaded)
            try:
                translator
            except NameError:
                translator = load_argos_translator()
            
            audio_clips = []
            translated_texts = []
            total_segments = len(segments)
            
            tts_voice = "ar-EG-SalmaNeural"
            
            for i, segment in enumerate(segments):
                start_time = segment['start']
                end_time = segment['end']
                original_text = segment['text'].strip()
                
                if not original_text:
                    continue
                
                translated_text = translate_text_lazy(original_text, translator, detected_lang or "en", req.target_lang)
                translated_texts.append(translated_text)
                
                update_task(task_id, TaskStatus.GENERATING_AUDIO, 
                           60 + int((i / total_segments) * 25), 
                           f"توليد الدبلجة الصوتية ({i+1}/{total_segments})...", 
                           "VOICE_GENERATION")
                
                try:
                    segment_audio_name = f"seg_{task_id[:8]}_{i}.mp3"
                    segment_audio_path = os.path.join(AUDIO_FOLDER, segment_audio_name)
                    
                    # LAZY TTS generation
                    import nest_asyncio
                    nest_asyncio.apply()
                    asyncio.get_event_loop().run_until_complete(
                        generate_tts_lazy(translated_text, segment_audio_path, tts_voice)
                    )
                    
                    audio_clip = AudioFileClip(segment_audio_path)
                    
                    segment_duration = end_time - start_time
                    current_duration = audio_clip.duration
                    
                    if current_duration > segment_duration and segment_duration > 0:
                        speed_factor = min(current_duration / segment_duration, 1.8)
                        audio_clip = audio_clip.fx(afx.speedx, speed_factor)
                    
                    audio_clip = audio_clip.set_start(start_time)
                    audio_clips.append(audio_clip)
                    
                except Exception as e:
                    print(f"⚠️ TTS error for segment {i}: {e}")
                    continue
            
            # STEP 5: Merge Audio with Video
            if audio_clips:
                update_task(task_id, TaskStatus.MERGING, 88, "دمج ومزامنة الصوت مع الفيديو...", "SYNCING")
                
                original_video = VideoFileClip(video_path)
                final_audio = CompositeAudioClip(audio_clips)
                final_audio = final_audio.set_duration(original_video.duration)
                final_video = original_video.set_audio(final_audio)
                
                output_filename = f"dubbed_{os.path.basename(video_path)}"
                output_video_path = os.path.join(OUTPUT_FOLDER, output_filename)
                
                final_video.write_videofile(
                    output_video_path, 
                    codec="libx264", 
                    audio_codec="aac",
                    verbose=False, 
                    logger=None,
                    threads=2  # Reduced for Free Tier
                )
                
                original_video.close()
                final_audio.close()
                
                result["dubbed_video_path"] = output_video_path
                result["dubbed_video_url"] = f"/output/{output_filename}"
                result["translated_text"] = " ".join(translated_texts[:10]) + "..." if len(translated_texts) > 10 else " ".join(translated_texts)
                
                update_task(task_id, TaskStatus.MERGING, 95, "تم دمج الصوت مع الفيديو ✓", "SYNCING")
        
        # COMPLETE
        update_task(task_id, TaskStatus.COMPLETED, 100, "تمت العملية بنجاح! 🎉", "FINALIZING", result)
        print(f"✅ Task completed: {task_id[:8]}")
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        error_msg = f"فشلت العملية: {str(e)}"
        update_task(task_id, TaskStatus.FAILED, 0, error_msg, "FAILED")
        print(f"❌ Task failed: {task_id[:8]} - {error_msg}")

@app.get("/status/{task_id}", response_model=TaskResponse)
def get_task_status(task_id: str):
    """Get processing status for a task"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="لم يتم العثور على المهمة")
    
    task = tasks[task_id]
    return TaskResponse(
        task_id=task_id,
        status=task["status"],
        progress=task["progress"],
        message=task["message"],
        stage=task.get("stage"),
        result=task.get("result")
    )

@app.get("/download/{task_id}/{file_type}")
def download_file(task_id: str, file_type: Literal["video", "audio", "srt"]):
    """Download processed file"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="لم يتم العثور على المهمة")
    
    task = tasks[task_id]
    result = task.get("result", {})
    
    if file_type == "video" and "dubbed_video_path" in result:
        return FileResponse(
            result["dubbed_video_path"], 
            filename="dubbed_video.mp4",
            media_type="video/mp4"
        )
    elif file_type == "srt" and "srt_path" in result:
        return FileResponse(
            result["srt_path"], 
            filename=f"subtitles_{task.get('target_lang', 'ar')}.srt",
            media_type="text/plain; charset=utf-8"
        )
    else:
        raise HTTPException(status_code=404, detail=f"الملف '{file_type}' غير متوفر")

# ============= DIRECT VIDEO UPLOAD ENDPOINT =============
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB max

@app.post("/upload", response_model=TaskResponse)
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    mode: str = Form(default="DUBBING"),
    target_lang: str = Form(default="ar")
):
    """
    Upload video file directly for processing (bypasses YouTube restrictions).
    Supported formats: MP4, MKV, WebM, MOV, AVI
    Max file size: 500MB
    """
    task_id = str(uuid.uuid4())
    
    # Validate file type
    allowed_extensions = ['.mp4', '.mkv', '.webm', '.mov', '.avi', '.m4v']
    file_ext = os.path.splitext(file.filename or "")[1].lower()
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400, 
            detail=f"❌ نوع الملف غير مدعوم. الأنواع المدعومة: {', '.join(allowed_extensions)}"
        )
    
    # Validate mode
    if mode not in ["DUBBING", "SUBTITLES", "BOTH"]:
        mode = "DUBBING"
    
    # Save uploaded file
    upload_filename = f"{task_id}{file_ext}"
    upload_path = os.path.join(UPLOAD_FOLDER, upload_filename)
    
    try:
        # Stream file to disk (memory efficient)
        with open(upload_path, "wb") as buffer:
            while True:
                chunk = await file.read(1024 * 1024)  # 1MB chunks
                if not chunk:
                    break
                buffer.write(chunk)
        
        # Check file size
        file_size = os.path.getsize(upload_path)
        if file_size > MAX_FILE_SIZE:
            os.remove(upload_path)
            raise HTTPException(
                status_code=400,
                detail=f"❌ حجم الملف كبير جداً. الحد الأقصى: 500MB"
            )
        
        print(f"📤 File uploaded: {upload_filename} ({file_size / 1024 / 1024:.1f} MB)")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"❌ فشل رفع الملف: {str(e)}")
    
    # Initialize task
    tasks[task_id] = {
        "task_id": task_id,
        "status": TaskStatus.PENDING,
        "progress": 0,
        "message": "تم استلام الفيديو، جاري بدء المعالجة...",
        "stage": "PENDING",
        "source": "upload",
        "filename": file.filename,
        "mode": mode,
        "target_lang": target_lang,
        "created_at": datetime.now().isoformat(),
        "result": None
    }
    
    print(f"🚀 New UPLOAD task: {task_id} - Mode: {mode}")
    
    # Start background processing
    background_tasks.add_task(process_uploaded_video_task, task_id, upload_path, mode, target_lang, file.filename)
    
    return TaskResponse(
        task_id=task_id,
        status=TaskStatus.PENDING,
        progress=0,
        message="تم رفع الفيديو بنجاح، جاري المعالجة...",
        stage="PENDING"
    )

async def process_uploaded_video_task(task_id: str, video_path: str, mode: str, target_lang: str, original_filename: str):
    """Background task for processing UPLOADED video (no YouTube download needed)"""
    try:
        print(f"📹 Processing uploaded video: {task_id[:8]}...")
        
        # Skip download - video already uploaded!
        update_task(task_id, TaskStatus.DOWNLOADING, 15, "✅ تم استلام الفيديو", "DOWNLOAD")
        
        title = original_filename or "Uploaded Video"
        thumbnail = ""
        
        # STEP 2: Extract Audio
        update_task(task_id, TaskStatus.TRANSCRIBING, 20, "جاري استخراج الصوت...", "TRANSCRIPTION")
        from moviepy.editor import VideoFileClip, AudioFileClip, CompositeAudioClip
        import moviepy.audio.fx.all as afx
        
        base_name = os.path.basename(video_path).split('.')[0]
        audio_path = os.path.join(AUDIO_FOLDER, f"{base_name}.mp3")
        
        clip = VideoFileClip(video_path)
        if clip.audio is None:
            raise ValueError("لا يوجد صوت في هذا الفيديو")
        clip.audio.write_audiofile(audio_path, verbose=False, logger=None)
        clip.close()
        
        # STEP 3: Transcribe
        update_task(task_id, TaskStatus.TRANSCRIBING, 25, "تحليل الصوت باستخدام Whisper AI...", "TRANSCRIPTION")
        whisper_model = load_whisper_model()
        
        segments_gen, info = whisper_model.transcribe(audio_path, beam_size=5, language=None)
        
        segments = []
        full_text = ""
        for segment in segments_gen:
            segments.append({
                "start": segment.start,
                "end": segment.end,
                "text": segment.text
            })
            full_text += segment.text + " "
        
        detected_lang = info.language
        update_task(task_id, TaskStatus.TRANSCRIBING, 45, f"تم استخراج النص (اللغة: {detected_lang}) ✓", "TRANSCRIPTION")
        
        del whisper_model
        
        result = {
            "title": title,
            "thumbnail": thumbnail,
            "original_text": full_text[:500] + "..." if len(full_text) > 500 else full_text,
            "video_path": video_path,
            "detected_language": detected_lang
        }
        
        # STEP 4: Process based on mode
        
        # --- SUBTITLES MODE ---
        if mode in ["SUBTITLES", "BOTH"]:
            update_task(task_id, TaskStatus.GENERATING_SUBTITLES, 50, "إنشاء ملف الترجمة...", "SUBTITLE_GENERATION")
            
            translator = load_argos_translator()
            
            srt_content = ""
            for i, segment in enumerate(segments, 1):
                start_time = segment['start']
                end_time = segment['end']
                text = segment['text'].strip()
                
                if not text:
                    continue
                
                translated_text = translate_text_lazy(text, translator, "en", target_lang)
                
                def format_time(seconds):
                    hours = int(seconds // 3600)
                    minutes = int((seconds % 3600) // 60)
                    secs = int(seconds % 60)
                    millis = int((seconds - int(seconds)) * 1000)
                    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
                
                srt_content += f"{i}\n"
                srt_content += f"{format_time(start_time)} --> {format_time(end_time)}\n"
                srt_content += f"{translated_text}\n\n"
            
            srt_filename = f"{base_name}_{target_lang}.srt"
            srt_path = os.path.join(OUTPUT_FOLDER, srt_filename)
            
            with open(srt_path, 'w', encoding='utf-8') as f:
                f.write(srt_content)
            
            result["srt_path"] = srt_path
            result["srt_url"] = f"/output/{srt_filename}"
            update_task(task_id, TaskStatus.GENERATING_SUBTITLES, 60, "تم إنشاء ملف الترجمة ✓", "SUBTITLE_GENERATION")
        
        # --- DUBBING MODE ---
        if mode in ["DUBBING", "BOTH"]:
            update_task(task_id, TaskStatus.TRANSLATING, 55, "ترجمة النص إلى العربية...", "TRANSLATION")
            
            try:
                translator
            except NameError:
                translator = load_argos_translator()
            
            audio_clips = []
            translated_texts = []
            total_segments = len(segments)
            
            tts_voice = "ar-EG-SalmaNeural"
            
            for i, segment in enumerate(segments):
                start_time = segment['start']
                end_time = segment['end']
                original_text = segment['text'].strip()
                
                if not original_text:
                    continue
                
                translated_text = translate_text_lazy(original_text, translator, detected_lang or "en", target_lang)
                translated_texts.append(translated_text)
                
                update_task(task_id, TaskStatus.GENERATING_AUDIO, 
                           60 + int((i / total_segments) * 25), 
                           f"توليد الدبلجة الصوتية ({i+1}/{total_segments})...", 
                           "VOICE_GENERATION")
                
                try:
                    segment_audio_name = f"seg_{task_id[:8]}_{i}.mp3"
                    segment_audio_path = os.path.join(AUDIO_FOLDER, segment_audio_name)
                    
                    import nest_asyncio
                    nest_asyncio.apply()
                    asyncio.get_event_loop().run_until_complete(
                        generate_tts_lazy(translated_text, segment_audio_path, tts_voice)
                    )
                    
                    audio_clip = AudioFileClip(segment_audio_path)
                    
                    segment_duration = end_time - start_time
                    current_duration = audio_clip.duration
                    
                    if current_duration > segment_duration and segment_duration > 0:
                        speed_factor = min(current_duration / segment_duration, 1.8)
                        audio_clip = audio_clip.fx(afx.speedx, speed_factor)
                    
                    audio_clip = audio_clip.set_start(start_time)
                    audio_clips.append(audio_clip)
                    
                except Exception as e:
                    print(f"⚠️ TTS error for segment {i}: {e}")
                    continue
            
            # Merge
            if audio_clips:
                update_task(task_id, TaskStatus.MERGING, 88, "دمج ومزامنة الصوت مع الفيديو...", "SYNCING")
                
                original_video = VideoFileClip(video_path)
                final_audio = CompositeAudioClip(audio_clips)
                final_audio = final_audio.set_duration(original_video.duration)
                final_video = original_video.set_audio(final_audio)
                
                output_filename = f"dubbed_{base_name}.mp4"
                output_video_path = os.path.join(OUTPUT_FOLDER, output_filename)
                
                final_video.write_videofile(
                    output_video_path, 
                    codec="libx264", 
                    audio_codec="aac",
                    verbose=False, 
                    logger=None,
                    threads=2
                )
                
                original_video.close()
                final_audio.close()
                
                result["dubbed_video_path"] = output_video_path
                result["dubbed_video_url"] = f"/output/{output_filename}"
                result["translated_text"] = " ".join(translated_texts[:10]) + "..." if len(translated_texts) > 10 else " ".join(translated_texts)
                
                update_task(task_id, TaskStatus.MERGING, 95, "تم دمج الصوت مع الفيديو ✓", "SYNCING")
        
        # COMPLETE
        update_task(task_id, TaskStatus.COMPLETED, 100, "تمت العملية بنجاح! 🎉", "FINALIZING", result)
        print(f"✅ Upload task completed: {task_id[:8]}")
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        error_msg = f"فشلت العملية: {str(e)}"
        update_task(task_id, TaskStatus.FAILED, 0, error_msg, "FAILED")
        print(f"❌ Upload task failed: {task_id[:8]} - {error_msg}")

# ============= Legacy Endpoints =============
@app.post("/translate")
def translate_endpoint(req: TextRequest):
    """Translate text to target language"""
    try:
        translator = load_argos_translator()
        translated = translate_text_lazy(req.text, translator, "en", req.target_lang)
        return {"status": "success", "translated_text": translated, "source_text": req.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate-audio")
async def tts_endpoint(req: TTSRequest):
    """Generate TTS audio from text"""
    try:
        output_filename = f"tts_{req.lang}_{abs(hash(req.text)) % 10000}.mp3"
        output_path = os.path.join(AUDIO_FOLDER, output_filename)
        await generate_tts_lazy(req.text, output_path)
        return {"status": "success", "audio_path": output_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============= Startup =============
@app.on_event("startup")
async def startup_event():
    """Initialize on startup - NO HEAVY MODEL LOADING"""
    print("🚀 Arab Dubbing API v2.0 Starting...")
    print(f"📁 Downloads: {os.path.abspath(DOWNLOADS_FOLDER)}")
    print(f"📁 Audio: {os.path.abspath(AUDIO_FOLDER)}")
    print(f"📁 Output: {os.path.abspath(OUTPUT_FOLDER)}")
    print("⚡ Models will be loaded on-demand (Lazy Loading)")
    print("✅ API Ready!")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
