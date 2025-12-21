import os
from datetime import timedelta
from google.cloud import storage
from google.oauth2 import service_account

class GCSStorage:
    def __init__(self):
        # Ensure we have credentials
        self.credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        self.project_id = os.getenv("GCP_PROJECT_ID")
        self.bucket_name = "processed-segments" # Default bucket
        
        if self.credentials_path and os.path.exists(self.credentials_path):
            self.client = storage.Client.from_service_account_json(self.credentials_path)
        else:
            # Fallback for local env if env var is not set but gcloud auth is present, 
            # OR if running on Render/Cloud with implicit auth.
            # Ideally the user should provide the JSON key file path in .env
            print("⚠️ GCS: No JSON key found, attempting default credentials...")
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
                    "responseHeader": ["Content-Type", "x-goog-resumable"],
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

# Singleton instance
gcs_service = GCSStorage()
