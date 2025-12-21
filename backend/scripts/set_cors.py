
import os
from google.cloud import storage

def set_cors(bucket_name):
    """Sets the CORS configuration for the bucket."""
    storage_client = storage.Client()
    bucket = storage_client.get_bucket(bucket_name)

    cors_configuration = [
        {
            "origin": ["*"],
            "responseHeader": [
                "Content-Type",
                "Access-Control-Allow-Origin",
                "x-goog-resumable"
            ],
            "method": ["GET", "HEAD", "OPTIONS"],
            "maxAgeSeconds": 3600
        }
    ]

    bucket.cors = cors_configuration
    bucket.patch()

    print(f"✅ CORS configuration set for bucket: {bucket_name}")
    print(f"   Origins: *")
    print(f"   Methods: GET, HEAD, OPTIONS")
    print(f"   Headers: Content-Type, Access-Control-Allow-Origin")

if __name__ == "__main__":
    # You can set this env var or hardcode it
    BUCKET_NAME = os.getenv("GCS_BUCKET_NAME", "processed-segments")
    
    print(f"🔌 Connecting to GCS to update CORS for bucket: {BUCKET_NAME}...")
    try:
        set_cors(BUCKET_NAME)
    except Exception as e:
        print(f"❌ Failed to set CORS: {e}")
        print("💡 Hint: Make sure you have GOOGLE_APPLICATION_CREDENTIALS set or are logged in via gcloud.")
