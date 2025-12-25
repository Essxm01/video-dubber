import os
from datetime import timedelta
from google.cloud import storage
from google.oauth2 import service_account

class GCSStorage:
    def __init__(self):
        # Ensure we have credentials
        self.credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        self.credentials_json_str = os.getenv("GCS_CREDENTIALS_JSON")
        self.project_id = os.getenv("GCP_PROJECT_ID")
        self.bucket_name = "processed-segments" # Default bucket
        
        self.client = None
        
        # 1. Priority: JSON String in Env Var (Koyeb/Render)
        if self.credentials_json_str:
            try:
                import json
                print("🔑 Found GCS_CREDENTIALS_JSON env var. Authenticating...")
                info = json.loads(self.credentials_json_str)
                creds = service_account.Credentials.from_service_account_info(info)
                self.client = storage.Client(credentials=creds, project=self.project_id)
            except Exception as e:
                print(f"❌ Failed to parse GCS_CREDENTIALS_JSON: {e}")

        # 2. File Path (Local Dev)
        if not self.client and self.credentials_path and os.path.exists(self.credentials_path):
            print(f"📂 Found Key File: {self.credentials_path}")
            self.client = storage.Client.from_service_account_json(self.credentials_path)
            
        # 3. Fallback (Default / Implicit)
        if not self.client:
            print("⚠️ GCS: No valid key found. Attempting Default Credentials...")
            try:
                self.client = storage.Client()
            except Exception as e:
                print(f"❌ GCS Client Init Failed: {e}")
                self.client = None
        
        # Auto-configure CORS for the bucket to allow browser playback
        if self.client:
            self.configure_cors()

    def configure_cors(self):
        """Sets CORS policy on the bucket to allow playback from any origin."""
        try:
            bucket = self.client.bucket(self.bucket_name)
            bucket.cors = [
                {
                    "origin": ["*"],
                    "responseHeader": [
                        "Content-Type", 
                        "x-goog-resumable", 
                        "Access-Control-Allow-Origin", 
                        "Range"
                    ],
                    "method": ["GET", "HEAD", "OPTIONS"],
                    "maxAgeSeconds": 3600
                }
            ]
            bucket.patch()
            print(f"✅ GCS Bucket CORS Configured for {self.bucket_name}")
        except Exception as e:
            print(f"⚠️ GCS CORS Config Failed: {e}")

    def upload_file(self, source_path: str, destination_blob_name: str, content_type: str = "video/mp4") -> str:
        """Uploads a file to the bucket and returns the public/signed URL."""
        if not self.client: return None

        try:
            bucket = self.client.bucket(self.bucket_name)
            blob = bucket.blob(destination_blob_name)
            
            blob.upload_from_filename(source_path, content_type=content_type)
            
            print(f"✅ GCS Upload Success: {destination_blob_name}")
            return self.generate_signed_url(destination_blob_name)
            
        except Exception as e:
            print(f"❌ GCS Upload Error: {e}")
            return None

    def generate_signed_url(self, blob_name: str, expiration_hours: int = 24) -> str:
        """Generates a V4 signed URL for the blob."""
        if not self.client: return ""
        
        try:
            bucket = self.client.bucket(self.bucket_name)
            blob = bucket.blob(blob_name)
            
            url = blob.generate_signed_url(
                version="v4",
                expiration=timedelta(hours=expiration_hours),
                method="GET"
            )
            return url
        except Exception as e:
            print(f"⚠️ URL Sign Error: {e}")
            return ""

    def stream_file_content(self, blob_name: str):
        """Yields file content in chunks for streaming."""
        if not self.client: return None
        try:
            bucket = self.client.bucket(self.bucket_name)
            blob = bucket.blob(blob_name)
            # Open directly as a stream
            with blob.open("rb") as f:
                while chunk := f.read(1024 * 1024): # 1MB chunks
                    yield chunk
        except Exception as e:
            print(f"❌ GCS Stream Error: {e}")
            yield b""

# Singleton instance
gcs_service = GCSStorage()
