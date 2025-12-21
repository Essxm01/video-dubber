import os
import time
from supabase import create_client, Client

class DatabaseService:
    def __init__(self):
        self.url = os.getenv("SUPABASE_URL")
        self.key = os.getenv("SUPABASE_KEY")
        self.client: Client = None
        self._init_client()

    def _init_client(self):
        if self.url and self.key:
            try:
                self.client = create_client(self.url, self.key)
            except Exception as e:
                print(f"❌ Supabase Connection Failed: {e}")

    def _ensure_connection(self):
        """Simple check to re-init if client is somehow lost (though Supabase-py is stateless)"""
        if not self.client:
            self._init_client()

    def create_job(self, job_id: str, filename: str, mode: str = "DUBBING", target_lang: str = "ar"):
        self._ensure_connection()
        if not self.client: return
        for attempt in range(3):
            try:
                self.client.table("video_jobs").insert({
                    "id": job_id,
                    "original_filename": filename,
                    "status": "pending",
                    "mode": mode,
                    "target_lang": target_lang
                }).execute()
                break
            except Exception as e:
                print(f"⚠️ DB Insert Job Error (Attempt {attempt+1}): {e}")
                time.sleep(1)

    def create_segment(self, job_id: str, index: int, status: str = "pending"):
        self._ensure_connection()
        if not self.client: return
        for attempt in range(3):
            try:
                self.client.table("video_segments").insert({
                    "job_id": job_id,
                    "segment_index": index,
                    "status": status
                }).execute()
                break
            except Exception as e:
                print(f"⚠️ DB Insert Segment Error (Attempt {attempt+1}): {e}")
                time.sleep(1)

    def update_segment_status(self, job_id: str, index: int, status: str, media_url: str = None, gcs_path: str = None):
        self._ensure_connection()
        if not self.client: return
        try:
            data = {"status": status}
            if media_url: data["media_url"] = media_url
            if gcs_path: data["gcs_path"] = gcs_path
            
            self.client.table("video_segments").update(data).match({
                "job_id": job_id, 
                "segment_index": index
            }).execute()
        except Exception as e:
            print(f"⚠️ DB Update Segment Error: {e}")

    def get_job_segments(self, job_id: str):
        self._ensure_connection()
        if not self.client: return []
        for attempt in range(3): # Retroactive Retry for fetching
            try:
                # Order by segment_index ASC
                res = self.client.table("video_segments").select("*").eq("job_id", job_id).order("segment_index").execute()
                return res.data
            except Exception as e:
                print(f"⚠️ DB Fetch Error (Attempt {attempt+1}): {e}")
                time.sleep(1) # Wait 1s and retry
        return []

db_service = DatabaseService()

