import os
import uuid
import subprocess
import glob
from services.db import db_service

class JobManager:
    def __init__(self, upload_dir="uploads", temp_dir="temp_segments"):
        self.upload_dir = upload_dir
        self.temp_dir = temp_dir
        os.makedirs(upload_dir, exist_ok=True)
        os.makedirs(temp_dir, exist_ok=True)

    def create_job(self, file_path: str, original_filename: str, mode: str, target_lang: str) -> str:
        """
        Creates a job, splits the video, and registers segments in DB.
        Returns job_id.
        """
        job_id = str(uuid.uuid4())
        
        # 1. Register Job in DB
        db_service.create_job(job_id, original_filename, mode, target_lang)
        
        # 2. Split Video into 5-minute chunks
        segment_pattern = os.path.join(self.temp_dir, f"{job_id}_%03d.mp4")
        
        # FFmpeg command to split
        # -c copy is fast (stream copy), but might not be frame-perfect. 
        # For dubbing sync, re-encoding might be safer, but user requested speed/copy if possible.
        # We'll try copy. If sync issues arise, we can switch to re-encode.
        cmd = [
            "ffmpeg", "-i", file_path,
            "-c", "copy",
            "-map", "0",
            "-f", "segment",
            "-segment_time", "300", # 5 minutes
            "-reset_timestamps", "1",
            segment_pattern
        ]
        
        print(f"✂️ Splitting video for job {job_id}...")
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # 3. Discover segments
        # Pattern matching to find created files
        # Note: glob pattern needs wildcard
        search_pattern = os.path.join(self.temp_dir, f"{job_id}_*.mp4")
        segments = sorted(glob.glob(search_pattern))
        
        # 4. Register Segments in DB
        for idx, seg_path in enumerate(segments):
            db_service.create_segment(job_id, idx, status="pending")
            print(f"  -> Segment {idx} registered: {os.path.basename(seg_path)}")
            
        return job_id, segments

    def cleanup_source(self, file_path: str):
        """Deletes the original source file."""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"🧹 Source Cleanup: {file_path}")
        except Exception as e:
            print(f"⚠️ Source Cleanup Failed: {e}")

    def cleanup_segment(self, segment_path: str):
        """Deletes a local segment file."""
        try:
            if os.path.exists(segment_path):
                os.remove(segment_path)
                print(f"🧹 Segment Cleanup: {segment_path}")
        except Exception as e:
            print(f"⚠️ Segment Cleanup Failed: {e}")

job_manager = JobManager()
