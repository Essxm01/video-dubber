
import requests
import os
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")

url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={API_KEY}"
data = {
    "input": {"text": "Test connection"},
    "voice": {"languageCode": "en-US", "name": "en-US-Journey-F"},
    "audioConfig": {"audioEncoding": "MP3"}
}

print(f"Testing API Key: {API_KEY[:10]}...")
response = requests.post(url, json=data)

if response.status_code == 200:
    print("✅ SUCCESS! Google Cloud TTS is WORKING.")
else:
    print(f"❌ ERROR: {response.json()['error']['message']}")
