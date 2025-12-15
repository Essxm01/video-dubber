"""
Arab Dubbing API - Version 12.0 (Natural Speech + Background Audio)
- NEW: Natural/Colloquial Arabic translation (not formal Fus-ha)
- NEW: Background audio mixing (10% original + 100% dubbed)
- IMPROVED: More human-like dubbing experience
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
from deep_translator import GoogleTranslator

load_dotenv()

# Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

app = FastAPI(title="Arab Dubbing API", version="12.0.0")

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

# Voice options for Edge TTS
VOICES = {
    "female": "ar-EG-SalmaNeural",
    "male": "ar-EG-ShakirNeural",
    "female_gulf": "ar-AE-FatimaNeural",
    "male_gulf": "ar-AE-HamdanNeural",
}

# ============= DB Helper =============
def get_fresh_supabase():
    try:
        from supabase import create_client
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except: 
        return None

def db_update(task_id: str, status: str, progress: int, message: str, result: dict = None):
    try:
        sb = get_fresh_supabase()
        if sb:
            data = {"status": status, "progress": progress, "message": message, "updated_at": datetime.now().isoformat()}
            if result: data["result"] = result
            sb.table("projects").update(data).eq("id", task_id).execute()
            print(f"📊 {status} {progress}%: {message}")
    except Exception as e:
        print(f"DB Update Error: {e}")

def upload_to_storage(file_path: str, bucket: str, dest_name: str, content_type: str) -> str:
    try:
        sb = get_fresh_supabase()
        if not sb: return None
        with open(file_path, "rb") as f:
            sb.storage.from_(bucket).upload(path=dest_name, file=f.read(), file_options={"content-type": content_type, "upsert": "true"})
        url = sb.storage.from_(bucket).get_public_url(dest_name)
        print(f"✅ Uploaded: {url}")
        return url
    except Exception as e:
        print(f"Storage Error: {e}")
        return None

# ============= AI Logic =============
def extract_audio(video_path: str, audio_path: str) -> bool:
    cmd = ["ffmpeg", "-i", video_path, "-vn", "-acodec", "libmp3lame", "-ab", "128k", "-ar", "24000", "-y", audio_path]
    result = subprocess.run(cmd, capture_output=True)
    return result.returncode == 0

def get_video_duration(video_path: str) -> float:
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", video_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return float(result.stdout.strip())
    except:
        return 0

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
        if hasattr(transcription, 'segments') and transcription.segments:
            for seg in transcription.segments:
                segments.append({
                    "start": seg["start"], 
                    "end": seg["end"], 
                    "text": seg["text"].strip()
                })
        elif hasattr(transcription, 'text') and transcription.text:
            segments.append({"start": 0, "end": 10, "text": transcription.text.strip()})
        
        if not segments:
            segments.append({"start": 0, "end": 5, "text": "لم يتم العثور على نص"})
        
        return segments
    except Exception as e:
        print(f"Groq Error: {e}")
        return [{"start": 0, "end": 5, "text": "خطأ في التحليل"}]

def translate_natural(text: str, target_lang: str = "ar") -> str:
    """
    Translate to NATURAL Arabic (Egyptian colloquial style)
    Not formal Fus-ha - more like everyday speech
    """
    if not text or not text.strip(): 
        return "نص فارغ"
    
    try:
        # First, do basic translation
        basic_translation = GoogleTranslator(source='auto', target=target_lang).translate(text)
        
        if basic_translation:
            # Make it more natural by replacing formal words with colloquial ones
            natural = basic_translation
            
            # Common replacements for more natural Egyptian Arabic
            replacements = {
                "أنا ذاهب": "أنا رايح",
                "ماذا": "ايه",
                "لماذا": "ليه",
                "هذا": "ده",
                "هذه": "دي",
                "الآن": "دلوقتي",
                "جيد": "كويس",
                "جميل": "حلو",
                "أريد": "عايز",
                "نريد": "عايزين",
                "يريد": "عايز",
                "أذهب": "أروح",
                "نذهب": "نروح",
                "تعال": "تعالى",
                "انظر": "بص",
                "انظري": "بصي",
                "استمع": "اسمع",
                "كثير": "كتير",
                "قليل": "شوية",
                "صغير": "صغير",
                "كبير": "كبير",
                "سوف": "ها",
                "لن": "مش ها",
                "ليس": "مش",
                "ليست": "مش",
                "لكن": "بس",
                "أيضاً": "كمان",
                "فقط": "بس",
                "الأطفال": "الأولاد",
                "أطفال": "أولاد",
            }
            
            for formal, colloquial in replacements.items():
                natural = natural.replace(formal, colloquial)
            
            print(f"🌐 Natural: {text[:20]}... -> {natural[:25]}...")
            return natural
        
        return text
    except Exception as e:
        print(f"⚠️ Translation Error: {e}")
        return text

async def generate_tts(text: str, path: str, voice: str = "female") -> bool:
    if not text or not text.strip():
        text = "نص فارغ"
    
    voice_name = VOICES.get(voice, VOICES["female"])
    
    try:
        import edge_tts
        await edge_tts.Communicate(text, voice_name).save(path)
        
        if os.path.exists(path) and os.path.getsize(path) > 0:
            return True
        return False
    except Exception as e:
        print(f"TTS Error: {e}")
        return False

def generate_silence(duration: float, output_path: str):
    if duration <= 0:
        duration = 0.1
    cmd = ["ffmpeg", "-f", "lavfi", "-i", f"anullsrc=r=24000:cl=mono", "-t", str(duration), "-acodec", "libmp3lame", "-y", output_path]
    subprocess.run(cmd, capture_output=True)
    return os.path.exists(output_path)

def format_srt_time(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

def generate_srt(segments: list, translated_segments: list) -> str:
    srt_content = ""
    for i, (orig, trans) in enumerate(zip(segments, translated_segments), 1):
        start_time = format_srt_time(orig["start"])
        end_time = format_srt_time(orig["end"])
        srt_content += f"{i}\n{start_time} --> {end_time}\n{trans}\n\n"
    return srt_content

def merge_audio_with_background(video_path: str, dubbed_audio: str, original_audio: str, output_path: str, bg_volume: float = 0.1):
    """
    Merge dubbed audio with original audio as background
    bg_volume: 0.0-1.0 (10% = 0.1)
    """
    try:
        # Mix: dubbed at 100% + original at 10%
        # amix filter with volume adjustment
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", dubbed_audio,
            "-i", original_audio,
            "-filter_complex", 
            f"[1:a]volume=1.0[dubbed];[2:a]volume={bg_volume}[bg];[dubbed][bg]amix=inputs=2:duration=shortest[aout]",
            "-map", "0:v:0",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "128k",
            "-shortest",
            output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"⚠️ Audio mix failed, trying simple method: {result.stderr[:200]}")
            # Fallback: just use dubbed audio
            cmd_simple = [
                "ffmpeg", "-y",
                "-i", video_path,
                "-i", dubbed_audio,
                "-c:v", "copy",
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-shortest",
                output_path
            ]
            subprocess.run(cmd_simple, check=True)
        
        return os.path.exists(output_path)
    except Exception as e:
        print(f"Merge Error: {e}")
        return False

def create_timed_audio(tts_files: list, segments: list, video_duration: float, output_path: str):
    """Create a single audio file with proper timing gaps"""
    
    if not tts_files:
        return None
    
    temp_dir = "temp_audio"
    os.makedirs(temp_dir, exist_ok=True)
    
    timed_audio_files = []
    current_time = 0
    
    for i, (audio_file, seg) in enumerate(zip(tts_files, segments)):
        if not audio_file or not os.path.exists(audio_file):
            continue
            
        segment_start = seg.get("start", current_time)
        
        # Add silence gap if needed
        gap_duration = segment_start - current_time
        if gap_duration > 0.05:
            silence_path = os.path.join(temp_dir, f"silence_{i}.mp3")
            generate_silence(gap_duration, silence_path)
            if os.path.exists(silence_path):
                timed_audio_files.append(silence_path)
        
        timed_audio_files.append(audio_file)
        
        # Get audio duration
        probe_cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", audio_file]
        result = subprocess.run(probe_cmd, capture_output=True, text=True)
        try:
            audio_duration = float(result.stdout.strip())
        except:
            audio_duration = seg.get("end", segment_start + 2) - segment_start
        
        current_time = segment_start + audio_duration
    
    # Add final silence
    if current_time < video_duration:
        final_silence = os.path.join(temp_dir, "silence_final.mp3")
        generate_silence(video_duration - current_time, final_silence)
        if os.path.exists(final_silence):
            timed_audio_files.append(final_silence)
    
    if not timed_audio_files:
        return None
    
    # Concatenate
    list_file = os.path.join(temp_dir, "list.txt")
    with open(list_file, "w") as f:
        for a in timed_audio_files:
            f.write(f"file '{os.path.abspath(a)}'\n")
    
    subprocess.run(["ffmpeg", "-f", "concat", "-safe", "0", "-i", list_file, "-c", "copy", "-y", output_path], check=True)
    
    # Cleanup temp
    try:
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
    except: pass
    
    return output_path if os.path.exists(output_path) else None

# ============= API Routes =============
class TaskResponse(BaseModel):
    task_id: str
    status: str
    progress: int = 0
    message: str = ""

@app.get("/")
def root():
    return {"status": "active", "version": "12.0.0", "features": ["natural_arabic", "background_audio", "voice_selection", "srt"]}

@app.get("/health")
def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/voices")
def get_voices():
    return {
        "voices": [
            {"id": "female", "name": "سلمى (مصري أنثى)", "code": VOICES["female"]},
            {"id": "male", "name": "شاكر (مصري ذكر)", "code": VOICES["male"]},
            {"id": "female_gulf", "name": "فاطمة (خليجي أنثى)", "code": VOICES["female_gulf"]},
            {"id": "male_gulf", "name": "حمدان (خليجي ذكر)", "code": VOICES["male_gulf"]},
        ]
    }

@app.post("/upload", response_model=TaskResponse)
async def upload(
    background_tasks: BackgroundTasks, 
    file: UploadFile = File(...), 
    mode: str = Form("DUBBING"), 
    target_lang: str = Form("ar"),
    voice: str = Form("female"),
    generate_srt_file: str = Form("true"),
    bg_audio_volume: str = Form("0")  # Background audio OFF by default
):
    task_id = str(uuid.uuid4())
    
    if not file.filename:
        raise HTTPException(400, "اسم الملف مطلوب")
    
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ['.mp4', '.mkv', '.webm', '.mov', '.avi']:
        raise HTTPException(400, "نوع الملف غير مدعوم")
    
    path = os.path.join(UPLOAD_FOLDER, f"{task_id}_{file.filename}")
    
    content = await file.read()
    with open(path, "wb") as f: 
        f.write(content)
    
    file_size = os.path.getsize(path)
    if file_size > 25 * 1024 * 1024:
        os.remove(path)
        raise HTTPException(400, "حجم الملف كبير جداً (الحد 25MB)")
    
    print(f"📤 Uploaded: {file.filename} ({file_size/1024/1024:.1f}MB) | Voice: {voice} | BG: {bg_audio_volume}")
    
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
        except Exception as e:
            print(f"DB Insert Error: {e}")
    
    gen_srt = generate_srt_file.lower() in ["true", "1", "yes"]
    
    try:
        bg_vol = float(bg_audio_volume)
        bg_vol = max(0, min(1, bg_vol))  # Clamp 0-1
    except:
        bg_vol = 0.1
    
    background_tasks.add_task(process_video_task, task_id, path, mode, target_lang, file.filename, voice, gen_srt, bg_vol)
    return TaskResponse(task_id=task_id, status="PENDING", progress=0, message="جاري المعالجة...")

@app.get("/status/{task_id}")
def status(task_id: str):
    sb = get_fresh_supabase()
    if sb:
        try:
            res = sb.table("projects").select("*").eq("id", task_id).execute()
            if res.data: 
                return res.data[0]
        except Exception as e:
            print(f"Status Error: {e}")
    return {"status": "UNKNOWN", "progress": 0, "message": ""}

async def process_video_task(task_id, video_path, mode, target_lang, filename, voice, gen_srt, bg_volume):
    try:
        base = task_id[:8]
        original_audio_path = os.path.join(AUDIO_FOLDER, f"{base}_original.mp3")
        
        video_duration = get_video_duration(video_path)
        print(f"🎬 Video duration: {video_duration:.2f}s | BG Volume: {bg_volume}")
        
        # Step 1: Extract Audio
        db_update(task_id, "EXTRACTING", 10, "استخراج الصوت...")
        if not extract_audio(video_path, original_audio_path):
            raise Exception("فشل استخراج الصوت")
        
        # Step 2: Transcribe
        db_update(task_id, "TRANSCRIBING", 25, "تحليل الكلام...")
        segments = transcribe_groq(original_audio_path)
        
        # Step 3: Translate (NATURAL Arabic) & TTS
        tts_files = []
        translated_texts = []
        total = len(segments) if segments else 1
        
        for i, seg in enumerate(segments):
            progress = 25 + int((i / total) * 45)
            
            if i % 3 == 0:
                db_update(task_id, "GENERATING_AUDIO", progress, f"دبلجة {i+1}/{total}...")
            
            # Translate to NATURAL Arabic (not formal)
            translated = translate_natural(seg.get("text", ""), target_lang)
            translated_texts.append(translated)
            
            # Generate TTS
            tts_path = os.path.join(AUDIO_FOLDER, f"tts_{base}_{i}.mp3")
            success = await generate_tts(translated, tts_path, voice)
            
            tts_files.append(tts_path if success else None)
        
        # Filter valid files
        valid_tts = [(f, s) for f, s in zip(tts_files, segments) if f and os.path.exists(f)]
        valid_files = [f for f, _ in valid_tts]
        valid_segs = [s for _, s in valid_tts]
        
        # Step 4: Create timed dubbed audio
        db_update(task_id, "MERGING", 75, "مزامنة التوقيت...")
        dubbed_audio_path = os.path.join(AUDIO_FOLDER, f"{base}_dubbed.mp3")
        create_timed_audio(valid_files, valid_segs, video_duration, dubbed_audio_path)
        
        # Step 5: Merge with background audio
        db_update(task_id, "MERGING", 85, "دمج الصوت مع الخلفية...")
        output_path = os.path.join(OUTPUT_FOLDER, f"dubbed_{base}.mp4")
        
        if bg_volume > 0 and os.path.exists(dubbed_audio_path):
            merge_audio_with_background(video_path, dubbed_audio_path, original_audio_path, output_path, bg_volume)
        else:
            # No background, just dubbed audio
            subprocess.run([
                "ffmpeg", "-y", "-i", video_path, "-i", dubbed_audio_path,
                "-c:v", "copy", "-map", "0:v:0", "-map", "1:a:0", "-shortest", output_path
            ], check=True)
        
        # Step 6: Generate SRT
        srt_url = None
        if gen_srt and segments and translated_texts:
            db_update(task_id, "GENERATING_SRT", 92, "إنشاء ملف الترجمة...")
            srt_content = generate_srt(segments, translated_texts)
            srt_path = os.path.join(OUTPUT_FOLDER, f"subtitles_{base}.srt")
            with open(srt_path, "w", encoding="utf-8") as f:
                f.write(srt_content)
            srt_url = upload_to_storage(srt_path, "videos", f"subtitles/{base}.srt", "text/plain; charset=utf-8")
        
        # Step 7: Upload video
        db_update(task_id, "UPLOADING", 95, "رفع الملف...")
        video_url = upload_to_storage(output_path, "videos", f"dubbed/final_{base}.mp4", "video/mp4")
        
        if not video_url:
            video_url = f"/output/dubbed_{base}.mp4"
        
        result = {
            "dubbed_video_url": video_url, 
            "title": filename,
            "voice": voice,
            "duration": video_duration,
            "bg_volume": bg_volume
        }
        
        if srt_url:
            result["srt_url"] = srt_url
        
        db_update(task_id, "COMPLETED", 100, "تم بنجاح! 🎉", result=result)
        
        # Cleanup
        try:
            os.remove(video_path)
            os.remove(original_audio_path)
            os.remove(dubbed_audio_path)
            for f in tts_files:
                if f and os.path.exists(f): os.remove(f)
        except: pass
        
    except Exception as e:
        print(f"🔥 FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        db_update(task_id, "FAILED", 0, f"خطأ: {str(e)[:100]}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=10000)