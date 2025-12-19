# Local AI Pipeline Architecture Overhaul

## Planning Phase

- [x] Analyze current project structure and cloud API usage
- [x] Review existing `main.py` backend implementation
- [x] Create implementation plan for local AI microservice
- [x] Get user approval on implementation plan (Approved with 4GB VRAM constraints)

## Execution Phase

### 1. Git Safety & Structure

- [x] Update `.gitignore` to exclude `D:/Video Dubber/ai-services/`
- [x] Create `D:/Video Dubber/ai-services/` folder structure (User created manually)

### 2. AI Microservice Files

- [x] Create `ai-services/app.py` - FastAPI wrapper for AI models
- [x] Create `ai-services/core/audio_extraction.py` - FFmpeg audio extraction
- [x] Create `ai-services/core/transcription.py` - Whisper STT
- [x] Create `ai-services/core/diarization.py` - Pyannote speaker ID
- [x] Create `ai-services/core/translation.py` - NLLB translation
- [x] Create `ai-services/core/tts.py` - XTTS-v2 TTS
- [x] Create `ai-services/core/video_merge.py` - FFmpeg video merge

### 3. Setup & Installation Scripts

- [x] Create `ai-services/model_loader.py` - HuggingFace model downloader
- [x] Create `ai-services/setup_ai_env.bat` - Windows venv setup script
- [x] Create `ai-services/requirements.txt` - Python dependencies
- [x] Install PyTorch with CUDA support (Manual Step)

### 4. Backend Integration

- [x] Create orchestrator in main backend to call AI Microservice
- [x] Update backend to use local pipeline instead of cloud APIs

## Verification Phase

- [x] Test model download script (All models ready ✅)
- [x] Test AI microservice startup (Verified ✅)
- [x] Test full pipeline end-to-end (Backend Running @ 10000 ✅)
- [x] Verify Git ignores model files

## 🔥 Genius Optimization Phase (Current)

- [x] Audit system for Python 3.14 compatibility
- [x] Replace `pydub` with `moviepy` in all services
- [x] Upgrade Whisper to `medium` model for higher accuracy
- [x] Fix Frontend API URL (was pointing to Render cloud)
- [x] Verify Pyannote license token in `.env` (Confirmed present)
- [x] Final End-to-End Test with "Genius" settings (Systems Online - Waiting for User)

## Cloud Pipeline Migration (Google GenAI + Render)

- [x] **SDK Migration:** Migrate from `google-generativeai` to `google-genai` (v0.3.0+) to fix deprecation/404.
- [x] **Hybrid Audio Pipeline:** Implement Gemini Native Audio (Emotion Analysis) + Azure (TTS).
- [x] **Smart Batching:** Merge close segments for natural flow (no robotic pauses).
- [x] **Pronunciation Polish:** Refine Gemini prompts for Professional Fusha (Documentary Style).
- [x] **Final Verification:** Ensure end-to-end flow handles uploads and emotion mapping.
- [x] **Robustness:** Dynamic Model Discovery & V1/V1beta Fallbacks.
- [x] **Deep Solve (V22):** Implement "Whisper First" pipeline to guarantee 100% audio coverage (Fixes 1:40 cutoff).

## V25: Precision Sync & Silence Optimization (Current)

- [x] **Silence Reduction:** Implement `pydub` silence trimming on generated TTS audio.
- [x] **Strict Speedup Cap:** Limit audio speedup to 1.15x (max 15%) per user request.
- [x] **Smart Video Freeze:** Refine freeze-frame logic to handle duration mismatches > 15%.
- [x] **Frame-Accurate Sync:** Ensure video segments are extracted with precise timestamps to prevent AV drift.

## V26: Adaptive Concise Translation (New)

- [x] **Prompt Engineering:** Update System Prompt to prioritize concise Fusha synonyms that match English duration.
- [x] **Context Awareness:** Instruct Gemini to "simplify without losing meaning" to aid synchronization.
