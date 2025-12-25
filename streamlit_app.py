import streamlit as st
import requests
import time
import os

# --- إعدادات الصفحة ---
st.set_page_config(page_title="Arab Dubbing Pro", page_icon="🎙️", layout="centered")

# --- رابط المحرك (Koyeb API) ---
# هذا هو الرابط الخاص بمشروعك الذي نجحنا في تشغيله
API_URL = "https://sacred-fawn-arab-dubbing-7b0a1186.koyeb.app"

# --- التصميم (UI) ---
st.title("🎙️ Arab Dubbing AI (V9)")
st.markdown("### تحويل الفيديو إلى العربية بدقة سنيمائية")

# رفع الفيديو
uploaded_file = st.file_uploader("ارفع الفيديو هنا (MP4)", type=["mp4"])

if uploaded_file is not None:
    st.video(uploaded_file)
    
    if st.button("🚀 ابدأ الدبلجة الآن"):
        with st.spinner("جاري رفع الفيديو للمحرك... 📤"):
            try:
                # 1. إرسال الفيديو للمحرك
                # استخدام getvalue() لضمان إرسال البيانات الخام
                files = {"file": ("video.mp4", uploaded_file.getvalue(), "video/mp4")}
                params = {"mode": "DUBBING", "target_lang": "ar"}
                
                response = requests.post(f"{API_URL}/upload", files=files, data=params)
                
                if response.status_code == 200:
                    data = response.json()
                    job_id = data["job_id"]
                    st.success(f"تم الاستلام! جاري المعالجة... (ID: {job_id})")
                    
                    # 2. انتظار النتيجة (Polling)
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    while True:
                        try:
                            status_res = requests.get(f"{API_URL}/job/{job_id}")
                            if status_res.status_code == 200:
                                job_data = status_res.json()
                                # استخراج الحالة من أول مقطع إذا لم تكن موجودة في الجذر
                                segments = job_data.get("segments", [])
                                if segments:
                                    # حساب التقدم بناءً على المقاطع الجاهزة
                                    total_segs = len(segments)
                                    ready_segs = sum(1 for s in segments if s.get("status") == "ready")
                                    progress = int((ready_segs / total_segs) * 100) if total_segs > 0 else 0
                                    progress_bar.progress(progress)
                                    
                                    # تحديد الحالة العامة
                                    all_ready = all(s.get("status") == "ready" for s in segments)
                                    any_failed = any(s.get("status") == "failed" for s in segments)
                                    
                                    if all_ready:
                                        status_text.text("✅ تمت الدبلجة بنجاح!")
                                        st.balloons()
                                        st.success("فيديوهك جاهز! 👇")
                                        
                                        # تجميع الروابط أو عرض الرابط الأول
                                        # في النظام الجديد، يتم تشغيل كل مقطع على حدة أو تجميعها
                                        # هنا سنعرض رابط المقطع الأول كمثال أو نحتاج لرابط التجميع إذا كان متوفراً
                                        # سنعرض كل المقاطع الجاهزة
                                        for idx, seg in enumerate(segments):
                                            final_url = seg.get("media_url")
                                            if final_url:
                                                st.write(f"📺 مقطع {idx+1}")
                                                st.video(final_url)
                                        break
                                        
                                    elif any_failed:
                                        st.error("❌ فشلت بعض المقاطع في المعالجة.")
                                        break
                                    
                                    else:
                                        status_text.text(f"⚙️ جاري العمل... ({ready_segs}/{total_segs})")
                                        time.sleep(3)
                                else:
                                    status_text.text("⏳ جاري تحليل الفيديو...")
                                    time.sleep(3)
                            else:
                                time.sleep(3)
                        except Exception as e:
                            st.warning(f"انتظار الاستجابة... ({e})")
                            time.sleep(3)
                            
                else:
                    st.error(f"فشل الرفع: {response.text}")
                    
            except Exception as e:
                st.error(f"حدث خطأ في الاتصال: {e}")

# --- تذييل الصفحة ---
st.markdown("---")
st.caption("Powered by Koyeb & Google Cloud | V9 Engine")
