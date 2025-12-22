import os
import time
import json
import subprocess
from datetime import datetime
from pydub import AudioSegment
from groq import Groq
from google import genai
from google.genai import types
import azure.cognitiveservices.speech as speechsdk
from dotenv import load_dotenv

# Load env
load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
AZURE_SPEECH_KEY = os.getenv("AZURE_SPEECH_KEY", "")
AZURE_SPEECH_REGION = os.getenv("AZURE_SPEECH_REGION", "westeurope")

# Init Gemini
gemini_client = None
try:
    if GEMINI_API_KEY:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
except Exception as e:
    print(f"⚠️ Gemini Init Error: {e}")

# --- HELPERS ---
def discover_best_gemini_model(client):
    # Fallback to a known stable model if dynamic discovery fails
    return 'gemini-2.0-flash' 

def is_speech(audio_path: str, silence_threshold=-40.0, min_duration=0.5) -> bool:
    """
    Simple VAD: Checks if audio has enough energy to be speech.
    Prevents translating mute/noise segments.
    """
    try:
        audio = AudioSegment.from_file(audio_path)
        if len(audio) < (min_duration * 1000):
            return False
        if audio.dBFS < silence_threshold:
            return False
        return True
    except:
        return True # Fallback to processing if check fails 

from google.api_core.exceptions import ResourceExhausted

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
        if hasattr(transcription, 'segments'):
            for seg in transcription.segments:
                segments.append({
                    "start": seg["start"], "end": seg["end"], "text": seg["text"].strip(), "emotion": "neutral"
                })
    except Exception as e:
        print(f"⚠️ Groq Failed: {e}")
        return []

    # 2. Gemini Enrichment (Speaker/Gender/Emotion)
    if segments and gemini_client:
        try:
            # DEBUG: Check Library Version and Available Models
            import google.generativeai as genai_debug
            try:
                print(f"DEBUG: Google GenAI Library Version: {genai_debug.__version__}")
                print("DEBUG: Listing Available Models...")
                for m in genai_debug.list_models():
                    if 'generateContent' in m.supported_generation_methods:
                        print(f"   - Found Model: {m.name}")
            except Exception as e:
                print(f"DEBUG: Could not list models: {e}")

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
            Use shorter synonyms where possible without losing meaning. 
            Detect Emotion (happy, sad, neutral, excited).
            
            Input: {json.dumps(simplified)}
            
            Output JSON: [{{ "id": 0, "ar_text": "...", "emotion": "neutral", "gender": "Male", "speaker": "Speaker A" }}]
            """

            # Retry Logic for Quota (429) and Model Not Found (404)
            # from google.api_core.exceptions import NotFound # Removing specific import if not reliable

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
                    break # Success
                except ResourceExhausted:
                    wait_time = (attempt + 1) * 10
                    print(f"⚠️ Quota hit (429). Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                except Exception as e:
                    error_str = str(e)
                    print(f"⚠️ Enrichment Attempt {attempt+1} Error: {error_str}")
                    
                    # 🚨 CRITICAL SWITCH: If Flash fails (404), switch to Pro immediately
                    if "404" in error_str or "NOT_FOUND" in error_str:
                        print(f"🔄 Model '{current_model}' caused 404. Switching to 'gemini-flash-latest' for next attempt.")
                        current_model = 'gemini-flash-latest'
                        time.sleep(1)
                        continue # Retry immediately
                    
                    time.sleep(2)

            try: gemini_client.files.delete(name=gl_file.name)
            except: pass

            if response and response.text:
                enrichment_map = {item['id']: item for item in json.loads(response.text)}
                for i, seg in enumerate(segments):
                    if i in enrichment_map:
                        data = enrichment_map[i]
                        seg['text'] = data.get('ar_text', seg['text'])
                        seg['emotion'] = data.get('emotion', 'neutral')
                        seg['gender'] = data.get('gender', 'Male')
                        seg['speaker'] = data.get('speaker', 'Speaker A')
        except Exception as e:
            print(f"⚠️ Enrichment Failed: {e}")

    return optimize_segments_for_flow(segments)

def optimize_segments_for_flow(segments, gap_threshold=0.75, max_chars=280):
    if not segments: return []
    optimized = []
    current = segments[0].copy()
    for next_seg in segments[1:]:
        gap = next_seg["start"] - current["end"]
        if gap < gap_threshold and (len(current["text"]) + len(next_seg["text"])) < max_chars and current.get("speaker") == next_seg.get("speaker"):
            current["text"] += " " + next_seg["text"]
            current["end"] = next_seg["end"]
        else:
            optimized.append(current)
            current = next_seg.copy()
    optimized.append(current)
    return optimized

def clean_text(text: str) -> str:
    """Removes hallucinations like [Music], (Sound), *Effects*."""
    import re
    # Remove [...] (...) *...*
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
        # ffmpeg filter: aresample=async=1:min_comp=0.01:first_pts=0
        # -ac 1 (Mono), -ar 44100 (Sample Rate), -acodec pcm_s16le (WAV standard)
        cmd = [
            "ffmpeg", "-i", input_path,
            "-af", "aresample=async=1:min_comp=0.01:first_pts=0",
            "-ac", "1", "-ar", "44100", "-c:a", "pcm_s16le",
            "-y", output_path
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return True
    except Exception as e:
        print(f"Timestamp Repair Failed: {e}")
        return False

# --- TTS & MERGING ---
def generate_audio_gemini(text: str, path: str, emotion: str = "neutral", voice_name: str = "ar-EG-ShakirNeural") -> bool:
    # 1. Generate SSML
    ssml = None
    if gemini_client:
        try:
            resp = gemini_client.models.generate_content(
                model='gemini-2.0-flash',
                contents=f"Convert to SSML for Azure TTS (ar-EG-ShakirNeural). Emotion: {emotion}. Text: {text}. Output only SSML."
            )
            val = resp.text.replace("```xml", "").replace("```", "").strip()
            if val.startswith("<speak"): ssml = val
        except: pass

    # 2. Azure TTS
    try:
        speech_config = speechsdk.SpeechConfig(subscription=AZURE_SPEECH_KEY, region=AZURE_SPEECH_REGION)
        speech_config.speech_synthesis_voice_name = voice_name
        # Fix 3: Request Native 44.1kHz from Azure (Highest Quality)
        speech_config.set_speech_synthesis_output_format(speechsdk.SpeechSynthesisOutputFormat.Riff44100Hz16BitMonoPcm)
        
        audio_config = speechsdk.audio.AudioOutputConfig(filename=path)
        synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)
        
        if ssml:
            res = synthesizer.speak_ssml_async(ssml).get()
        else:
            res = synthesizer.speak_text_async(text).get()
            
        return res.reason == speechsdk.ResultReason.SynthesizingAudioCompleted
    except Exception as e:
        print(f"TTS Error: {e}")
        return False

def generate_silence(duration_ms: int, output_path: str):
    """Generates a silent audio file of specific duration."""
    try:
        # Fix 3: DTS/Sample Rate Mismatch. Force 44100Hz, 16-bit, Mono.
        silence = AudioSegment.silent(duration=duration_ms, frame_rate=44100)
        silence = silence.set_channels(1).set_sample_width(2)
        silence.export(output_path, format="wav")
        return True
    except Exception as e:
        print(f"⚠️ Silence Gen Error: {e}")
        return False


def extract_audio(video_path: str, audio_path: str) -> bool:
    # Fix 2: Force 44100Hz to prevent sample rate mismatch distortion
    cmd = ["ffmpeg", "-i", video_path, "-vn", "-acodec", "libmp3lame", "-ab", "128k", "-ar", "44100", "-ac", "1", "-y", audio_path]
    return subprocess.run(cmd, capture_output=True).returncode == 0


def merge_audio_video(video_path, audio_files, output_path):
    # 1. Create concat list
    list_file = f"{output_path}.list.txt"
    with open(list_file, "w") as f:
        for a in audio_files: 
            if os.path.exists(a): f.write(f"file '{os.path.abspath(a)}'\n")
    
    # 2. Concat audio (Output to WAV first to allow stream copying from WAV inputs)
    merged_audio = f"{output_path}.temp.wav" 
    # Inputs are .wav (pcm_s16le), output is .wav, so -c copy works.
    subprocess.run(["ffmpeg", "-f", "concat", "-safe", "0", "-i", list_file, "-c", "copy", "-y", merged_audio], check=True, stdout=subprocess.DEVNULL)
    
    # 3. Merge with video
    # Encode audio to aac for mp4 compatibility
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", merged_audio,
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "128k", # Encode WAV -> AAC
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-shortest",
        output_path
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
    
    # Cleanup
    try:
        os.remove(list_file)
        os.remove(merged_audio)
    except: pass

def adjust_speed(input_path: str, output_path: str, speed: float):
    """Changes audio speed using atempo filter."""
    try:
        # ffmpeg atempo filter: 0.5 to 2.0 (we limit to 1.25)
        subprocess.run(["ffmpeg", "-i", input_path, "-filter:a", f"atempo={speed}", "-vn", "-y", output_path], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except:
        return False

# --- MAIN PIPELINE FUNCTION ---
def process_segment_pipeline(video_chunk_path: str, output_chunk_path: str):
    """
    V3 Pipeline: Smart Adaptation (Text Condensation + Video Stretching).
    """
    base_name = os.path.splitext(video_chunk_path)[0]
    audio_path = f"{base_name}_source.mp3"
    
    print(f"🎤 Extracting audio: {video_chunk_path}")
    extract_audio(video_chunk_path, audio_path)
    
    # 1. Get Duration from Video
    original_video_dur = 0
    try:
        probe = subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", video_chunk_path]
        )
        original_video_dur = float(probe.decode().strip())
    except:
        pass # Fallback to segments logic if needed, but video duration is best truth

    print(f"🧠 Transcribing & Translating...")
    segments = smart_transcribe(audio_path)
    
    dubbed_files = []
    
    # ELASTIC SYNCING STATE
    current_timeline_ms = 0
    
    # We process assuming a linear flow. For V3, we strictly process 1 segment = 1 TTS.
    # If segments overlap or are fragmented, 'optimize_segments_for_flow' usually handles it.
    # Here we simplify: The *Entire Chunk* corresponds to the sum of segments.
    # But usually 'video_chunk_path' IS one segment from the main loop. 
    # Let's assume the input video_chunk_path is the VISUAL segment corresponding to these audio segments.
    
    # Actually, often 'smart_transcribe' returns multiple sentences for one video chunk?
    # No, 'process_segment_pipeline' is called per visual segment. 
    # STARTING ASSUMPTION: The input video chunk is ONE continuous timeline that needs ONE continuous audio track.
    # We will concat the TTS results.
    
    final_audio_track = f"{base_name}_full_track.wav"
    
    for idx, seg in enumerate(segments):
        tts_raw = f"{base_name}_tts_raw_{idx}.wav"
        tts_clean = f"{base_name}_tts_clean_{idx}.wav"
        tts_final = f"{base_name}_tts_final_{idx}.wav"
        
        text = clean_text(seg["text"])
        if not text or len(text) < 2:
            print(f"  ⏭️ Skipping empty/short segment {idx}")
            continue

        # 0. Smart Condensation
        # Est. Duration: ~13 chars per second for Arabic
        est_chars_per_sec = 13
        est_duration = len(text) / est_chars_per_sec
        
        # Target: This segment's duration in the video?
        # Since we just have 'segments' from 'smart_transcribe' which uses the audio source,
        # the 'seg["end"] - seg["start"]' IS the target duration if we want to match original pacing.
        target_dur = seg["end"] - seg["start"]
        
        # Limit: We can accept up to 1.25x speed. So raw text can be 1.25x longer than target.
        max_acceptable_dur = target_dur * 1.25
        
        if est_duration > max_acceptable_dur:
            text = condense_text(text, target_dur, est_duration)
            
        # 1. Generate Raw TTS
        # V4: Dual Male Voice Logic
        gender = seg.get("gender", "Male")
        speaker = seg.get("speaker", "Speaker A")
        
        if gender == "Male":
            if "B" in speaker: voice = "ar-SA-HamedNeural" # Distinct Male
            else: voice = "ar-EG-ShakirNeural" # Default Male
        else:
            voice = "ar-EG-SalmaNeural" # Female

        print(f"  🗣️ Gen TTS ({voice}): {text[:30]}...")
        time.sleep(2) # Anti-rate limit
        
        success = generate_audio_gemini(text, tts_raw, seg.get("emotion", "neutral"), voice)
        
        if not success or not os.path.exists(tts_raw):
            print(f"  ❌ TTS Failed. Using original audio fallback.")
            # Fallback code
            cmd = ["ffmpeg", "-i", audio_path, "-ss", str(seg["start"]), "-t", str(target_dur), "-y", tts_final]
            subprocess.run(cmd, stdout=subprocess.DEVNULL)
            sanitize_audio(tts_final, tts_final) # Ensure 44.1k
            dubbed_files.append(tts_final)
            current_timeline_ms += (target_dur * 1000)
            continue

        # 2. Sanitize (44.1kHz & DTS Fix)
        sanitize_audio(tts_raw, tts_clean)
        
        # 3. Check Duration & Stretch
        tts_audio = AudioSegment.from_file(tts_clean)
        tts_dur_ms = len(tts_audio)
        target_dur_ms = target_dur * 1000.0
        
        # Calculate needed silences or speedups
        # Logic: We want to match 'target_dur'.
        
        # Gap handling: If this segment doesn't start immediately after previous, insert silence used in original
        start_gap_ms = (seg["start"] * 1000.0) - current_timeline_ms
        if start_gap_ms > 100:
            sil_path = f"{base_name}_sil_{idx}.wav"
            generate_silence(int(start_gap_ms), sil_path)
            dubbed_files.append(sil_path)
            current_timeline_ms += start_gap_ms

        ratio = tts_dur_ms / target_dur_ms if target_dur_ms > 0 else 1.0
        
        if ratio <= 1.0:
            # TTS is shorter. Use it.
            dubbed_files.append(tts_clean)
            current_timeline_ms += tts_dur_ms
        elif ratio <= 1.25:
            # Speed up
            print(f"  ⚡ Speeding up {ratio:.2f}x")
            adjust_speed(tts_clean, tts_final, ratio)
            # Verify sanitize again? 'adjust_speed' uses simple filter. Ideally sanitize after? 
            # But adjust_speed uses ffmpeg, so let's trust it for now or just ensure rate.
            dubbed_files.append(tts_final)
            current_timeline_ms += target_dur_ms # We squashed it to fit target
        else:
            # > 1.25x. Even with condensation loop, it might happen.
            # Strategy: Max speed 1.25x, then STRETCH video.
            print(f"  🐢 Ratio {ratio:.2f}x > 1.25. Capping audio speed & Stretching Video.")
            
            # 1. Speed audio to max 1.25x
            adjust_speed(tts_clean, tts_final, 1.25)
            dubbed_files.append(tts_final)
            
            # New audio duration = Old / 1.25
            new_audio_ms = tts_dur_ms / 1.25
            
            # The 'overflow' ms that we need to extend the video by
            overflow_ms = new_audio_ms - target_dur_ms
            
            # We can't stretch strictly *per segment* easily in extensive merge flow unless we split video.
            # BUT: This function 'process_segment_pipeline' operates on a 'video_chunk_path'.
            # If 'video_chunk_path' represents JUST this sentence (which is how segments logic in main.py works), then we CAN stretch the whole video chunk!
            
            # However, prompt implies 'segments' is a list.
            # If the chunk contains multiple sentences, stretching local video parts is complex (VFR).
            # FALLBACK SIMPLIFIED: If ANY segment pushes duration, we might desync later segments if we don't handle carefully.
            # Easiest Robust approach: Just let the audio push the timeline. 
            # AND at the end, if Total Audio > Total Video, we slow down the VIDEO.
            
            current_timeline_ms += new_audio_ms

        # Cleanup
        for p in [tts_raw]:
            if os.path.exists(p): os.remove(p)

    # 4. Merge All Audio
    if dubbed_files:
        concat_list = f"{base_name}_concat.txt"
        with open(concat_list, "w") as f:
            for d in dubbed_files: f.write(f"file '{os.path.abspath(d)}'\n")
            
        merged_wav = f"{base_name}_merged.wav"
        subprocess.run(["ffmpeg", "-f", "concat", "-safe", "0", "-i", concat_list, "-c", "copy", "-y", merged_wav], stdout=subprocess.DEVNULL)
        
        # 5. Final Sync Check (Video Stretch Logic)
        audio_len_ms = len(AudioSegment.from_file(merged_wav))
        video_len_ms = original_video_dur * 1000.0
        
        final_video_input = video_chunk_path
        
        if audio_len_ms > (video_len_ms + 100): # Tolerance 100ms
            stretch_ratio = audio_len_ms / video_len_ms
            print(f"  🕰️ Extending Video by {stretch_ratio:.2f}x to match Audio...")
            
            stretched_video = f"{base_name}_stretched.mp4"
            # setpts = PTS * Ratio (slowing down increases PTS)
            # We verify the audio sample rate here too: -ar 44100
            cmd = [
                "ffmpeg", "-i", video_chunk_path,
                "-filter:v", f"setpts={stretch_ratio}*PTS",
                "-r", "24", # Maintain framerate
                "-y", stretched_video
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, check=True)
            final_video_input = stretched_video
            
        # 6. Mux
        cmd = [
            "ffmpeg", "-y",
            "-i", final_video_input,
            "-i", merged_wav,
            "-c:v", "copy", # Should work if we stretched to a temp file
            "-c:a", "aac", "-b:a", "192k", "-ar", "44100", # High Quality Audio
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-shortest",
            output_chunk_path
        ]
        # If we stretched, the video determines length. -shortest is safe.
        subprocess.run(cmd, stdout=subprocess.DEVNULL, check=True)
        
        # Cleanup
        try:
            os.remove(concat_list)
            os.remove(merged_wav)
            if final_video_input != video_chunk_path: os.remove(final_video_input)
        except: pass
        
    else:
        # Fallback copy
        subprocess.run(["ffmpeg", "-i", video_chunk_path, "-c", "copy", output_chunk_path], check=True)
    
    # Final Cleanup
    for f in dubbed_files: 
        if os.path.exists(f): 
            try: os.remove(f)
            except: pass
    if os.path.exists(audio_path): os.remove(audio_path)
