
import { ProcessingStage, ServiceMode } from './types';

// Base steps - ALL possible steps
export const ALL_STEPS = [
  { id: ProcessingStage.DOWNLOAD, label: 'upload_video', icon: 'Upload' },
  { id: ProcessingStage.TRANSCRIPTION, label: 'analyze_audio', icon: 'FileAudio' },
  { id: ProcessingStage.TRANSLATION, label: 'translate_text', icon: 'Languages' },
  { id: ProcessingStage.SUBTITLE_GENERATION, label: 'generate_subs', icon: 'FileText' },
  { id: ProcessingStage.VOICE_GENERATION, label: 'generate_voice', icon: 'Mic' },
  { id: ProcessingStage.SYNCING, label: 'sync_merge', icon: 'RefreshCw' },
  { id: ProcessingStage.FINALIZING, label: 'complete', icon: 'CheckCircle' },
];

// Legacy export for backwards compatibility
export const STEPS = ALL_STEPS;

/**
 * Get steps based on selected mode
 * SUBTITLES: Upload -> Transcribe -> Translate -> Generate SRT -> Complete
 * DUBBING: Upload -> Transcribe -> Translate -> Generate Voice -> Merge -> Complete
 * BOTH: Upload -> Transcribe -> Translate -> Generate SRT -> Generate Voice -> Merge -> Complete
 */
export const getStepsForMode = (mode: ServiceMode) => {
  switch (mode) {
    case 'SUBTITLES':
      return [
        { id: ProcessingStage.DOWNLOAD, label: 'upload_video', icon: 'Upload' },
        { id: ProcessingStage.TRANSCRIPTION, label: 'analyze_audio', icon: 'FileAudio' },
        { id: ProcessingStage.TRANSLATION, label: 'translate_text', icon: 'Languages' },
        { id: ProcessingStage.SUBTITLE_GENERATION, label: 'generate_subs', icon: 'FileText' },
        { id: ProcessingStage.FINALIZING, label: 'complete', icon: 'CheckCircle' },
      ];

    case 'DUBBING':
      return [
        { id: ProcessingStage.DOWNLOAD, label: 'upload_video', icon: 'Upload' },
        { id: ProcessingStage.TRANSCRIPTION, label: 'analyze_audio', icon: 'FileAudio' },
        { id: ProcessingStage.TRANSLATION, label: 'translate_text', icon: 'Languages' },
        { id: ProcessingStage.VOICE_GENERATION, label: 'generate_voice', icon: 'Mic' },
        { id: ProcessingStage.SYNCING, label: 'sync_merge', icon: 'RefreshCw' },
        { id: ProcessingStage.FINALIZING, label: 'complete', icon: 'CheckCircle' },
      ];

    case 'BOTH':
    default:
      return [
        { id: ProcessingStage.DOWNLOAD, label: 'upload_video', icon: 'Upload' },
        { id: ProcessingStage.TRANSCRIPTION, label: 'analyze_audio', icon: 'FileAudio' },
        { id: ProcessingStage.TRANSLATION, label: 'translate_text', icon: 'Languages' },
        { id: ProcessingStage.SUBTITLE_GENERATION, label: 'generate_subs', icon: 'FileText' },
        { id: ProcessingStage.VOICE_GENERATION, label: 'generate_voice', icon: 'Mic' },
        { id: ProcessingStage.SYNCING, label: 'sync_merge', icon: 'RefreshCw' },
        { id: ProcessingStage.FINALIZING, label: 'complete', icon: 'CheckCircle' },
      ];
  }
};

export const MOCK_YOUTUBE_THUMBNAIL = "https://picsum.photos/800/450";

export const TRANSLATIONS = {
  ar: {
    appTitle: "دبلجة العرب",
    home: "الرئيسية",
    featuresNav: "المميزات",
    faqNav: "الأسئلة الشائعة",
    contactNav: "تواصل معنا",
    howItWorks: "كيف يعمل؟",
    myVideosTitle: "فيديوهاتي",
    login: "تسجيل دخول",
    logout: "تسجيل خروج",
    settings: "الإعدادات",
    heroBadge: "مجاني بالكامل 100%",
    heroTitle: "دبلج وترجم فيديوهاتك",
    heroHighlight: "بذكاء اصطناعي متطور",
    heroDesc: "حول أي فيديو يوتيوب إلى اللغة العربية. اختر بين الدبلجة الصوتية الكاملة، أو ملفات الترجمة، أو كليهما معاً بضغطة زر.",
    placeholder: "ضع رابط فيديو يوتيوب هنا...",
    startBtn: "ابدأ المعالجة",
    features: ['ترجمة دقيقة', 'دبلجة صوتية', 'ملفات SRT', 'مجاني للأبد'],

    // Service Modes
    modeDubbing: "دبلجة صوتية",
    modeDubbingDesc: "تحويل صوت المتحدث إلى العربية مع مزامنة الشفاه.",
    modeSubtitles: "ترجمة (Subtitles)",
    modeSubtitlesDesc: "إنشاء ملفات ترجمة وعرضها على الفيديو.",
    modeBoth: "شامل (دبلجة + ترجمة)",
    modeBothDesc: "أفضل تجربة: صوت عربي مع نصوص مترجمة.",

    processingTitle: "جاري معالجة الفيديو",
    geminiAnalysis: "تحليل Gemini الذكي",
    successTitle: "تمت العملية بنجاح!",
    successDesc: "الفيديو الخاص بك جاهز للمشاهدة والتحميل.",
    dubbedBadge: "تمت المعالجة",
    exportOptions: "خيارات التصدير",
    downloadVideo: "تحميل الفيديو (MP4)",
    downloadAudio: "تحميل الصوت فقط (WAV)",
    downloadSub: "ملف الترجمة (SRT)",
    share: "مشاركة",
    dubAnother: "معالجة فيديو آخر",
    errorTitle: "عذراً، فشلت العملية",
    returnHome: "العودة للرئيسية",
    // My Videos
    noVideos: "لا توجد فيديوهات محفوظة",
    noVideosDesc: "لم تقم بدبلجة أي فيديو في هذا الحساب حتى الآن. ابدأ الآن!",
    watchBtn: "مشاهدة النتيجة",

    // Auth
    welcomeBack: "مرحباً بعودتك",
    loginDesc: "سجل الدخول للمتابعة إلى دبلجة العرب",
    googleLogin: "المتابعة باستخدام Google",
    icloudLogin: "المتابعة باستخدام iCloud",
    noAccount: "ليس لديك حساب؟",
    signUp: "إنشاء حساب",
    emailLabel: "البريد الإلكتروني",
    passwordLabel: "كلمة المرور",
    nameLabel: "الاسم الكامل",
    orDivider: "أو الاستمرار باستخدام",
    haveAccount: "لديك حساب بالفعل؟",
    loginLink: "سجل دخولك",
    signUpLink: "أنشئ حساباً",
    submitLogin: "تسجيل الدخول",
    submitSignUp: "إنشاء الحساب",
    createAccountTitle: "إنشاء حساب جديد",
    createAccountDesc: "انضم إلينا لتبدأ رحلة الدبلجة",
    // Steps
    download_video: 'تحميل الفيديو',
    analyze_audio: 'تحليل الصوت (Whisper)',
    translate_text: 'ترجمة النص (AI)',
    generate_voice: 'توليد الدبلجة',
    generate_subs: 'تنسيق الترجمة',
    sync_merge: 'مزامنة ودمج',
    // How It Works
    howTitle: "كيف تعمل منصة دبلجة العرب؟",
    howDesc: "نستخدم سلسلة معقدة من نماذج الذكاء الاصطناعي لتقديم أفضل نتيجة مجانًا",
    step1Title: "تحليل الفيديو",
    step1Desc: "نقوم بتحميل الفيديو وفصل المسار الصوتي وتحليله.",
    step2Title: "النسخ والترجمة",
    step2Desc: "يتم تحويل الكلام لنص باستخدام Whisper ثم ترجمته بدقة.",
    step3Title: "المعالجة (صوت/نص)",
    step3Desc: "بناءً على اختيارك، نقوم بتوليد صوت بشري أو ملفات ترجمة.",
    step4Title: "الدمج النهائي",
    step4Desc: "دمج المسارات الجديدة مع الفيديو الأصلي بدقة عالية.",
    // Marketing Sections & Features Page
    featuresSectionTitle: "لماذا تختار دبلجة العرب؟",
    featuresSectionDesc: "حلول متكاملة للدبلجة والترجمة في منصة واحدة.",
    featureCards: [
      { title: "حرية الاختيار", desc: "لست مجبراً على الدبلجة فقط، يمكنك طلب ملفات الترجمة فقط أو كليهما." },
      { title: "مجاني بالكامل", desc: "استمتع بجميع الميزات المتقدمة دون دفع أي رسوم أو اشتراكات مخفية." },
      { title: "استنساخ الصوت", desc: "نحافظ على نبرة المتحدث الأصلي وخامة صوته لتبدو الدبلجة طبيعية تماماً." },
      { title: "ترجمة دقيقة", desc: "نستخدم نماذج لغوية تفهم السياق لإنتاج ترجمات صحيحة لغوياً وثقافياً." },
      { title: "سرعة خيالية", desc: "فيديو مدته ساعة يتم دبلجته في دقائق معدودة بفضل معالجاتنا السحابية." },
      { title: "جودة 4K", desc: "نحافظ على جودة الفيديو الأصلية دون أي فقدان في الوضوح." }
    ],
    useCasesTitle: "لمن بنينا دبلجة العرب؟",
    useCases: [
      { title: "صناع المحتوى", desc: "وسع جمهورك للوطن العربي وضاعف مشاهداتك." },
      { title: "المنصات التعليمية", desc: "ترجم الكورسات العالمية لطلابك بضغطة زر." },
      { title: "المسوقين", desc: "استخدم إعلانات عالمية ناجحة وأعد إطلاقها محلياً." }
    ],
    ctaTitle: "جاهز لتجربة السحر؟",
    ctaDesc: "انضم إلينا وابدأ دبلجة وترجمة الفيديو الأول مجاناً وبدون أي قيود.",
    ctaBtn: "ابدأ الآن",

    // FAQ
    faqTitle: "الأسئلة الشائعة",
    faqDesc: "إجابات على الأسئلة الأكثر شيوعاً حول دبلجة العرب",
    faqItems: [
      { q: "هل الخدمة مجانية حقاً؟", a: "نعم، دبلجة العرب مجانية بالكامل بنسبة 100% ولا توجد أي رسوم مخفية." },
      { q: "ما هي المدة المسموح بها للفيديو؟", a: "ندعم حالياً الفيديوهات التي تصل مدتها إلى ساعتين." },
      { q: "هل تدعمون لغات غير الإنجليزية؟", a: "حالياً ندعم التحويل من الإنجليزية إلى العربية، وقريباً سندعم المزيد من اللغات." },
      { q: "كيف يتم التعامل مع الخصوصية؟", a: "نحن لا نحتفظ بالفيديوهات الأصلية، ويتم حذف الملفات المعالجة بعد 24 ساعة من خوادمنا." },
      { q: "هل يمكنني تحميل ملف الترجمة فقط؟", a: "نعم، يمكنك اختيار وضع 'ترجمة' والحصول على ملف SRT فقط." }
    ],

    // Contact
    contactTitle: "تواصل معنا",
    contactDesc: "نحن هنا لمساعدتك. تواصل معنا لأي استفسار أو اقتراح.",
    contactName: "الاسم",
    contactEmail: "البريد الإلكتروني",
    contactMsg: "الرسالة",
    contactSubmit: "إرسال الرسالة",
    contactSuccess: "تم إرسال رسالتك بنجاح!"
  },
  en: {
    appTitle: "Arab Dubbing",
    home: "Home",
    featuresNav: "Features",
    faqNav: "FAQ",
    contactNav: "Contact",
    howItWorks: "How it Works",
    myVideosTitle: "My Videos",
    login: "Login",
    logout: "Logout",
    settings: "Settings",
    heroBadge: "100% Free Forever",
    heroTitle: "Dub & Translate Videos",
    heroHighlight: "Using Advanced AI",
    heroDesc: "Convert any YouTube video to Arabic. Choose between full AI Dubbing, Subtitles, or Both. Completely free.",
    placeholder: "Paste YouTube link here...",
    startBtn: "Start Processing",
    features: ['Accurate Translation', 'AI Dubbing', 'SRT Subtitles', 'Always Free'],

    // Service Modes
    modeDubbing: "AI Dubbing",
    modeDubbingDesc: "Convert speech to Arabic with lip-sync.",
    modeSubtitles: "Subtitles",
    modeSubtitlesDesc: "Generate and burn captions onto video.",
    modeBoth: "All-in-One",
    modeBothDesc: "Best experience: Arabic Audio + Subtitles.",

    processingTitle: "Processing Video",
    geminiAnalysis: "Gemini Smart Analysis",
    successTitle: "Processing Complete!",
    successDesc: "Your video is ready to watch and download.",
    dubbedBadge: "Processed",
    exportOptions: "Export Options",
    downloadVideo: "Download Video (MP4)",
    downloadAudio: "Download Audio (WAV)",
    downloadSub: "Subtitle File (SRT)",
    share: "Share",
    dubAnother: "Process Another Video",
    errorTitle: "Oops, process failed",
    returnHome: "Return Home",
    // My Videos
    noVideos: "No videos saved",
    noVideosDesc: "You haven't dubbed any videos on this account yet. Start now!",
    watchBtn: "Watch Result",

    // Auth
    welcomeBack: "Welcome Back",
    loginDesc: "Sign in to continue to Arab Dubbing",
    googleLogin: "Continue with Google",
    icloudLogin: "Continue with iCloud",
    noAccount: "Don't have an account?",
    signUp: "Sign Up",
    emailLabel: "Email Address",
    passwordLabel: "Password",
    nameLabel: "Full Name",
    orDivider: "Or continue with",
    haveAccount: "Already have an account?",
    loginLink: "Log in",
    signUpLink: "Sign up",
    submitLogin: "Sign In",
    submitSignUp: "Create Account",
    createAccountTitle: "Create Account",
    createAccountDesc: "Join us to start dubbing",
    // Steps
    download_video: 'Download Video',
    analyze_audio: 'Audio Analysis',
    translate_text: 'Translation (AI)',
    generate_voice: 'Voice Dubbing',
    generate_subs: 'Subtitle Formatting',
    sync_merge: 'Sync & Merge',
    // How It Works
    howTitle: "How Arab Dubbing Works?",
    howDesc: "We use a complex chain of AI models to deliver the best results for free",
    step1Title: "Video Analysis",
    step1Desc: "We download the video, separate audio track and analyze it.",
    step2Title: "Transcription & Translation",
    step2Desc: "Speech to text using Whisper, then accurate translation.",
    step3Title: "Processing",
    step3Desc: "Depending on choice: generating AI voice or subtitle tracks.",
    step4Title: "Final Merge",
    step4Desc: "Merging new tracks with original video seamlessly.",
    // Marketing Sections & Features
    featuresSectionTitle: "Why Choose Arab Dubbing?",
    featuresSectionDesc: "Complete solution for Dubbing and Translation.",
    featureCards: [
      { title: "Your Choice", desc: "Not forced to dub. Choose subtitles only if you prefer keeping original audio." },
      { title: "Completely Free", desc: "Enjoy all premium features without paying any fees or hidden subscriptions." },
      { title: "Voice Cloning", desc: "We preserve the original speaker's tone and texture for 100% natural results." },
      { title: "Context Aware", desc: "We don't just translate words; we translate meaning using advanced LLMs." },
      { title: "Blazing Fast", desc: "A one-hour video takes minutes to process using our cloud GPUs." },
      { title: "4K Quality", desc: "We maintain the original video fidelity with zero quality loss." }
    ],
    useCasesTitle: "Who is this for?",
    useCases: [
      { title: "Content Creators", desc: "Expand to the Arab world and double your views." },
      { title: "EdTech Platforms", desc: "Translate global courses for your students instantly." },
      { title: "Marketers", desc: "Localize successful global ads for the MENA region." }
    ],
    ctaTitle: "Ready to experience the magic?",
    ctaDesc: "Join us and start dubbing your first video for free without limits.",
    ctaBtn: "Start Now",

    // FAQ
    faqTitle: "Frequently Asked Questions",
    faqDesc: "Answers to the most common questions about Arab Dubbing",
    faqItems: [
      { q: "Is the service really free?", a: "Yes, Arab Dubbing is 100% free with no hidden fees." },
      { q: "What is the max video length?", a: "We currently support videos up to 2 hours long." },
      { q: "Do you support languages other than English?", a: "Currently we support English to Arabic, with more languages coming soon." },
      { q: "How is privacy handled?", a: "We do not keep original videos. Processed files are deleted from our servers after 24 hours." },
      { q: "Can I download just the subtitles?", a: "Yes, you can choose 'Subtitles' mode and get the SRT file only." }
    ],

    // Contact
    contactTitle: "Contact Us",
    contactDesc: "We're here to help. Reach out to us for any questions or suggestions.",
    contactName: "Name",
    contactEmail: "Email",
    contactMsg: "Message",
    contactSubmit: "Send Message",
    contactSuccess: "Your message has been sent successfully!"
  }
};
