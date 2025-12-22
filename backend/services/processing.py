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
    return 'gemini-1.5-flash' 

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
            gl_file = gemini_client.files.upload(file=audio_path)
            while gl_file.state.name == "PROCESSING":
                time.sleep(1)
                gl_file = gemini_client.files.get(name=gl_file.name)
            
            simplified = [{"id": i, "start": s["start"], "end": s["end"], "text": s["text"]} for i, s in enumerate(segments)]
            prompt = f"""
            Task: Listen carefully to the audio. Diarize speakers (Speaker A, Speaker B).
            CRITICAL: Identify gender based on PITCH and TONE. 
            Translate text to Professional Arabic (Fusha).
            Detect Emotion (happy, sad, neutral, excited).
            
            Input: {json.dumps(simplified)}
            
            Output JSON: [{{ "id": 0, "ar_text": "...", "emotion": "neutral", "gender": "Male", "speaker": "Speaker A" }}]
            """

            # Retry Logic for Quota (429) and Model Not Found (404)
            from google.api_core.exceptions import NotFound

            response = None
            max_retries = 3
            current_model = 'gemini-1.5-flash'

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
                except NotFound:
                    print(f"⚠️ Model {current_model} NOT FOUND (404). Switching to gemini-pro.")
                    current_model = 'gemini-pro'
                    # Retry immediately with new model
                    continue
                except Exception as e:
                    print(f"⚠️ Enrichment Attempt {attempt+1} Error: {e}")
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

# --- TTS & MERGING ---
def generate_audio_gemini(text: str, path: str, emotion: str = "neutral", voice_name: str = "ar-EG-ShakirNeural") -> bool:
    # 1. Generate SSML
    ssml = None
    if gemini_client:
        try:
            resp = gemini_client.models.generate_content(
                model='gemini-1.5-flash',
                contents=f"Convert to SSML for Azure TTS (ar-EG-ShakirNeural). Emotion: {emotion}. Text: {text}. Output only SSML."
            )
            val = resp.text.replace("```xml", "").replace("```", "").strip()
            if val.startswith("<speak"): ssml = val
        except: pass

    # 2. Azure TTS
    try:
        speech_config = speechsdk.SpeechConfig(subscription=AZURE_SPEECH_KEY, region=AZURE_SPEECH_REGION)
        speech_config.speech_synthesis_voice_name = voice_name
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
    V2 Pipeline with Elastic Syncing.
    """
    base_name = os.path.splitext(video_chunk_path)[0]
    audio_path = f"{base_name}_source.mp3"
    
    print(f"🎤 Extracting audio: {video_chunk_path}")
    extract_audio(video_chunk_path, audio_path)
    
    print(f"🧠 Transcribing & Translating...")
    segments = smart_transcribe(audio_path)
    
    dubbed_files = []
    
    # ELASTIC SYNCING STATE
    current_timeline_ms = 0
    
    for idx, seg in enumerate(segments):
        tts_temp = f"{base_name}_tts_temp_{idx}.wav"
        tts_final = f"{base_name}_tts_final_{idx}.wav"
        
        # 1. Generate Raw TTS
        voice = "ar-EG-ShakirNeural" if seg.get("gender") == "Male" else "ar-EG-SalmaNeural"
        print(f"  🗣️ Gen TTS ({voice}): {seg['text'][:30]}...")
        
        # Fix 2: Rate Limit Prevention (Sleep 4s for Free Tier)
        time.sleep(4)
        
        success = generate_audio_gemini(seg["text"], tts_temp, seg.get("emotion", "neutral"), voice)
        
        if not success or not os.path.exists(tts_temp):
            print(f"  ❌ TTS Failed. Using original audio fallback.")
            # Fallback: Extract original audio for this segment duration
            seg_dur = seg["end"] - seg["start"]
            cmd = ["ffmpeg", "-i", audio_path, "-ss", str(seg["start"]), "-t", str(seg_dur), "-y", tts_final]
            subprocess.run(cmd, stdout=subprocess.DEVNULL)
            dubbed_files.append(tts_final)
            current_timeline_ms = seg["end"] * 1000 # Advance Timeline
            continue

        # 2. Calculate Sync Metadata
        # Target Start Time (ms)
        target_start_ms = seg["start"] * 1000
        
        # Current Gap (Silence needed?)
        gap_ms = target_start_ms - current_timeline_ms
        
        if gap_ms > 100: # If gap > 0.1s, insert silence
             silence_path = f"{base_name}_silence_{idx}.wav"
             if generate_silence(gap_ms, silence_path):
                 dubbed_files.append(silence_path)
                 current_timeline_ms += gap_ms
                 
        # 3. Speed/Stretch Check
        # Original Duration (ms)
        original_dur_ms = (seg["end"] - seg["start"]) * 1000
        # TTS Duration (ms)
        tts_audio = AudioSegment.from_file(tts_temp)
        tts_dur_ms = len(tts_audio)
        
        ratio = tts_dur_ms / original_dur_ms if original_dur_ms > 0 else 1.0
        
        if ratio <= 1.0:
            # TTS is shorter/equal. Good.
            # We just use it (and maybe pad end or let next gap handle it).
            # Rename temp to final
            os.rename(tts_temp, tts_final)
            dubbed_files.append(tts_final)
            current_timeline_ms += tts_dur_ms
            
        elif ratio <= 1.25:
             # TTS is slightly longer. Speed up.
             print(f"  ⚡ Speeding up by {ratio:.2f}x")
             if adjust_speed(tts_temp, tts_final, ratio):
                 dubbed_files.append(tts_final)
                 # New duration is roughly original duration
                 current_timeline_ms += original_dur_ms 
             else:
                 # Speedup failed? Use original
                 dubbed_files.append(tts_temp)
                 current_timeline_ms += tts_dur_ms
                 
        else:
             # Ratio > 1.25. Too long!
             # Cap speed at 1.25x
             print(f"  ⚠️ Text too long ({ratio:.2f}x). Capping at 1.25x.")
             if adjust_speed(tts_temp, tts_final, 1.25):
                 dubbed_files.append(tts_final)
                 # We consume 1.25x less time than TTS, but still more than original.
                 # This pushes the timeline.
                 current_timeline_ms += (tts_dur_ms / 1.25)
             else:
                 dubbed_files.append(tts_temp)
                 current_timeline_ms += tts_dur_ms

        # Cleanup temp
        if os.path.exists(tts_temp): os.remove(tts_temp)

    
    if dubbed_files:
        print(f"🎬 Merging {len(dubbed_files)} audio clips...")
        merge_audio_video(video_chunk_path, dubbed_files, output_chunk_path)
    else:
        # Fallback
        print("⚠️ No speech detected, copying original.")
        subprocess.run(["ffmpeg", "-i", video_chunk_path, "-c", "copy", output_chunk_path], check=True)
    
    # Cleanup intermediate
    for f in dubbed_files:
        try: os.remove(f)
        except: pass
    try: os.remove(audio_path)
    except: pass
