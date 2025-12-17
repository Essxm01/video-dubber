"""
Arab Dubbing API - Version 19.0 (Google Cloud TTS / Gemini)
- TTS: Google Cloud TTS (Neural/Wavenet) → Edge TTS (Fallback)
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
from datetime import datetime
from dotenv import load_dotenv
from groq import Groq
from deep_translator import GoogleTranslator
from pydub import AudioSegment
import math

# Load environment variables
load_dotenv()

# Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")  # Uses Google Cloud TTS API Key
AZURE_SPEECH_KEY = os.getenv("AZURE_SPEECH_KEY", "")
AZURE_SPEECH_REGION = os.getenv("AZURE_SPEECH_REGION", "westeurope")

app = FastAPI(title="Arab Dubbing API", version="19.0.0")

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
    return {"status": "active", "version": "19.0.0", "engine": "Groq + Google Cloud TTS (Gemini)"}

# --- LOCAL TASK STORAGE (reliable fallback) ---
LOCAL_TASKS = {}

# --- HELPERS ---
def get_fresh_supabase():
    try:
        from supabase import create_client
        if SUPABASE_URL and SUPABASE_KEY:
            return create_client(SUPABASE_URL, SUPABASE_KEY)
        return None
    except: return None

def db_update(task_id: str, status: str, progress: int, message: str, result: dict = None):
    data = {"status": status, "progress": progress, "message": message, "updated_at": datetime.now().isoformat()}
    if result: data["result"] = result
    
    # Always update local storage (reliable)
    if task_id not in LOCAL_TASKS:
        LOCAL_TASKS[task_id] = {}
    LOCAL_TASKS[task_id].update(data)
    print(f"📊 {status} {progress}%: {message}")
    
    # Also try Supabase
    try:
        sb = get_fresh_supabase()
        if sb:
            sb.table("projects").update(data).eq("id", task_id).execute()
    except: pass

def upload_to_storage(file_path: str, bucket: str, dest_name: str, content_type: str) -> str:
    try:
        sb = get_fresh_supabase()
        if not sb: return None
        
        # Ensure bucket exists
        buckets = sb.storage.list_buckets()
        bucket_exists = any(b.name == bucket for b in buckets)
        if not bucket_exists:
            try: sb.storage.create_bucket(bucket, options={"public": False})
            except: pass

        with open(file_path, "rb") as f:
            sb.storage.from_(bucket).upload(path=dest_name, file=f.read(), file_options={"content-type": content_type, "upsert": "true"})
        
        # Use Signed URL (valid for 10 years ~ 315360000s) to avoid private bucket issues
        # Public URL often fails if bucket is not explicitly set to Public
        res = sb.storage.from_(bucket).create_signed_url(dest_name, 315360000)
        
        # Handle dict response (Supabase Python client returns {'signedURL': '...'})
        if isinstance(res, dict) and "signedURL" in res:
            return res["signedURL"]
        return res
    except Exception as e:
        print(f"Server Upload Error: {e}")
        return None

def extract_audio(video_path: str, audio_path: str) -> bool:
    cmd = ["ffmpeg", "-i", video_path, "-vn", "-acodec", "libmp3lame", "-ab", "64k", "-ar", "16000", "-y", audio_path]
    return subprocess.run(cmd, capture_output=True).returncode == 0

def get_video_duration(video_path: str) -> float:
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", video_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return float(result.stdout.strip())
    except: return 0.0

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

import google.generativeai as genai

# Configure Gemini for Translation
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    try:
        # DEBUG: List available models to check permission/version issues
        print("🔍 Checking available Gemini models...")
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(f"   - {m.name}")
    except Exception as e:
        print(f"⚠️ Failed to list Gemini models: {e}")

# 2. TRANSLATION (Strict Egyptian Slang)
def translate_text(text: str, target_lang: str = "ar") -> str:
    if not text.strip(): return ""
    
    # We prefer the flash model for speed, but fallback to pro/standard if needed
    # Update: Prioritizing 'latest' and '2.0' models confirmed to be available in production logs
    models_to_try = [
        'gemini-2.0-flash', 
        'gemini-flash-latest', 
        'gemini-pro-latest', 
        'gemini-1.5-flash', 
        'gemini-1.5-pro'
    ]
    
    for model_name in models_to_try:
        try:
            model = genai.GenerativeModel(model_name)
            
            # STRICT PROMPT: Modern Standard Arabic (Fusha)
            prompt = f"""
            Task: Translate the following English text to **Modern Standard Arabic (Fusha)**.
            
            Input Text: "{text}"
            
            CRITICAL RULES:
            1. Output **ONLY** the translated Arabic text.
            2. Use correct, formal vocabulary (e.g., "الحافلة" not "الأتوبيس", "جداً" not "أوي").
            3. Ensure professional sentence structure suitable for a documentary or news broadcast.
            4. NO "Here is the translation" or metadata.
            5. Do not wrap output in quotes.
            """
            
            response = model.generate_content(prompt)
            if response and response.text:
                # Clean up any potential leakage
                clean_text = response.text.strip().replace('"', '').replace("`", "").split('\n')[0]
                print(f"🇸🇦 Gemini Fusha: {clean_text}")
                return clean_text
                
        except Exception as e:
            print(f"⚠️ Gemini Error ({model_name}): {e}")
            continue

    # Fallback
    try:
        from deep_translator import GoogleTranslator
        return GoogleTranslator(source='auto', target=target_lang).translate(text)
    except: return text

# 3. TTS (Gemini Native Audio with Acting Cues -> Fallback Edge TTS)
# 3. TTS (Gemini Native Audio with Acting Cues -> Fallback Edge TTS)
def generate_audio_gemini(text: str, path: str) -> bool:
    if not text.strip(): return False
    
    # Ensure API Key is loaded
    if not GEMINI_API_KEY:
        print("⚠️ Gemini Key missing for TTS.")
        return False

    try:
        # CRITICAL: Use Gemini 2.0 Flash Experimental for Native Audio
        model = genai.GenerativeModel("gemini-2.0-flash-exp")
        
        print(f"💎 Gemini 2.0 TTS: Narrating in Fusha -> {text[:20]}...")
        
        # PROMPT FOR FUSHA VOICE ACTING
        prompt = f"""
        Act as a professional Arabic Documentary Narrator.
        Generate spoken audio for the provided text.
        
        RULES:
        1. **Language:** strict Modern Standard Arabic (Fusha).
        2. **Tone:** Deep, warm, and professional.
        3. **Performance:** Read with feeling. If you see [sad], sound sad. If [excited], sound excited.
        
        Input Text:
        "{text}"
        """
        
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                response_mime_type="audio/mp3"
            )
        )
        
        # Save the audio
        with open(path, "wb") as f:
            f.write(response.parts[0].inline_data.data)
            
        print("✅ Gemini 2.0 Success!")
        return True

    except Exception as e:
        print(f"⚠️ Gemini 2.0 Audio Failed: {e}")
        
    # Fallback to Azure TTS (High Quality)
    if AZURE_SPEECH_KEY:
        try:
            print("🔄 Fallback: Azure TTS (High Quality)...")
            import azure.cognitiveservices.speech as speechsdk
            
            speech_config = speechsdk.SpeechConfig(
                subscription=AZURE_SPEECH_KEY, 
                region=AZURE_SPEECH_REGION
            )
            # Use high-quality Arabic Neural voice
            speech_config.speech_synthesis_voice_name = "ar-EG-ShakirNeural"
            speech_config.set_speech_synthesis_output_format(
                speechsdk.SpeechSynthesisOutputFormat.Audio16Khz32KBitRateMonoMp3
            )
            
            clean_text = text.replace("[whispering]", "").replace("[excited]", "").replace("[sad]", "").replace("[sigh]", "")
            
            audio_config = speechsdk.audio.AudioOutputConfig(filename=path)
            synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)
            
            result = synthesizer.speak_text_async(clean_text).get()
            
            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                print("✅ Azure TTS Success!")
                return True
            else:
                print(f"⚠️ Azure TTS Failed: {result.reason}")
        except Exception as e:
            print(f"❌ Azure TTS Error: {e}")
    
    print("❌ All TTS methods failed")
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
    # First check local storage (most reliable)
    if task_id in LOCAL_TASKS:
        return {"id": task_id, **LOCAL_TASKS[task_id]}
    
    # Then try Supabase
    try:
        sb = get_fresh_supabase()
        if sb:
            res = sb.table("projects").select("*").eq("id", task_id).execute()
            if res.data: return res.data[0]
    except: pass
    
    return {"status": "UNKNOWN"}

def generate_srt_content(segments, translated_texts):
    srt_content = ""
    for i, (seg, trans) in enumerate(zip(segments, translated_texts)):
        start_time = format_timestamp(seg['start'])
        end_time = format_timestamp(seg['end'])
        srt_content += f"{i+1}\n{start_time} --> {end_time}\n{trans}\n\n"
    return srt_content

def format_timestamp(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"

async def process_video_task(task_id, video_path, mode, target_lang, filename):
    try:
        base = task_id[:8]
        audio_path = os.path.join(AUDIO_FOLDER, f"{base}.mp3")
        
        db_update(task_id, "EXTRACTING", 10, "استخراج الصوت...")
        extract_audio(video_path, audio_path)
        
        # Get Video Duration for final sync
        original_video_duration = get_video_duration(video_path)
        
        db_update(task_id, "TRANSCRIBING", 20, "تحليل الكلام...")
        segments = smart_transcribe(audio_path)
        
        if not segments:
            db_update(task_id, "FAILED", 0, "فشل تحليل الكلام")
            return

        # -------------------------------------------
        # MODE 1: TRANSLATION (Subtitles Only)
        # -------------------------------------------
        if mode == "TRANSLATION":
            translated_texts = []
            total = len(segments)
            
            for i, seg in enumerate(segments):
                progress = 20 + int((i / total) * 60)
                if i % 5 == 0: db_update(task_id, "TRANSLATING", progress, f"ترجمة النصوص {i+1}/{total}...")
                translated_texts.append(translate_text(seg["text"], target_lang))
            
            # Generate SRT
            srt_content = generate_srt_content(segments, translated_texts)
            srt_path = os.path.join(OUTPUT_FOLDER, f"subs_{base}.srt")
            with open(srt_path, "w", encoding="utf-8") as f:
                f.write(srt_content)
                
            db_update(task_id, "BURNING_SUBS", 90, "دمج الترجمة مع الفيديو...")
            output_path = os.path.join(OUTPUT_FOLDER, f"subtitled_{base}.mp4")
            
            # Burn Subtitles (Hardsub)
            # Note: For strict Arabic handling, this depends on ffmpeg build. 
            # Simple force_style for font size and alignment.
            # Using absolute path for subtitles filter is safer.
            abs_srt = os.path.abspath(srt_path).replace("\\", "/").replace(":", "\\:")
            
            subprocess.run([
                "ffmpeg", "-y",
                "-i", video_path,
                "-vf", f"subtitles='{abs_srt}':force_style='FontName=Arial,FontSize=24,Alignment=2,Outline=1,Shadow=1'",
                "-c:a", "copy",
                output_path
            ], check=True)
            
            db_update(task_id, "UPLOADING", 95, "رفع النتيجة...")
            url = upload_to_storage(output_path, "videos", f"subtitled/final_{base}.mp4", "video/mp4")
            
            db_update(task_id, "COMPLETED", 100, "تم بنجاح! 🎉", result={"dubbed_video_url": url, "title": filename})
            
            # Cleanup
            try:
                os.remove(video_path)
                os.remove(audio_path)
                os.remove(srt_path)
            except: pass
            return

        # -------------------------------------------
        # MODE 2: DUBBING (Original Logic)
        # -------------------------------------------
        
        # Initialize Master Audio Track (pydub)
        master_audio = AudioSegment.silent(duration=0)
        
        print("⏳ Starting Smart Sync processing...")
        total = len(segments)
        
        for i, segment in enumerate(segments):
            progress = 20 + int((i / total) * 60)
            
            if i % 2 == 0:
                db_update(task_id, "GENERATING_AUDIO", progress, f"توليد الصوت البشري والمزامنة {i+1}/{total}...")
            
            # 1. Translate
            translated = translate_text(segment["text"], target_lang)
            
            # 2. TTS Generation (Temp File)
            temp_file = os.path.join(AUDIO_FOLDER, f"temp_{base}_{i}.mp3")
            generate_audio_gemini(translated, temp_file)
            
            # 3. Load Audio Segment
            start_time_ms = int(segment['start'] * 1000)
            end_time_ms = int(segment['end'] * 1000)
            original_duration_ms = end_time_ms - start_time_ms
            
            if os.path.exists(temp_file) and os.path.getsize(temp_file) > 100:
                segment_audio = AudioSegment.from_file(temp_file)
            else:
                # If TTS failed, add silence for the duration to maintain sync
                segment_audio = AudioSegment.silent(duration=original_duration_ms)

            # --- SYNCHRONIZATION LOGIC ---
            
            # 1. Handle Gaps (Silence before this sentence)
            current_master_duration = len(master_audio)
            gap_duration = start_time_ms - current_master_duration
            
            if gap_duration > 0:
                # Add silence to sync with the video start time
                master_audio += AudioSegment.silent(duration=gap_duration)
            
            # 2. Append Audio
            master_audio += segment_audio
            
            # Clean up temp file
            try:
                os.remove(temp_file)
            except: pass
            
        # Final Padding to match video duration
        video_duration_ms = int(original_video_duration * 1000)
        current_total = len(master_audio)

        if current_total < video_duration_ms:
            master_audio += AudioSegment.silent(duration=video_duration_ms - current_total)

        # Export Final Audio
        merged_audio_path = os.path.join(AUDIO_FOLDER, f"merged_dubbed_{base}.mp3")
        master_audio.export(merged_audio_path, format="mp3")
        print("✅ Smart Audio Timeline created with Synchronization.")
            
        db_update(task_id, "MERGING", 90, "دمج الفيديو...")
        output_path = os.path.join(OUTPUT_FOLDER, f"dubbed_{base}.mp4")
        
        # Merge using FFmpeg (Simple audio replace since we have a full track now)
        subprocess.run([
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", merged_audio_path,
            "-c:v", "copy",
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-shortest",
            output_path
        ], check=True)
        
        db_update(task_id, "UPLOADING", 95, "رفع النتيجة...")
        url = upload_to_storage(output_path, "videos", f"dubbed/final_{base}.mp4", "video/mp4")
        
        if not url:
            # If upload fails, try to fallback to local URL (for inspection) but warn
            print("⚠️ Upload failed, falling back to local URL")
            url = f"/output/{os.path.basename(output_path)}"
            if not os.path.exists(output_path):
                 raise Exception("فشل رفع الملف إلى السحابة (Supabase Storage Failed)")

        db_update(task_id, "COMPLETED", 100, "تم بنجاح! 🎉", result={"dubbed_video_url": url, "title": filename})
        
        # Cleanup (ONLY if upload successful to keep local debug file)
        if url.startswith("http"):
             try:
                os.remove(video_path)
                os.remove(audio_path)
                os.remove(merged_audio_path)
                # os.remove(output_path) # Keep output for now just in case
             except: pass
            
    except Exception as e:
        print(f"🔥 FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        db_update(task_id, "FAILED", 0, f"خطأ: {str(e)[:100]}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=10000)