import streamlit as st
import requests
import time

# إعدادات الصفحة
st.set_page_config(page_title="مدبلج العرب AI", page_icon="🎙️", layout="centered")

# --- هام: ضع رابط محرك Koyeb هنا ---
API_URL = "https://sacred-fawn-arab-dubbing-7b0a1186.koyeb.app"

st.title("🎙️ مدبلج العرب (الإصدار التاسع)")
st.write("ارفع الفيديو، وسيقوم الذكاء الاصطناعي بدبلجته ودمجه تلقائياً.")

uploaded_file = st.file_uploader("اختر فيديو (MP4)", type=["mp4"])

if uploaded_file:
    st.video(uploaded_file)
    
    if st.button("🚀 ابدأ الدبلجة"):
        with st.spinner("جاري رفع الفيديو للمحرك..."):
            try:
                files = {"file": uploaded_file.getvalue()}
                params = {"mode": "DUBBING", "target_lang": "ar"}
                # إرسال للمحرك
                response = requests.post(f"{API_URL}/upload", files={"file": uploaded_file}, data=params)
                
                if response.status_code == 200:
                    job_id = response.json().get("job_id")
                    st.success(f"تم الاستلام! رقم العملية: {job_id}")
                    
                    # شريط التقدم
                    my_bar = st.progress(0)
                    status_text = st.empty()
                    
                    # متابعة الحالة
                    while True:
                        time.sleep(5) # انتظر 5 ثواني
                        res = requests.get(f"{API_URL}/job/{job_id}")
                        if res.status_code == 200:
                            data = res.json()
                            status = data.get("status")
                            
                            if status == "completed":
                                my_bar.progress(100)
                                status_text.success("✅ تمت الدبلجة بنجاح!")
                                
                                # جلب الرابط النهائي
                                video_url = data.get("output_url") or data.get("media_url") or data.get("video_url")
                                
                                if video_url:
                                    st.video(video_url)
                                    st.markdown(f"[📥 اضغط هنا لتحميل الفيديو]({video_url})")
                                else:
                                    st.error("انتهت المعالجة لكن لم يتم العثور على رابط الفيديو.")
                                break
                                
                            elif status == "failed":
                                status_text.error("❌ فشلت العملية في السيرفر.")
                                st.write(data)
                                break
                            else:
                                status_text.text(f"⏳ جاري المعالجة... الحالة: {status}")
                        else:
                            st.error("فشل الاتصال بالمحرك.")
                            break
                else:
                    st.error(f"حدث خطأ في الرفع: {response.text}")
            except Exception as e:
                st.error(f"خطأ: {e}")

st.markdown("---")
st.caption("Powered by Koyeb & Streamlit")
