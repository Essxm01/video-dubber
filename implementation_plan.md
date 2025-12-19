# V21 Hybrid Implementation Plan

## Goal Description

Implement "Hybrid V21" architecture for the dubbing API. This combines Gemini's advanced "Native Audio" understanding (for emotion and context) with the robust "SSML" capabilities of Azure TTS.

## V25 Optimization: Precision Sync & Silence Reduction (Current)

**Goal:** Address user feedback regarding image-audio desync (image preceding sound) and reduce robotic pauses.

### Key Changes

1. **Aggressive Silence Trimming:** Use `pydub` to remove silence > 200ms from generated TTS audio *before* duration checks.
2. **Strict Speedup Cap:** Limit audio speedup to **1.15x** (15%) max.
3. **Prioritize Video:** If audio is still longer than video after trimming + 1.15x speedup, freeze the video frame to extend the visual timeline.
4. **Resync Logic:** Strictly align start of next segment to end of previous segment to prevent drift accumulation.

### Files to Modify

#### [MODIFY] [main.py](file:///D:/video-dubber/backend/main.py)

- Import `from pydub.silence import split_on_silence`
- Add helper `trim_silence(audio_segment)`
- Update `process_video_task` loop:
  - Step 1: `trim_silence`
  - Step 2: Check Ratio logic with new 1.15x limit.
  - Step 3: Ensure video extraction uses precise timestamps.

## Completed Features (V21)

### 1. Gemini Native Audio Analysis (The Brain)

- **What:** Upload audio directly to Gemini 1.5 Pro using the new `google.genai` SDK.
- **Output:** JSON with `{start, end, text, emotion}`.
- **Why:** To capture emotional nuances (e.g., excitement, sadness) that plain text transcription misses.
- **SDK Upgrade:** Migrated from deprecated `google.generativeai` to `google.genai` (v0.3.0+).

### 2. Smart Batching (The Flow)

- **Algorithm:** `optimize_segments_for_flow`
- **Logic:** Merges segments separated by < 0.75s silence.
- **Benefit:** Eliminates robotic pauses between short sentences, creating a "breathless" natural flow.

### 3. Emotion-Aware SSML (The Voice)

- **Dynamic SSML:** Gemini generates SSML tags based on the detected emotion.
- **Examples:**
  - `neutral`: Normal pacing.
  - `dramatic`: Longer pauses (<break time="600ms"/>).
  - `fast`: Quicker rhythm for excitement.
- **Tone:** Professional Modern Standard Arabic (Fusha) for documentary style.

## Architecture Changes (Backend)

### [modified] [main.py](file:///D:/video-dubber/backend/main.py)

1. **Replaced:** `smart_transcribe` now uses `gemini_client.files.upload` and `models.generate_content`.
2. **Added:** `optimize_segments_for_flow` function for batching.
3. **Updated:** `process_video_task` to use the new pipeline.
4. **Refactored:** Removed deprecated SDK usage to fix 404 errors.

## Verification Plan

1. **SDK Check:** Confirm no "deprecated" warnings in logs.
2. **Upload Check:** Verify `files.upload` succeeds without `path` error.
3. **Flow Check:** Listen to output to confirm segments are merged and flowing naturally.
