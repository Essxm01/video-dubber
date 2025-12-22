import os
import time
import json
import subprocess
import asyncio
import nest_asyncio
import edge_tts
from datetime import datetime
from pydub import AudioSegment
from groq import Groq
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Apply Nest Asyncio to allow nested event loops (crucial for edge-tts in sync wrappers)
nest_asyncio.apply()

# Load env
load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Init Gemini
gemini_client = None
try:
    if GEMINI_API_KEY:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
except Exception as e:
    print(f"⚠️ Gemini Init Error: {e}")

# --- HELPERS ---

def clean_text(text: str) -> str:
    """Removes hallucinations like [Music], (Sound), *Effects*."""
    import re
    text = re.sub(r"\[.*?\]", "", text)
    text = re.sub(r"\(.*?\)", "", text)
    text = re.sub(r"\*.*?\*", "", text)
    return text.strip()

def condense_text(text: str, target_seconds: float, current_est_seconds: float) -> str:
    """Uses Gemini to summarize/condense Arabic text to fit the duration."""
    if not gemini_client: return text
    
    needed_reduction = 1.0 - (target_seconds / current_est_seconds)
    if needed_reduction < 0.1: return text # Ignore small changes
    
    print(f"  📉 Condensing text (Est: {current_est_seconds:.2f}s -> Target: {target_seconds:.2f}s)...")
    
    prompt = f"""
    The following Arabic text is too long for the video segment.
    Original: "{text}"
    
    Task: Rewrite it to be significantly shorter (approx {target_seconds} seconds speaking time) while strictly preserving the core meaning.
    Use concise vocabulary. Output ONLY the shortened Arabic text.
    """
    
    try:
        resp = gemini_client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt
        )
        return resp.text.strip()
    except Exception as e:
        print(f"  ⚠️ Condense Failed: {e}")
        return text

def sanitize_audio(input_path: str, output_path: str) -> bool:
    """
    1. Resample to 44100Hz, 16-bit, Mono.
    2. Fix timestamps (aresample=async=1).
    """
    try:
        cmd = [
            "ffmpeg", "-i", input_path,
            "-af", "aresample=async=1:min_comp=0.01:first_pts=0",
            "-ac", "1", "-ar", "44100",  # Force 44.1kHz Mono
            "-y", output_path
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return True
    except Exception as e:
        print(f"Timestamp Repair Failed: {e}")
        return False

def adjust_speed(input_path: str, output_path: str, speed: float):
    """Changes audio speed using atempo filter."""
    try:
        subprocess.run(["ffmpeg", "-i", input_path, "-filter:a", f"atempo={speed}", "-vn", "-y", output_path], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except:
        return False

def generate_silence(duration_ms: int, output_path: str):
    try:
        if duration_ms <= 0: return False
        silence = AudioSegment.silent(duration=duration_ms, frame_rate=44100)
        silence = silence.set_channels(1).set_sample_width(2)
        silence.export(output_path, format="wav")
        return True
    except: return False

def extract_audio(video_path: str, audio_path: str) -> bool:
    cmd = ["ffmpeg", "-i", video_path, "-vn", "-acodec", "libmp3lame", "-ab", "128k", "-ar", "44100", "-ac", "1", "-y", audio_path]
    return subprocess.run(cmd, capture_output=True).returncode == 0

# --- STT & ENRICHMENT ---

def smart_transcribe(audio_path: str):
    segments = []
    # 1. Groq Whisper
    try:
        client = Groq(api_key=GROQ_API_KEY)
        with open(audio_path, "rb") as f:
            transcription = client.audio.transcriptions.create(
                file=(os.path.basename(audio_path), f.read()),
                model="whisper-large-v3",
                response_format="verbose_json"
            )
        
        # Parse segments and include no_speech_prob
        if hasattr(transcription, 'segments'):
            for seg in transcription.segments:
                segments.append({
                    "start": seg["start"], 
                    "end": seg["end"], 
                    "text": seg["text"].strip(), 
                    "no_speech_prob": seg.get("no_speech_prob", 0.0), # Critical for VAD
                    "emotion": "neutral"
                })
    except Exception as e:
        print(f"⚠️ Groq Failed: {e}")
        return []

    # 2. Gemini Enrichment
    if segments and gemini_client:
        try:
            gl_file = gemini_client.files.upload(file=audio_path)
            while gl_file.state.name == "PROCESSING":
                time.sleep(1)
                gl_file = gemini_client.files.get(name=gl_file.name)
            
            simplified = [{"id": i, "start": s["start"], "end": s["end"], "text": s["text"]} for i, s in enumerate(segments)]
            prompt = f"""
            Task: Listen carefully to the audio. Diarize speakers (Speaker A, Speaker B).
            CRITICAL: Identify gender based on PITCH and TONE. 
            Translate text to Professional Arabic (Fusha).
            CRITICAL: The Arabic output must be CONCISE (Short & Brief) to fit video timing.
            If the source text is an interjection (Wow, Oh, Um) or noise, keep it extremely short or ignore.
            
            Input: {json.dumps(simplified)}
            
            Output JSON: [{{ "id": 0, "ar_text": "...", "speaker": "Speaker A" }}]
            """

            response = None
            max_retries = 3
            current_model = 'gemini-2.0-flash'

            for attempt in range(max_retries):
                try:
                    response = gemini_client.models.generate_content(
                        model=current_model, 
                        contents=[prompt, gl_file],
                        config=types.GenerateContentConfig(response_mime_type="application/json")
                    )
                    break 
                except Exception as e:
                    print(f"⚠️ Enrichment Attempt {attempt+1} Error: {e}")
                    if "404" in str(e) or "NOT_FOUND" in str(e):
                        current_model = 'gemini-flash-latest'
                        time.sleep(1)
                    else:
                        time.sleep(2)

            try: gemini_client.files.delete(name=gl_file.name)
            except: pass

            if response and response.text:
                enrichment_map = {item['id']: item for item in json.loads(response.text)}
                for i, seg in enumerate(segments):
                    if i in enrichment_map:
                        data = enrichment_map[i]
                        seg['text'] = data.get('ar_text', seg['text'])
                        seg['speaker'] = data.get('speaker', 'Speaker A')
        except Exception as e:
            print(f"⚠️ Enrichment Failed: {e}")

    return segments

# --- EDGE TTS ---

async def generate_edge_tts_async(text: str, voice: str, output_path: str) -> bool:
    try:
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_path)
        return True
    except Exception as e:
        print(f"TTS Error ({voice}): {e}")
        return False

def generate_audio_edge(text: str, path: str, voice: str) -> bool:
    """Synchronous wrapper for Edge TTS."""
    try:
        asyncio.run(generate_edge_tts_async(text, voice, path))
        return os.path.exists(path) and os.path.getsize(path) > 0
    except Exception as e:
        print(f"Edge TTS Failed: {e}")
        return False

# --- PIPELINE ---

def process_segment_pipeline(video_chunk_path: str, output_chunk_path: str):
    """
    V5 Pipeline: Edge-TTS, VAD, Smart Sync.
    """
    base_name = os.path.splitext(video_chunk_path)[0]
    audio_path = f"{base_name}_source.mp3"
    
    print(f"🎤 Extracting audio: {video_chunk_path}")
    extract_audio(video_chunk_path, audio_path)
    
    # Get Video Duration
    original_video_dur = 0
    try:
        probe = subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", video_chunk_path]
        )
        original_video_dur = float(probe.decode().strip())
    except: pass

    print(f"🧠 Transcribing...")
    segments = smart_transcribe(audio_path)
    
    dubbed_files = []
    current_timeline_ms = 0
    
    for idx, seg in enumerate(segments):
        tts_raw = f"{base_name}_tts_raw_{idx}.mp3" # Edge uses MP3 usually
        tts_clean = f"{base_name}_tts_clean_{idx}.wav"
        tts_final = f"{base_name}_tts_final_{idx}.wav"
        
        text = clean_text(seg["text"])
        
        # 1. VAD / Noise Filter
        no_speech = seg.get("no_speech_prob", 0.0)
        target_dur = seg["end"] - seg["start"]
        
        if no_speech > 0.4 or not text or len(text) < 2:
            print(f"  ⏭️ Skipping Segment {idx} (No Speech Prob: {no_speech:.2f} or Empty Text)")
            # Fill with silence or original audio? 
            # Ideally original audio for background ambiance.
            # Extract original audio for this duration
            cmd = ["ffmpeg", "-i", audio_path, "-ss", str(seg["start"]), "-t", str(target_dur), "-y", tts_final]
            subprocess.run(cmd, stdout=subprocess.DEVNULL)
            sanitize_audio(tts_final, tts_final)
            dubbed_files.append(tts_final)
            current_timeline_ms += (target_dur * 1000)
            continue
            
        # 2. Voice Mapping (Dual Male)
        speaker = seg.get("speaker", "Speaker A")
        # Heuristic: Speaker B or numbers usually mean second speaker
        if "B" in speaker or "2" in str(speaker):
            voice = "ar-SA-HamedNeural"
        else:
            voice = "ar-EG-ShakirNeural"

        # 3. Smart Sync Check (Condense Loop)
        est_chars_per_sec = 13
        est_duration = len(text) / est_chars_per_sec
        
        # First check estimate vs limit
        if est_duration > (target_dur * 1.3):
             print(f"  📉 Predicted Text Too Long (Est {est_duration:.2f}s vs Max {target_dur*1.3:.2f}s). Condensing...")
             text = condense_text(text, target_dur, est_duration)
        
        print(f"  🗣️ Gen TTS ({voice}): {text[:30]}...")
        # Generate
        success = generate_audio_edge(text, tts_raw, voice)
        
        if not success:
            # Fallback to original
             print(f"  ❌ TTS Failed. Using original.")
             cmd = ["ffmpeg", "-i", audio_path, "-ss", str(seg["start"]), "-t", str(target_dur), "-y", tts_final]
             subprocess.run(cmd, stdout=subprocess.DEVNULL)
             sanitize_audio(tts_final, tts_final)
             dubbed_files.append(tts_final)
             current_timeline_ms += (target_dur * 1000)
             continue
             
        # Sanitize to 44.1k WAV
        sanitize_audio(tts_raw, tts_clean)
        
        # Verify Duration
        tts_audio = AudioSegment.from_file(tts_clean)
        tts_dur_ms = len(tts_audio)
        target_dur_ms = target_dur * 1000.0
        
        # Gap handling (Start of segment vs timeline)
        start_gap_ms = (seg["start"] * 1000.0) - current_timeline_ms
        if start_gap_ms > 100:
            sil_path = f"{base_name}_sil_{idx}.wav"
            generate_silence(int(start_gap_ms), sil_path)
            dubbed_files.append(sil_path)
            current_timeline_ms += start_gap_ms
            
        ratio = tts_dur_ms / target_dur_ms if target_dur_ms > 0 else 1.0
        
        if ratio <= 1.0:
            dubbed_files.append(tts_clean)
            current_timeline_ms += tts_dur_ms
        elif ratio <= 1.25:
            print(f"  ⚡ Speeding up {ratio:.2f}x")
            adjust_speed(tts_clean, tts_final, ratio)
            dubbed_files.append(tts_final)
            current_timeline_ms += target_dur_ms
        else:
            # > 1.25x (even after condense attempts?)
            # Cap speed at 1.25x and STRETCH VIDEO later
            print(f"  🐢 Ratio {ratio:.2f}x. Capping speed & Will Stretch Video.")
            adjust_speed(tts_clean, tts_final, 1.25)
            dubbed_files.append(tts_final)
            # New duration
            new_dur = tts_dur_ms / 1.25
            current_timeline_ms += new_dur
            
        # Cleanup temp
        for p in [tts_raw]:
            if os.path.exists(p): os.remove(p)

    # 4. Merge
    if dubbed_files:
        concat_list = f"{base_name}_concat.txt"
        with open(concat_list, "w") as f:
            for d in dubbed_files: f.write(f"file '{os.path.abspath(d)}'\n")
            
        merged_wav = f"{base_name}_merged.wav"
        subprocess.run(["ffmpeg", "-f", "concat", "-safe", "0", "-i", concat_list, "-c", "copy", "-y", merged_wav], stdout=subprocess.DEVNULL)
        
        # 5. Video Stretch Logic
        audio_len_ms = len(AudioSegment.from_file(merged_wav))
        video_len_ms = original_video_dur * 1000.0
        final_video_input = video_chunk_path
        
        if audio_len_ms > (video_len_ms + 200): # Tolerance
            stretch_ratio = audio_len_ms / video_len_ms
            # Limit stretch? If > 1.5x, maybe panic? 
            # User said "Video Stretch (Slow-Mo)". 
            print(f"  🕰️ Extending Video by {stretch_ratio:.2f}x...")
            stretched_video = f"{base_name}_stretched.mp4"
            cmd = [
                "ffmpeg", "-i", video_chunk_path,
                "-filter:v", f"setpts={stretch_ratio}*PTS",
                "-r", "24",
                "-y", stretched_video
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, check=True)
            final_video_input = stretched_video
            
        # 6. Mux
        cmd = [
            "ffmpeg", "-y",
            "-i", final_video_input,
            "-i", merged_wav,
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-shortest",
            output_chunk_path
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, check=True)
        
        # Cleanup
        try:
            os.remove(concat_list)
            os.remove(merged_wav)
            if final_video_input != video_chunk_path: os.remove(final_video_input)
        except: pass
        
    else:
         subprocess.run(["ffmpeg", "-i", video_chunk_path, "-c", "copy", output_chunk_path], check=True)

    for f in dubbed_files: 
        if os.path.exists(f): 
            try: os.remove(f)
            except: pass
    if os.path.exists(audio_path): os.remove(audio_path)
