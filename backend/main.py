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

app = FastAPI(
    title="Arab Dubbing API",
    description="AI-powered video dubbing and translation platform",
    version="1.0.0"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "*"],
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
# In-memory task storage (replace with Redis/DB in production)
tasks: Dict[str, dict] = {}

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

def _download_video(url: str, task_id: str = None):
    """Download video from YouTube"""
    if task_id:
        update_task(task_id, TaskStatus.DOWNLOADING, 10, "جاري تحميل الفيديو...", "DOWNLOAD")
    
    ydl_opts = {
        "outtmpl": f"{DOWNLOADS_FOLDER}/%(id)s.%(ext)s",
        "format": "mp4",
        "overwrites": True
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
    return filename, info.get("title"), info.get("thumbnail")

def _extract_audio(video_path: str):
    """Extract audio from video file"""
    base_name = os.path.basename(video_path).split('.')[0]
    audio_path = os.path.join(AUDIO_FOLDER, f"{base_name}.mp3")
    
    clip = VideoFileClip(video_path)
    clip.audio.write_audiofile(audio_path, verbose=False, logger=None)
    clip.close()
    return audio_path

def _transcribe_audio(audio_path: str, task_id: str = None):
    """Transcribe audio using Whisper"""
    if task_id:
        update_task(task_id, TaskStatus.TRANSCRIBING, 30, "تحليل الصوت واستخراج النص (Whisper)...", "TRANSCRIPTION")
    
    model = whisper.load_model("base")
    result = model.transcribe(audio_path)
    return result["segments"], result.get("text", "")

def _generate_srt(segments: list, target_lang: str, task_id: str = None) -> str:
    """Generate SRT subtitle file from segments"""
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
        
        try:
            translated_text = translator.translate(text)
        except:
            translated_text = text
        
        # Convert seconds to SRT time format
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
    return {
        "message": "Arab Dubbing API - مرحباً بكم في دبلجة العرب",
        "version": "1.0.0",
        "endpoints": ["/process", "/status/{task_id}", "/download/{task_id}"]
    }

@app.get("/health")
def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.post("/process", response_model=TaskResponse)
async def start_processing(req: VideoRequest, background_tasks: BackgroundTasks):
    """
    Start video processing job
    Returns task_id for polling status
    """
    task_id = str(uuid.uuid4())
    
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
    """Background task for video processing"""
    try:
        # 1. Download
        video_path, title, thumbnail = _download_video(req.url, task_id)
        update_task(task_id, TaskStatus.DOWNLOADING, 20, "تم تحميل الفيديو", "DOWNLOAD")
        
        # 2. Extract Audio
        audio_path = _extract_audio(video_path)
        
        # 3. Transcribe
        segments, full_text = _transcribe_audio(audio_path, task_id)
        update_task(task_id, TaskStatus.TRANSCRIBING, 40, "تم استخراج النص", "TRANSCRIPTION")
        
        result = {
            "title": title,
            "thumbnail": thumbnail,
            "original_text": full_text,
            "video_path": video_path
        }
        
        # 4. Process based on mode
        if req.mode in ["SUBTITLES", "BOTH"]:
            # Generate SRT
            srt_content = _generate_srt(segments, req.target_lang, task_id)
            srt_filename = f"{os.path.basename(video_path).split('.')[0]}_{req.target_lang}.srt"
            srt_path = os.path.join(OUTPUT_FOLDER, srt_filename)
            with open(srt_path, 'w', encoding='utf-8') as f:
                f.write(srt_content)
            result["srt_path"] = srt_path
            result["srt_url"] = f"/output/{srt_filename}"
        
        if req.mode in ["DUBBING", "BOTH"]:
            update_task(task_id, TaskStatus.TRANSLATING, 50, "ترجمة النص...", "TRANSLATION")
            
            # Translate and generate audio
            update_task(task_id, TaskStatus.GENERATING_AUDIO, 60, "توليد الدبلجة الصوتية...", "VOICE_GENERATION")
            
            audio_clips = []
            translated_texts = []
            translator = GoogleTranslator(source='auto', target=req.target_lang)
            
            for i, segment in enumerate(segments):
                start_time = segment['start']
                end_time = segment['end']
                original_text = segment['text'].strip()
                
                if not original_text:
                    continue
                
                # Translate
                try:
                    translated_text = translator.translate(original_text)
                    translated_texts.append(translated_text)
                except:
                    translated_text = original_text
                
                # Generate TTS
                tts = gTTS(text=translated_text, lang=req.target_lang)
                segment_audio_name = f"seg_{task_id}_{i}.mp3"
                segment_audio_path = os.path.join(AUDIO_FOLDER, segment_audio_name)
                tts.save(segment_audio_path)
                
                # Create Clip
                audio_clip = AudioFileClip(segment_audio_path)
                
                # Adjust Duration
                segment_duration = end_time - start_time
                current_duration = audio_clip.duration
                
                if current_duration > segment_duration:
                    speed_factor = current_duration / segment_duration
                    audio_clip = audio_clip.fx(afx.speedx, speed_factor)
                
                audio_clip = audio_clip.set_start(start_time)
                audio_clips.append(audio_clip)
                
                # Update progress
                progress = 60 + int((i / len(segments)) * 20)
                update_task(task_id, TaskStatus.GENERATING_AUDIO, progress, f"معالجة المقطع {i+1}/{len(segments)}...", "VOICE_GENERATION")
            
            # Merge
            update_task(task_id, TaskStatus.MERGING, 85, "دمج ومزامنة المحتوى...", "SYNCING")
            
            original_video = VideoFileClip(video_path)
            
            if audio_clips:
                final_audio = CompositeAudioClip(audio_clips)
                final_audio = final_audio.set_duration(original_video.duration)
                final_video = original_video.set_audio(final_audio)
                
                output_filename = f"dubbed_{os.path.basename(video_path)}"
                output_video_path = os.path.join(OUTPUT_FOLDER, output_filename)
                final_video.write_videofile(output_video_path, codec="libx264", audio_codec="aac", verbose=False, logger=None)
                
                original_video.close()
                final_audio.close()
                
                result["dubbed_video_path"] = output_video_path
                result["dubbed_video_url"] = f"/output/{output_filename}"
                result["translated_text"] = " ".join(translated_texts)
        
        # Complete
        update_task(task_id, TaskStatus.COMPLETED, 100, "تمت العملية بنجاح!", "FINALIZING", result)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        update_task(task_id, TaskStatus.FAILED, 0, f"فشلت العملية: {str(e)}", "FAILED")

@app.get("/status/{task_id}", response_model=TaskResponse)
def get_task_status(task_id: str):
    """Get processing status for a task"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
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
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = tasks[task_id]
    result = task.get("result", {})
    
    if file_type == "video" and "dubbed_video_path" in result:
        return FileResponse(result["dubbed_video_path"], filename=f"dubbed_video.mp4")
    elif file_type == "srt" and "srt_path" in result:
        return FileResponse(result["srt_path"], filename=f"subtitles.srt")
    else:
        raise HTTPException(status_code=404, detail=f"File type '{file_type}' not available")

# Legacy endpoints for backwards compatibility
@app.post("/download")
def download_endpoint(url: str):
    try:
        path, title, thumb = _download_video(url)
        return {"status": "success", "file_path": path, "title": title, "thumbnail": thumb}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/transcribe")
def transcribe_endpoint(audio_path: str):
    try:
        if not os.path.exists(audio_path):
            raise HTTPException(status_code=404, detail="Audio file not found")
        segments, text = _transcribe_audio(audio_path)
        return {"status": "success", "segments": segments, "text": text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/translate")
def translate_endpoint(req: TextRequest):
    try:
        translated = GoogleTranslator(source='auto', target=req.target_lang).translate(req.text)
        return {"status": "success", "translated_text": translated, "source_text": req.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate-audio")
def tts_endpoint(req: TTSRequest):
    try:
        tts = gTTS(text=req.text, lang=req.lang)
        output_filename = f"tts_{req.lang}_{hash(req.text)}.mp3"
        output_path = os.path.join(AUDIO_FOLDER, output_filename)
        tts.save(output_path)
        return {"status": "success", "audio_path": output_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
