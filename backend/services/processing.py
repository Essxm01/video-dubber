import os
import time
import json
import subprocess
from datetime import datetime
from pydub import AudioSegment
from groq import Groq
from google import genai
from google.genai import types
from dotenv import load_dotenv
import azure.cognitiveservices.speech as speechsdk

# Load env variables (Render provides these)
load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
AZURE_SPEECH_KEY = os.getenv("AZURE_SPEECH_KEY", "") or os.getenv("SPEECH_KEY", "")
AZURE_SPEECH_REGION = os.getenv("AZURE_SPEECH_REGION", "") or os.getenv("SPEECH_REGION", "")

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
            
            Output JSON: [{{ "id": 0, "ar_text": "...", "speaker": "Speaker A", "emotion": "neutral" }}]
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
                        seg['emotion'] = data.get('emotion', 'neutral')
        except Exception as e:
            print(f"⚠️ Enrichment Failed: {e}")

    return segments

# --- AZURE TTS ---

def generate_audio_azure(text: str, path: str, voice: str, style: str = "neutral") -> bool:
    try:
        speech_config = speechsdk.SpeechConfig(subscription=AZURE_SPEECH_KEY, region=AZURE_SPEECH_REGION)
        
        # High Fidelity Output (24kHz Native String)
        # Fix: V6 - Use string identifier to avoid Enum version issues
        speech_config.set_property(
            speechsdk.PropertyId.SpeechServiceConnection_SynthOutputFormat, 
            "audio-24khz-160kbitrate-mono-mp3"
        )
        
        speech_config.speech_synthesis_voice_name = voice
        audio_config = speechsdk.audio.AudioOutputConfig(filename=path)
        
        # Construct SSML for emotion/style if needed
        # We wrap in basic SSML to be safe
        ssml = f"""
        <speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xmlns:mstts="https://www.w3.org/2001/mstts" xml:lang="ar-EG">
            <voice name="{voice}">
                <mstts:express-as style="{style}" styledegree="1">
                    {text}
                </mstts:express-as>
            </voice>
        </speak>
        """
        
        synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)
        
        # Use SSML Async
        result = synthesizer.speak_ssml_async(ssml).get()

        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            return True
        elif result.reason == speechsdk.ResultReason.Canceled:
            cancellation_details = result.cancellation_details
            print(f"Azure TTS Canceled: {cancellation_details.reason}")
            if cancellation_details.reason == speechsdk.CancellationReason.Error:
                print(f"Error details: {cancellation_details.error_details}")
            # Fallback to simple text if SSML fails?
            return False
            
    except Exception as e:
        print(f"Azure TTS Exception: {e}")
        return False

# --- PIPELINE ---

def process_segment_pipeline(video_chunk_path: str, output_chunk_path: str):
    """
    V5 Pipeline: Azure TTS (Dual Male), VAD, Smart Sync.
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
        tts_raw = f"{base_name}_tts_temp_{idx}.mp3"
        tts_clean = f"{base_name}_tts_clean_{idx}.wav"
        tts_final = f"{base_name}_tts_final_{idx}.wav"
        
        text = clean_text(seg["text"])
        
        # Calculate target duration FIRST (Used by Intro Guard & VAD)
        target_dur = seg["end"] - seg["start"]
        
        # V6: Intro Guard
        # Skip anything in the first 5 seconds (Music/Intro)
        if seg["start"] < 5.0:
            print(f"  🎵 Intro Guard: Skipping segment at {seg['start']}s (Intro/Music)")
            # Extract original audio just in case we need to preserve timeline? 
            # Actually, if we skip, we usually want to KEEP the original audio for this duration.
            # Logic below handles 'continue' by effectively doing nothing? 
            # WAIT. If we 'continue', we skip adding to 'dubbed_files'. 
            # If we skip adding to 'dubbed_files', the 'current_timeline_ms' won't advance?
            # NO. We MUST add the original audio to 'dubbed_files' to keep the timeline in sync!
            
            cmd = ["ffmpeg", "-i", audio_path, "-ss", str(seg["start"]), "-t", str(target_dur), "-y", tts_final]
            subprocess.run(cmd, stdout=subprocess.DEVNULL)
            sanitize_audio(tts_final, tts_final)
            dubbed_files.append(tts_final)
            current_timeline_ms += (target_dur * 1000)
            continue

        # 1. VAD / Noise Filter
        no_speech = seg.get("no_speech_prob", 0.0)
        # target_dur already calculated above
        
        if no_speech > 0.4 or not text or len(text) < 2:
            print(f"  ⏭️ Skipping Segment {idx} (No Speech Prob: {no_speech:.2f})")
            # Fill with silence or original noise? Original audio is best for background.
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
            voice = "ar-SA-HamedNeural" # Saudi Male
        else:
            voice = "ar-EG-ShakirNeural" # Egyptian Male
            
        style = "cheerful" if "!" in text or seg.get("emotion") == "happy" else "neutral"

        # 3. Smart Sync Check (Condense Loop)
        est_chars_per_sec = 13
        est_duration = len(text) / est_chars_per_sec
        
        if est_duration > (target_dur * 1.3):
             print(f"  📉 Predicted Text Too Long (Est {est_duration:.2f}s vs Max {target_dur*1.3:.2f}s). Condensing...")
             text = condense_text(text, target_dur, est_duration)
        
        print(f"  🗣️ Gen Azure TTS ({voice}): {text[:30]}...")
        # Generate
        success = generate_audio_azure(text, tts_raw, voice, style)
        
        if not success:
            # Maybe retry without SSML (Standard text)
            print("  ⚠️ SSML Failed? Retrying text-only.")
            try:
                speech_config = speechsdk.SpeechConfig(subscription=AZURE_SPEECH_KEY, region=AZURE_SPEECH_REGION)
                speech_config.set_speech_synthesis_output_format(speechsdk.SpeechSynthesisOutputFormat.Audio44100Hz16BitMonoMp3)
                speech_config.speech_synthesis_voice_name = voice
                audio_config = speechsdk.audio.AudioOutputConfig(filename=tts_raw)
                synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)
                synthesizer.speak_text_async(text).get()
                if os.path.exists(tts_raw) and os.path.getsize(tts_raw) > 0:
                    success = True
            except: pass

        if not success or not os.path.exists(tts_raw):
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
        
        # Gap handling
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
        elif ratio > 2.0:
            # PANIC MODE: Hallucination or Text too long.
            print(f"  ⚠️ PANIC: Ratio {ratio:.2f}x > 2.0. Dropping TTS & Using Original Audio.")
            cmd = ["ffmpeg", "-i", audio_path, "-ss", str(seg["start"]), "-t", str(target_dur), "-y", tts_final]
            subprocess.run(cmd, stdout=subprocess.DEVNULL)
            sanitize_audio(tts_final, tts_final)
            dubbed_files.append(tts_final)
            current_timeline_ms += (target_dur * 1000)
        else:
            # > 1.25x but <= 2.0
            # Cap speed at 1.25x and STRETCH VIDEO later
            print(f"  🐢 Ratio {ratio:.2f}x. Capping speed & Will Stretch Video.")
            adjust_speed(tts_clean, tts_final, 1.25)
            dubbed_files.append(tts_final)
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
