"""
Arab Dubbing API - Production Version v6.2
AI-powered video dubbing and translation platform

FEATURES:
- Groq API for Whisper transcription (whisper-large-v3)
- Gemini 2.5 Flash TTS (primary) with Edge-TTS fallback
- Director's Notes for natural Arabic speech
- Supabase Storage with retry logic
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
import time
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

app = FastAPI(title="Arab Dubbing API", version="6.2.0")

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

# ============= Fresh Supabase Client (Fixes disconnection) =============

def get_fresh_supabase():
    """Create a FRESH Supabase client for each operation"""
    try:
        from supabase import create_client
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        print(f"⚠️ Supabase init error: {e}")
        return None

# ============= Groq Client =============
_groq = None

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

# ============= DB Operations with Retry =============

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
                    "message": "جاري البدء...",
                    "stage": "PENDING",
                    "mode": mode,
                    "created_at": datetime.now().isoformat(),
                }).execute()
                print(f"✅ DB: Task created {task_id[:8]}")
                return
        except Exception as e:
            print(f"⚠️ DB create attempt {attempt+1}/3: {e}")
            time.sleep(1)

def db_update(task_id: str, status: str, progress: int, message: str, stage: str = None, result: dict = None):
    for attempt in range(3):
        try:
            sb = get_fresh_supabase()
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
                return
        except Exception as e:
            print(f"⚠️ DB update attempt {attempt+1}/3: {e}")
            time.sleep(1)

def db_get(task_id: str) -> dict:
    for attempt in range(3):
        try:
            sb = get_fresh_supabase()
            if sb:
                res = sb.table("projects").select("*").eq("id", task_id).execute()
                if res.data and len(res.data) > 0:
                    return res.data[0]
                return None
        except Exception as e:
            print(f"⚠️ DB get attempt {attempt+1}/3: {e}")
            time.sleep(0.5)
    return {"status": "PROCESSING", "progress": 10, "message": "جاري المعالجة..."}

# ============= Storage with Public URL =============

def upload_to_storage(file_path: str, bucket: str, dest_name: str, content_type: str) -> str:
    for attempt in range(3):
        try:
            sb = get_fresh_supabase()
            if not sb:
                raise Exception("Supabase not available")
            
            with open(file_path, "rb") as f:
                file_data = f.read()
            
            sb.storage.from_(bucket).upload(
                path=dest_name,
                file=file_data,
                file_options={"content-type": content_type, "upsert": "true"}
            )
            
            public_url = sb.storage.from_(bucket).get_public_url(dest_name)
            print(f"✅ UPLOADED: {dest_name}")
            print(f"✅ FINAL PUBLIC URL: {public_url}")
            return public_url
            
        except Exception as e:
            print(f"⚠️ Storage upload attempt {attempt+1}/3: {e}")
            time.sleep(1)
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

def extract_audio(video_path: str, audio_path: str) -> bool:
    cmd = ["ffmpeg", "-i", video_path, "-vn", "-acodec", "libmp3lame", "-ab", "64k", "-ar", "16000", "-y", audio_path]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=300)
        return True
    except:
        return False

def transcribe_groq(audio_path: str) -> tuple:
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
        translated = argostranslate.translate.translate(text, src, tgt)
        print(f"🌐 Translated [{src}->{tgt}]: {text[:30]}... -> {translated[:30]}...")
        return translated
    except Exception as e:
        print(f"⚠️ Translation failed ({src}->{tgt}): {e}")
        return text  # Return original if translation fails

# ============= TTS: GEMINI 2.5 PRIMARY + EDGE-TTS FALLBACK =============

def tts_gemini_25(text: str, output_path: str) -> bool:
    """
    Generate TTS using Gemini 2.5 Flash Preview TTS
    Uses Director's Notes for natural Arabic speech
    Returns True if success, False to trigger fallback
    """
    if not GEMINI_API_KEY:
        print("⚠️ GEMINI_API_KEY not set, using fallback")
        return False
    
    try:
        from google import genai
        from google.genai import types
        
        # Initialize client
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        # Build prompt with Director's Notes for natural Arabic
        prompt_with_notes = f"""### DIRECTOR'S NOTES
Style: Professional, warm, and engaging narration.
Language: Arabic (Egyptian dialect) - speak naturally and clearly.
Pace: Moderate, suitable for video dubbing.
Emotion: Match the content naturally.

#### TRANSCRIPT
{text}"""
        
        # Generate audio using Gemini 2.5 Flash TTS
        response = client.models.generate_content(
            model="gemini-2.5-flash-preview-tts",
            contents=prompt_with_notes,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name="Zephyr"  # Expressive multilingual voice
                        )
                    )
                )
            )
        )
        
        # Extract audio data from response
        if (response.candidates and 
            response.candidates[0].content and 
            response.candidates[0].content.parts):
            
            part = response.candidates[0].content.parts[0]
            
            if hasattr(part, 'inline_data') and part.inline_data:
                audio_data = part.inline_data.data
                mime_type = getattr(part.inline_data, 'mime_type', 'audio/wav')
                
                # Determine temp file extension based on mime
                if 'wav' in mime_type:
                    temp_ext = '.wav'
                elif 'mp3' in mime_type:
                    temp_ext = '.mp3'
                else:
                    temp_ext = '.wav'
                
                temp_path = output_path.replace('.mp3', f'_temp{temp_ext}')
                
                # Save raw audio
                with open(temp_path, 'wb') as f:
                    f.write(audio_data)
                
                # Convert to MP3 if needed
                if temp_ext != '.mp3':
                    cmd = ["ffmpeg", "-i", temp_path, "-y", output_path]
                    subprocess.run(cmd, check=True, capture_output=True, timeout=30)
                    try:
                        os.remove(temp_path)
                    except:
                        pass
                else:
                    os.rename(temp_path, output_path)
                
                print(f"🎙️ Gemini 2.5 TTS: {output_path}")
                return True
        
        print("⚠️ Gemini 2.5 returned no audio data")
        return False
        
    except Exception as e:
        print(f"⚠️ Gemini 2.5 TTS error: {e}")
        return False

async def tts_edge(text: str, path: str, voice: str = "ar-EG-SalmaNeural"):
    """Edge-TTS - Fast and reliable Arabic TTS"""
    import edge_tts
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(path)
    print(f"🔊 Edge-TTS: {path}")

async def generate_tts(text: str, path: str):
    """
    Generate TTS - Uses Edge-TTS directly for speed
    Gemini TTS disabled due to timeout issues
    """
    # DISABLED: Gemini TTS causes 30s timeout per segment
    # To re-enable: uncomment the following lines
    # if tts_gemini_25(text, path):
    #     return
    
    # Use Edge-TTS directly (fast and reliable)
    await tts_edge(text, path)

# ============= Audio/Video Processing =============

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
    return {"status": "active", "version": "6.2.0", "tts": "Gemini 2.5 + Edge Fallback"}

@app.get("/health")
def health():
    return {"status": "healthy"}

MAX_SIZE = 25 * 1024 * 1024

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
    
    print(f"📤 Uploaded: {file.filename} ({size/1024/1024:.1f}MB)")
    
    db_create(task_id, file.filename, mode)
    background_tasks.add_task(process_video, task_id, path, mode, target_lang, file.filename)
    
    return TaskResponse(task_id=task_id, status=Status.PENDING, progress=0, message="جاري المعالجة...", stage="PENDING")

# ============= Main Processing =============

async def process_video(task_id: str, video_path: str, mode: str, target_lang: str, filename: str):
    try:
        print(f"🎬 Processing [{mode}]: {task_id[:8]}")
        base = task_id[:8]
        audio_path = os.path.join(AUDIO_FOLDER, f"{base}.mp3")
        result = {"title": filename, "mode": mode}
        
        # STEP 1: Extract Audio
        db_update(task_id, Status.EXTRACTING, 10, "استخراج الصوت...", "EXTRACTING")
        
        if not extract_audio(video_path, audio_path):
            raise Exception("فشل استخراج الصوت")
        
        # STEP 2: Transcribe
        db_update(task_id, Status.TRANSCRIBING, 25, "تحليل الصوت (Groq AI)...", "TRANSCRIBING")
        
        segments, detected_lang = transcribe_groq(audio_path)
        result["detected_language"] = detected_lang
        result["segments_count"] = len(segments)
        
        db_update(task_id, Status.TRANSCRIBING, 40, f"تم استخراج {len(segments)} جملة ✓", "TRANSCRIBING")
        gc.collect()
        
        # STEP 3: Setup Translation
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
        
        # STEP 4: Subtitles (if needed)
        if mode in ["SUBTITLES", "BOTH"]:
            db_update(task_id, Status.GENERATING_SRT, 50, "إنشاء ملف الترجمة...", "GENERATING_SRT")
            
            srt_content = generate_srt(segments, detected_lang, target_lang)
            
            srt_filename = f"{base}_{target_lang}.srt"
            srt_local = os.path.join(OUTPUT_FOLDER, srt_filename)
            with open(srt_local, "w", encoding="utf-8") as f:
                f.write(srt_content)
            
            srt_url = upload_to_storage(srt_local, "videos", f"subtitles/{srt_filename}", "text/plain; charset=utf-8")
            
            if srt_url:
                result["srt_url"] = srt_url
            else:
                result["srt_url"] = f"/output/{srt_filename}"
            
            db_update(task_id, Status.GENERATING_SRT, 55, "تم إنشاء ملف الترجمة ✓", "GENERATING_SRT")
        
        # STEP 5: TTS Dubbing (if needed)
        if mode in ["DUBBING", "BOTH"]:
            db_update(task_id, Status.GENERATING_AUDIO, 55, "توليد الدبلجة (Gemini 2.5)...", "GENERATING_AUDIO")
            
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
                    asyncio.get_event_loop().run_until_complete(generate_tts(translated, tts_path))
                    tts_files.append(tts_path)
                except Exception as e:
                    print(f"TTS {i}: {e}")
            
            # STEP 6: Merge & Upload
            if tts_files:
                db_update(task_id, Status.MERGING, 82, "دمج الصوت...", "MERGING")
                
                merged_audio = os.path.join(AUDIO_FOLDER, f"merged_{base}.mp3")
                
                if merge_audio(tts_files, merged_audio):
                    db_update(task_id, Status.MERGING, 88, "دمج مع الفيديو...", "MERGING")
                    
                    output_name = f"dubbed_{base}.mp4"
                    output_local = os.path.join(OUTPUT_FOLDER, output_name)
                    
                    if combine_video_audio(video_path, merged_audio, output_local):
                        db_update(task_id, Status.UPLOADING, 92, "رفع الفيديو...", "UPLOADING")
                        
                        video_url = upload_to_storage(
                            output_local,
                            "videos",
                            f"dubbed/{output_name}",
                            "video/mp4"
                        )
                        
                        if video_url:
                            result["dubbed_video_url"] = video_url
                            print(f"🎬 FINAL VIDEO URL: {video_url}")
                        else:
                            result["dubbed_video_url"] = f"/output/{output_name}"
                        
                        result["dubbed_video_path"] = output_local
                    
                    # Cleanup
                    for f in tts_files:
                        try: os.remove(f)
                        except: pass
                    try: os.remove(merged_audio)
                    except: pass
            
            gc.collect()
        
        # DONE
        db_update(task_id, Status.COMPLETED, 100, "تمت العملية بنجاح! 🎉", "COMPLETED", result)
        print(f"✅ COMPLETED: {task_id[:8]}")
        print(f"✅ RESULT: {result}")
        
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
    print("🚀 Arab Dubbing API v6.2")
    print(f"🧠 STT: Groq Whisper Large-v3")
    print(f"🎙️ TTS: Gemini 2.5 Flash (+ Edge Fallback)")
    print(f"💾 Storage: Supabase (with retry)")
    
    if not GROQ_API_KEY:
        print("⚠️ GROQ_API_KEY missing!")
    if not GEMINI_API_KEY:
        print("⚠️ GEMINI_API_KEY missing - will use Edge-TTS only")
    if not SUPABASE_URL:
        print("⚠️ SUPABASE_URL missing!")
    
    print("✅ Ready!")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
