import os
from supabase import create_client, Client

class DatabaseService:
    def __init__(self):
        self.url = os.getenv("SUPABASE_URL")
        self.key = os.getenv("SUPABASE_KEY")
        self.client: Client = None
        
        if self.url and self.key:
            try:
                self.client = create_client(self.url, self.key)
            except Exception as e:
                print(f"❌ Supabase Connection Failed: {e}")

    def create_job(self, job_id: str, filename: str, mode: str = "DUBBING", target_lang: str = "ar"):
        if not self.client: return
        try:
            self.client.table("video_jobs").insert({
                "id": job_id,
                "original_filename": filename,
                "status": "pending",
                "mode": mode,
                "target_lang": target_lang
            }).execute()
        except Exception as e:
            print(f"⚠️ DB Insert Job Error: {e}")

    def create_segment(self, job_id: str, index: int, status: str = "pending"):
        if not self.client: return
        try:
            self.client.table("video_segments").insert({
                "job_id": job_id,
                "segment_index": index,
                "status": status
            }).execute()
        except Exception as e:
            print(f"⚠️ DB Insert Segment Error: {e}")

    def update_segment_status(self, job_id: str, index: int, status: str, media_url: str = None, gcs_path: str = None):
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
        if not self.client: return []
        try:
            # Order by segment_index ASC
            res = self.client.table("video_segments").select("*").eq("job_id", job_id).order("segment_index").execute()
            return res.data
        except Exception as e:
            print(f"⚠️ DB Fetch Error: {e}")
            return []

db_service = DatabaseService()
