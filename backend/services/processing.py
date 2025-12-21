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
            Task: Listen, Diarize, Translate to Fusha, Detect Emotion.
            Input: {json.dumps(simplified)}
            Output JSON: [{{ "id": 0, "ar_text": "...", "emotion": "happy", "gender": "Male", "speaker": "Speaker A" }}]
            """
            
            # Using specific latest model version to avoid 404
            response = gemini_client.models.generate_content(
                model='gemini-2.0-flash-exp', 
                contents=[prompt, gl_file],
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            try: gemini_client.files.delete(name=gl_file.name)
            except: pass

            if response.text:
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
                model='gemini-2.0-flash-exp',
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

def extract_audio(video_path: str, audio_path: str) -> bool:
    cmd = ["ffmpeg", "-i", video_path, "-vn", "-acodec", "libmp3lame", "-ab", "64k", "-ar", "16000", "-y", audio_path]
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

# --- MAIN PIPELINE FUNCTION ---
def process_segment_pipeline(video_chunk_path: str, output_chunk_path: str):
    """
    Full dubbing pipeline for a single 5-min chunk.
    1. Extract Audio
    2. Smart Transcribe (Groq + Gemini)
    3. Generate Dubbed Audio (Azure)
    4. Merge
    """
    base_name = os.path.splitext(video_chunk_path)[0]
    audio_path = f"{base_name}_source.mp3"
    
    print(f"🎤 Extracting audio: {video_chunk_path}")
    extract_audio(video_chunk_path, audio_path)
    
    print(f"🧠 Transcribing & Translating...")
    segments = smart_transcribe(audio_path)
    
    dubbed_files = []
    # Process each sentence
    for idx, seg in enumerate(segments):
        tts_path = f"{base_name}_tts_{idx}.wav"
        
        # Calculate duration match (simple vs complex)
        # We'll just generate the TTS and trust the timeline for now. 
        # Advanced sync (stretching) would be added here if needed.
        
        # Voice Selection
        voice = "ar-EG-ShakirNeural" if seg.get("gender") == "Male" else "ar-EG-SalmaNeural"
        
        success = generate_audio_gemini(seg["text"], tts_path, seg.get("emotion", "neutral"), voice)
        
        # Verify file was actually created and has content
        if success and os.path.exists(tts_path) and os.path.getsize(tts_path) > 0:
            dubbed_files.append(tts_path)
        else:
            print(f"⚠️ TTS Generation Failed for segment {idx}: {seg['text'][:20]}...")
            # Ideally generate silence here to maintain sync, but for now skip to avoid crash
    
    if dubbed_files:
        print(f"🎬 Merging {len(dubbed_files)} audio clips...")
        merge_audio_video(video_chunk_path, dubbed_files, output_chunk_path)
    else:
        # Fallback: Just copy original if no speech
        print("⚠️ No speech detected, copying original.")
        subprocess.run(["ffmpeg", "-i", video_chunk_path, "-c", "copy", output_chunk_path], check=True)
    
    # Cleanup intermediate TTS files
    for f in dubbed_files:
        try: os.remove(f)
        except: pass
    try: os.remove(audio_path)
    except: pass
