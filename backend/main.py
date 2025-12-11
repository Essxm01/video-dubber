from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, Dict, Literal
import uvicorn
import yt_dlp
import os
import whisper
from deep_translator import GoogleTranslator
from gtts import gTTS
from moviepy.editor import VideoFileClip, AudioFileClip, CompositeAudioClip
import moviepy.audio.fx.all as afx
import uuid
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = FastAPI(
    title="Arab Dubbing API",
    description="AI-powered video dubbing and translation platform - دبلجة العرب",
    version="1.0.0"
)

# CORS Configuration - Allow frontend domains
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "https://arab-dubbing.vercel.app",
    "https://arab-dubbing-*.vercel.app",
    "*"  # Allow all for development
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
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

# Mount static files for serving output videos
app.mount("/output", StaticFiles(directory=OUTPUT_FOLDER), name="output")

# ============= Task Management =============
# In-memory task storage (for production, use Redis or Supabase)
tasks: Dict[str, dict] = {}

# Load Whisper model on startup (cached)
WHISPER_MODEL = None

def get_whisper_model():
    """Lazy load Whisper model"""
    global WHISPER_MODEL
    if WHISPER_MODEL is None:
        model_size = os.getenv("WHISPER_MODEL", "base")
        print(f"🎙️ Loading Whisper model: {model_size}")
        WHISPER_MODEL = whisper.load_model(model_size)
    return WHISPER_MODEL

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
    target_lang: str = "ar"  # Default to Arabic
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
    """Download video from YouTube using yt-dlp"""
    if task_id:
        update_task(task_id, TaskStatus.DOWNLOADING, 5, "جاري تحميل الفيديو من يوتيوب...", "DOWNLOAD")
    
    ydl_opts = {
        "outtmpl": f"{DOWNLOADS_FOLDER}/%(id)s.%(ext)s",
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "overwrites": True,
        "quiet": True,
        "no_warnings": True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
            # Ensure file has .mp4 extension
            if not filename.endswith('.mp4'):
                base = os.path.splitext(filename)[0]
                if os.path.exists(base + '.mp4'):
                    filename = base + '.mp4'
            
            if task_id:
                update_task(task_id, TaskStatus.DOWNLOADING, 15, "تم تحميل الفيديو بنجاح", "DOWNLOAD")
            
            return filename, info.get("title"), info.get("thumbnail")
    except Exception as e:
        print(f"❌ Download error: {e}")
        raise HTTPException(status_code=500, detail=f"فشل تحميل الفيديو: {str(e)}")

def _extract_audio(video_path: str):
    """Extract audio from video file"""
    base_name = os.path.basename(video_path).split('.')[0]
    audio_path = os.path.join(AUDIO_FOLDER, f"{base_name}.mp3")
    
    try:
        clip = VideoFileClip(video_path)
        if clip.audio is None:
            raise ValueError("لا يوجد صوت في هذا الفيديو")
        clip.audio.write_audiofile(audio_path, verbose=False, logger=None)
        clip.close()
        return audio_path
    except Exception as e:
        print(f"❌ Audio extraction error: {e}")
        raise

def _transcribe_audio(audio_path: str, task_id: str = None):
    """Transcribe audio using Whisper AI"""
    if task_id:
        update_task(task_id, TaskStatus.TRANSCRIBING, 25, "تحليل الصوت باستخدام Whisper AI...", "TRANSCRIPTION")
    
    try:
        model = get_whisper_model()
        result = model.transcribe(audio_path, language=None)  # Auto-detect language
        
        if task_id:
            update_task(task_id, TaskStatus.TRANSCRIBING, 40, "تم استخراج النص من الصوت", "TRANSCRIPTION")
        
        return result["segments"], result.get("text", ""), result.get("language", "en")
    except Exception as e:
        print(f"❌ Transcription error: {e}")
        raise

def _generate_srt(segments: list, target_lang: str, task_id: str = None) -> str:
    """Generate SRT subtitle file from segments with translation"""
    if task_id:
        update_task(task_id, TaskStatus.GENERATING_SUBTITLES, 70, "تنسيق ملفات الترجمة...", "SUBTITLE_GENERATION")
    
    translator = GoogleTranslator(source='auto', target=target_lang)
    srt_content = ""
    
    for i, segment in enumerate(segments, 1):
        start_time = segment['start']
        end_time = segment['end']
        text = segment['text'].strip()
        
        if not text:
            continue
        
        # Translate text
        try:
            translated_text = translator.translate(text)
        except Exception as e:
            print(f"⚠️ Translation fallback for segment {i}: {e}")
            translated_text = text
        
        # Convert seconds to SRT time format (HH:MM:SS,mmm)
        def format_time(seconds):
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            secs = int(seconds % 60)
            millis = int((seconds - int(seconds)) * 1000)
            return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
        
        srt_content += f"{i}\n"
        srt_content += f"{format_time(start_time)} --> {format_time(end_time)}\n"
        srt_content += f"{translated_text}\n\n"
    
    return srt_content

# ============= API Endpoints =============
@app.get("/")
def root():
    """API Health Check"""
    return {
        "message": "Arab Dubbing API - مرحباً بكم في دبلجة العرب 🎬",
        "version": "1.0.0",
        "status": "active",
        "endpoints": {
            "process": "POST /process - Start video processing",
            "status": "GET /status/{task_id} - Check processing status",
            "download": "GET /download/{task_id}/{file_type} - Download result",
            "health": "GET /health - Health check"
        }
    }

@app.get("/health")
def health_check():
    """Health check endpoint for monitoring"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "whisper_model": os.getenv("WHISPER_MODEL", "base"),
        "active_tasks": len([t for t in tasks.values() if t.get("status") not in ["COMPLETED", "FAILED"]])
    }

@app.post("/process", response_model=TaskResponse)
async def start_processing(req: VideoRequest, background_tasks: BackgroundTasks):
    """
    Start video processing job
    
    - **url**: YouTube video URL
    - **target_lang**: Target language code (default: ar for Arabic)
    - **mode**: DUBBING, SUBTITLES, or BOTH
    
    Returns task_id for polling status
    """
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
    
    print(f"🚀 New task created: {task_id} - Mode: {req.mode} - Lang: {req.target_lang}")
    
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
    """Background task for complete video processing pipeline"""
    try:
        print(f"📹 Starting processing for task: {task_id[:8]}...")
        
        # ========== STEP 1: Download Video ==========
        video_path, title, thumbnail = _download_video(req.url, task_id)
        update_task(task_id, TaskStatus.DOWNLOADING, 20, "تم تحميل الفيديو بنجاح ✓", "DOWNLOAD")
        
        # ========== STEP 2: Extract Audio ==========
        audio_path = _extract_audio(video_path)
        
        # ========== STEP 3: Transcribe with Whisper ==========
        segments, full_text, detected_lang = _transcribe_audio(audio_path, task_id)
        update_task(task_id, TaskStatus.TRANSCRIBING, 45, f"تم استخراج النص (اللغة: {detected_lang}) ✓", "TRANSCRIPTION")
        
        result = {
            "title": title,
            "thumbnail": thumbnail,
            "original_text": full_text[:500] + "..." if len(full_text) > 500 else full_text,
            "video_path": video_path,
            "detected_language": detected_lang
        }
        
        # ========== STEP 4: Process based on mode ==========
        
        # --- SUBTITLES MODE ---
        if req.mode in ["SUBTITLES", "BOTH"]:
            update_task(task_id, TaskStatus.GENERATING_SUBTITLES, 50, "إنشاء ملف الترجمة...", "SUBTITLE_GENERATION")
            
            srt_content = _generate_srt(segments, req.target_lang, task_id)
            srt_filename = f"{os.path.basename(video_path).split('.')[0]}_{req.target_lang}.srt"
            srt_path = os.path.join(OUTPUT_FOLDER, srt_filename)
            
            with open(srt_path, 'w', encoding='utf-8') as f:
                f.write(srt_content)
            
            result["srt_path"] = srt_path
            result["srt_url"] = f"/output/{srt_filename}"
            update_task(task_id, TaskStatus.GENERATING_SUBTITLES, 60, "تم إنشاء ملف الترجمة ✓", "SUBTITLE_GENERATION")
        
        # --- DUBBING MODE ---
        if req.mode in ["DUBBING", "BOTH"]:
            update_task(task_id, TaskStatus.TRANSLATING, 55, "ترجمة النص إلى العربية...", "TRANSLATION")
            
            audio_clips = []
            translated_texts = []
            translator = GoogleTranslator(source='auto', target=req.target_lang)
            
            total_segments = len(segments)
            
            for i, segment in enumerate(segments):
                start_time = segment['start']
                end_time = segment['end']
                original_text = segment['text'].strip()
                
                if not original_text:
                    continue
                
                # Translate text
                try:
                    translated_text = translator.translate(original_text)
                    translated_texts.append(translated_text)
                except Exception as e:
                    print(f"⚠️ Translation error for segment {i}: {e}")
                    translated_text = original_text
                
                # Generate TTS audio
                update_task(task_id, TaskStatus.GENERATING_AUDIO, 
                           60 + int((i / total_segments) * 25), 
                           f"توليد الدبلجة الصوتية ({i+1}/{total_segments})...", 
                           "VOICE_GENERATION")
                
                try:
                    tts = gTTS(text=translated_text, lang=req.target_lang, slow=False)
                    segment_audio_name = f"seg_{task_id[:8]}_{i}.mp3"
                    segment_audio_path = os.path.join(AUDIO_FOLDER, segment_audio_name)
                    tts.save(segment_audio_path)
                    
                    # Create audio clip and align with video timeline
                    audio_clip = AudioFileClip(segment_audio_path)
                    
                    # Adjust speed to fit segment duration
                    segment_duration = end_time - start_time
                    current_duration = audio_clip.duration
                    
                    if current_duration > segment_duration and segment_duration > 0:
                        speed_factor = min(current_duration / segment_duration, 1.8)  # Cap at 1.8x
                        audio_clip = audio_clip.fx(afx.speedx, speed_factor)
                    
                    audio_clip = audio_clip.set_start(start_time)
                    audio_clips.append(audio_clip)
                    
                except Exception as e:
                    print(f"⚠️ TTS error for segment {i}: {e}")
                    continue
            
            # ========== STEP 5: Merge Audio with Video ==========
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
                    threads=4
                )
                
                # Cleanup
                original_video.close()
                final_audio.close()
                
                result["dubbed_video_path"] = output_video_path
                result["dubbed_video_url"] = f"/output/{output_filename}"
                result["translated_text"] = " ".join(translated_texts[:10]) + "..." if len(translated_texts) > 10 else " ".join(translated_texts)
                
                update_task(task_id, TaskStatus.MERGING, 95, "تم دمج الصوت مع الفيديو ✓", "SYNCING")
        
        # ========== COMPLETE ==========
        update_task(task_id, TaskStatus.COMPLETED, 100, "تمت العملية بنجاح! 🎉", "FINALIZING", result)
        print(f"✅ Task completed successfully: {task_id[:8]}")
        
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
            filename=f"dubbed_video.mp4",
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

# ============= Legacy Endpoints (backwards compatibility) =============

@app.post("/download")
def download_endpoint(url: str):
    """Legacy: Download video only"""
    try:
        path, title, thumb = _download_video(url)
        return {"status": "success", "file_path": path, "title": title, "thumbnail": thumb}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/translate")
def translate_endpoint(req: TextRequest):
    """Translate text to target language"""
    try:
        translated = GoogleTranslator(source='auto', target=req.target_lang).translate(req.text)
        return {"status": "success", "translated_text": translated, "source_text": req.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate-audio")
def tts_endpoint(req: TTSRequest):
    """Generate TTS audio from text"""
    try:
        tts = gTTS(text=req.text, lang=req.lang)
        output_filename = f"tts_{req.lang}_{abs(hash(req.text)) % 10000}.mp3"
        output_path = os.path.join(AUDIO_FOLDER, output_filename)
        tts.save(output_path)
        return {"status": "success", "audio_path": output_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============= Startup =============
@app.on_event("startup")
async def startup_event():
    """Pre-load Whisper model on startup"""
    print("🚀 Arab Dubbing API Starting...")
    print(f"📁 Downloads folder: {os.path.abspath(DOWNLOADS_FOLDER)}")
    print(f"📁 Audio folder: {os.path.abspath(AUDIO_FOLDER)}")
    print(f"📁 Output folder: {os.path.abspath(OUTPUT_FOLDER)}")
    
    # Optionally pre-load Whisper model
    if os.getenv("PRELOAD_WHISPER", "false").lower() == "true":
        get_whisper_model()
    
    print("✅ API Ready!")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
