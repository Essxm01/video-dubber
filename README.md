# دبلجة العرب - Arab Dubbing Platform

<div align="center">

![Arab Dubbing Logo](https://img.shields.io/badge/Arab%20Dubbing-AI%20Powered-6366f1?style=for-the-badge&logo=youtube&logoColor=white)

**منصة ذكاء اصطناعي لدبلجة وترجمة فيديوهات يوتيوب إلى العربية**

[🚀 Demo](https://arab-dubbing.vercel.app) | [📖 Documentation](#documentation) | [🐛 Report Bug](https://github.com/yourusername/arab-dubbing/issues)

</div>

---

## ✨ المميزات

- 🎙️ **دبلجة صوتية بالذكاء الاصطناعي** - تحويل صوت المتحدث إلى العربية
- 📝 **ترجمة احترافية** - إنشاء ملفات SRT للترجمة
- 🎬 **خيار شامل** - دبلجة + ترجمة معاً
- 🌐 **واجهة ثنائية اللغة** - عربي / إنجليزي
- 🌙 **الوضع الليلي** - دعم كامل للوضع الداكن
- ⚡ **معالجة سريعة** - بفضل Whisper و gTTS

---

## 🏗️ هيكل المشروع

```
arab-dubbing-platform/
├── frontend/           # React + TypeScript + Vite
│   ├── components/     # React components
│   ├── services/       # API services
│   └── ...
├── backend/            # FastAPI + Python
│   ├── main.py         # Main API server
│   └── requirements.txt
├── .github/            # GitHub Actions
└── vercel.json         # Vercel deployment config
```

---

## 🚀 Quick Start

### Prerequisites

- Node.js 18+
- Python 3.9+
- FFmpeg

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Backend

```bash
cd backend
pip install -r requirements.txt
python main.py
```

---

## 🔧 Tech Stack

### Frontend

- React 19
- TypeScript
- Vite
- Tailwind CSS (via custom classes)
- Lucide Icons

### Backend

- FastAPI
- OpenAI Whisper (Speech-to-Text)
- Google Translate API
- gTTS (Text-to-Speech)
- MoviePy (Video Processing)
- yt-dlp (YouTube Download)

### Infrastructure

- **Hosting**: Vercel (Frontend) + Railway/Render (Backend)
- **Database**: Supabase
- **Storage**: Supabase Storage

---

## 📝 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Health check |
| `/download` | POST | Download YouTube video |
| `/transcribe` | POST | Transcribe audio to text |
| `/translate` | POST | Translate text |
| `/generate-audio` | POST | Generate TTS audio |
| `/dub-video` | POST | Full dubbing pipeline |

---

## 🌍 Environment Variables

### Frontend (`.env.local`)

```
VITE_BACKEND_URL=http://localhost:8000
VITE_SUPABASE_URL=your_supabase_url
VITE_SUPABASE_ANON_KEY=your_supabase_key
GEMINI_API_KEY=your_gemini_key
```

### Backend (`.env`)

```
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
```

---

## 📄 License

MIT License © 2025 Arab Dubbing

---

<div align="center">
Made with ❤️ for the Arab world
</div>
<!-- Last Deploy Trigger: 12/25/2025 08:19:52 -->
Updated: 2025-12-26 02:33:41
> Last Deployment Trigger: 2025-12-26 04:30:12
