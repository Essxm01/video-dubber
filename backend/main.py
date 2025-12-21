"""
Arab Dubbing API V22 - Cloud Native Architecture
Split-Process-Stream Pipeline with GCS Storage
"""
import os
from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks, Request
from fastapi.responses import StreamingResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

# Use relative imports for services
from services.jobs import job_manager
from services.db import db_service
from services.storage import gcs_service
from services.processing import process_segment_pipeline

app = FastAPI(title="Arab Dubbing API V22", version="22.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ... (Existing health/root endpoints) ...

# Health Check Endpoint (Required for Render)
@app.get("/health")
def health():
    return {
        "status": "active",
        "version": "22.0.0",
        "engine": "Split-Process-Stream Pipeline",
        "services": {
            "gcs": gcs_service.client is not None,
            "supabase": db_service.client is not None
        }
    }

@app.get("/")
def root():
    return {"message": "Arab Dubbing API V22 - Ready"}

# NEW: Upload endpoint for chunked processing
@app.post("/upload")
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    mode: str = Form("DUBBING"),
    target_lang: str = Form("ar")
):
    # 1. Save Upload
    os.makedirs(job_manager.upload_dir, exist_ok=True)
    temp_path = os.path.join(job_manager.upload_dir, file.filename)
    with open(temp_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    # 2. Create Job & Split
    job_id, segments = job_manager.create_job(temp_path, file.filename, mode, target_lang)
    
    # 3. Queue Background Processing
    background_tasks.add_task(process_job_sequentially, job_id, segments, temp_path)
    
    return {"status": "ok", "job_id": job_id, "task_id": job_id, "segments_count": len(segments)}

# LEGACY: Keep old endpoint for backward compatibility
@app.post("/process-video")
async def process_video_legacy(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    mode: str = Form("DUBBING"),
    target_lang: str = Form("ar")
):
    # Redirect to new upload handler
    return await upload_video(background_tasks, file, mode, target_lang)

# PROXY STREAM ENDPOINT
@app.get("/stream/{job_id}/{filename}")
async def stream_video(job_id: str, filename: str):
    """Redirects to GCS Signed URL to allow direct playback with Range support."""
    blob_name = f"jobs/{job_id}/{filename}"
    signed_url = gcs_service.generate_signed_url(blob_name)
    if not signed_url:
        return {"error": "File not found or GCS error"}, 404
    return RedirectResponse(url=signed_url)

@app.get("/job/{job_id}")
def get_job_status(job_id: str, request: Request):
    """Retrieve segments from DB and rewrite URLs to use Proxy Stream."""
    segments = db_service.get_job_segments(job_id)
    
    # Rewrite media_url to use our Proxy Stream
    base_url = str(request.base_url).rstrip("/")
    for seg in segments:
        if seg.get("status") == "ready" and seg.get("media_url"):
            # Extract filename from the Signed URL or DB entry?
            # The 'media_url' in DB is likely the Signed URL or GCS path.
            # But we know the naming convention: "{job_id}_seg{idx}_dubbed.mp4"
            filename = f"{job_id}_seg{seg['segment_index']}_dubbed.mp4"
            seg["media_url"] = f"{base_url}/stream/{job_id}/{filename}"
            
    return {"job_id": job_id, "segments": segments}

# LEGACY: Keep old status endpoint for backward compatibility
@app.get("/status/{task_id}")
def get_task_status_legacy(task_id: str):
    """Legacy status endpoint - returns job segments."""
    segments = db_service.get_job_segments(task_id)
    
    # Determine overall progress
    if not segments:
        return {"status": "PENDING", "progress": 0, "message": "جاري التجهيز..."}
    
    ready_count = sum(1 for s in segments if s.get("status") == "ready")
    total = len(segments)
    progress = int((ready_count / total) * 100) if total > 0 else 0
    
    # Status
    all_ready = all(s.get("status") == "ready" for s in segments)
    any_failed = any(s.get("status") == "failed" for s in segments)
    
    if all_ready:
        status = "COMPLETED"
        message = "تمت الدبلجة بنجاح!"
        # Get first segment URL as result
        first_url = segments[0].get("media_url") if segments else None
        return {
            "status": status,
            "progress": 100,
            "message": message,
            "result": {"dubbed_video_url": first_url}
        }
    elif any_failed:
        return {"status": "FAILED", "progress": progress, "message": "فشلت بعض المقاطع"}
    else:
        return {"status": "PROCESSING", "progress": progress, "message": f"معالجة الجزء {ready_count+1}/{total}..."}

# --- BACKGROUND WORKER ---
def process_job_sequentially(job_id: str, segments: list, source_path: str):
    """Process each segment sequentially with immediate cleanup."""
    print(f"🚀 Starting Job {job_id} ({len(segments)} segments)")
    
    for idx, seg_path in enumerate(segments):
        try:
            print(f"⚡ Processing Segment {idx+1}/{len(segments)}: {seg_path}")
            
            # Update Status: Processing
            db_service.update_segment_status(job_id, idx, "processing")
            
            # OUTPUT PATH
            output_name = f"{job_id}_seg{idx}_dubbed.mp4"
            output_path = os.path.join("output", output_name)
            os.makedirs("output", exist_ok=True)
            
            # CORE PIPELINE (Dub the chunk)
            process_segment_pipeline(seg_path, output_path)
            
            # UPLOAD TO GCS
            gcs_url = None
            if os.path.exists(output_path):
                gcs_url = gcs_service.upload_file(output_path, f"jobs/{job_id}/{output_name}")
            
            # Update Status: Ready
            status = "ready" if gcs_url else "failed"
            db_service.update_segment_status(job_id, idx, status, media_url=gcs_url)
            
            # CLEANUP (Immediate Deletion Rule)
            job_manager.cleanup_segment(seg_path)  # Delete source chunk
            if os.path.exists(output_path):
                os.remove(output_path)  # Delete local output
            
        except Exception as e:
            print(f"❌ Segment {idx} Failed: {e}")
            db_service.update_segment_status(job_id, idx, "failed")
    
    # Final Cleanup
    job_manager.cleanup_source(source_path)
    print(f"🏁 Job {job_id} Completed!")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)