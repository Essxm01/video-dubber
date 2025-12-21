
import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Youtube, Wand2, Sparkles, AlertCircle, Mic, FileText, Layers, Upload } from 'lucide-react';
import { Header } from './components/Header';
import { Button } from './components/Button';
import { StageStepper } from './components/StageStepper';
import { ResultPlayer } from './components/ResultPlayer';
import { SmartVideoPlayer } from './components/SmartVideoPlayer'; // NEW
import { AuthPage } from './components/AuthPage';
import { HowItWorksPage } from './components/HowItWorksPage';
import { FeaturesPage } from './components/FeaturesPage';
import { FAQPage } from './components/FAQPage';
import { ContactPage } from './components/ContactPage';
import { MarketingSections } from './components/MarketingSections';
import { MyVideosPage } from './components/MyVideosPage';
import { SettingsPage } from './components/SettingsPage';
import { MainInterface } from './components/MainInterface';
import { startRealProcessing, checkBackendHealth, BACKEND_URL, uploadVideo, getTaskStatus } from './services/apiService';
import { generateVideoInsights } from './services/geminiService';
import { useAuth } from './contexts/AuthContext';
import { useToast } from './components/ToastContext';
import { ProcessingState, ProcessingStage, VideoMetadata, TaskStatus, Language, Theme, AppView, ServiceMode, HistoryItem } from './types';
import { MOCK_YOUTUBE_THUMBNAIL, TRANSLATIONS, getStepsForMode } from './constants';

function App() {
  // --- State Management ---
  const [url, setUrl] = useState('');
  const [mode, setMode] = useState<ServiceMode>('DUBBING');
  const [state, setState] = useState<ProcessingState>(ProcessingState.IDLE);
  const [taskStatus, setTaskStatus] = useState<TaskStatus>({
    taskId: '',
    progress: 0,
    stage: ProcessingStage.DOWNLOAD,
    message: ''
  });
  const [metadata, setMetadata] = useState<VideoMetadata | null>(null);
  const [errorMsg, setErrorMsg] = useState('');

  // Settings & Auth
  const [lang, setLang] = useState<Language>('ar');
  const [theme, setTheme] = useState<Theme>('light');
  const [view, setView] = useState<AppView>('HOME');
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null);

  // File Upload state
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Cleanup function ref
  const [stopProcessing, setStopProcessing] = useState<(() => void) | null>(null);

  // Auth & Toast hooks
  const { user, isAuthenticated, signOut, loading: authLoading } = useAuth();
  const { showSuccess, showError, showWarning, showInfo } = useToast();

  // Translations shortcut
  const t = TRANSLATIONS[lang];

  // --- Check Backend Health ---
  useEffect(() => {
    const checkHealth = async () => {
      try {
        const isHealthy = await checkBackendHealth();
        setBackendOnline(isHealthy);
        if (!isHealthy) {
          console.warn('⚠️ Backend is offline');
        }
      } catch {
        setBackendOnline(false);
      }
    };
    checkHealth();
  }, []);

  // --- Theme Effect ---
  useEffect(() => {
    const root = window.document.documentElement;
    if (theme === 'dark') {
      root.classList.add('dark');
    } else {
      root.classList.remove('dark');
    }
  }, [theme]);

  // --- Language Effect (Direction) ---
  useEffect(() => {
    const root = window.document.documentElement;
    root.setAttribute('lang', lang);
    root.setAttribute('dir', lang === 'ar' ? 'rtl' : 'ltr');
  }, [lang]);

  // Handle Input Change
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setUrl(e.target.value);
    if (errorMsg) setErrorMsg('');
  };

  // Start Process
  const handleStart = async () => {
    // 1. Validation
    const cleanUrl = url.trim();
    const youtubeRegex = /^(https?:\/\/)?(www\.)?(youtube\.com|youtu\.?be)\/.+$/;

    if (!youtubeRegex.test(cleanUrl)) {
      setErrorMsg(lang === 'ar' ? "الرجاء إدخال رابط يوتيوب صحيح" : "Please enter a valid YouTube URL");
      showError(lang === 'ar' ? "رابط غير صالح" : "Invalid URL");
      return;
    }

    // Check backend
    if (backendOnline === false) {
      showError(lang === 'ar' ? "الخادم غير متصل. جاري المحاولة..." : "Server offline. Retrying...");
      const isHealthy = await checkBackendHealth();
      if (!isHealthy) {
        setErrorMsg(lang === 'ar' ? "تعذر الاتصال بالخادم" : "Cannot connect to server");
        return;
      }
      setBackendOnline(true);
    }

    setState(ProcessingState.VALIDATING);

    // 2. Fetch Gemini Insights (optional - for nice UX)
    try {
      const insights = await generateVideoInsights(cleanUrl);
      setMetadata({
        url: cleanUrl,
        title: insights.title,
        smartSummary: insights.summary,
        thumbnail: MOCK_YOUTUBE_THUMBNAIL,
        mode: mode
      });
    } catch (err) {
      // Continue without Gemini insights
      setMetadata({
        url: cleanUrl,
        title: 'جاري المعالجة...',
        smartSummary: '',
        thumbnail: MOCK_YOUTUBE_THUMBNAIL,
        mode: mode
      });
    }

    // 3. Start REAL backend processing
    setState(ProcessingState.PROCESSING);
    showInfo(lang === 'ar' ? 'بدأت معالجة الفيديو...' : 'Processing started...');

    try {
      const cleanup = startRealProcessing(
        cleanUrl,
        mode,
        (status) => {
          setTaskStatus(status);
        },
        (result) => {
          // Success callback - UPDATE URL WITH DUBBED VIDEO
          setMetadata(prev => prev ? {
            ...prev,
            title: result?.title || prev.title,
            thumbnail: result?.thumbnail || prev.thumbnail,
            url: result?.dubbed_video_url || prev.url,
          } : null);
          console.log('📹 Result URL:', result?.dubbed_video_url);
          setState(ProcessingState.COMPLETED);
          showSuccess(lang === 'ar' ? 'تمت الدبلجة بنجاح! 🎉' : 'Dubbing completed! 🎉');

          // Save to history if authenticated
          if (isAuthenticated && user) {
            const newItem: HistoryItem = {
              id: Date.now().toString(),
              title: result?.title || metadata?.title || 'Video',
              thumbnail: result?.thumbnail || metadata?.thumbnail || '',
              date: new Date().toLocaleDateString(lang === 'ar' ? 'ar-EG' : 'en-US'),
              url: cleanUrl,
              mode: mode,
              smartSummary: metadata?.smartSummary
            };
            setHistory(prev => [newItem, ...prev]);
          }
        },
        (errorMessage) => {
          // Error callback
          setErrorMsg(errorMessage);
          setState(ProcessingState.FAILED);
          showError(errorMessage);
        }
      );

      setStopProcessing(() => cleanup);
    } catch (err: any) {
      setErrorMsg(err.message || 'حدث خطأ غير متوقع');
      setState(ProcessingState.FAILED);
      showError(err.message || 'حدث خطأ غير متوقع');
    }
  };

  // Handle file selection
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      // Validate file size (500MB max)
      if (file.size > 500 * 1024 * 1024) {
        showError(lang === 'ar' ? 'حجم الملف كبير جداً. الحد الأقصى 500MB' : 'File too large. Max 500MB');
        return;
      }
      setUploadedFile(file);
      showSuccess(lang === 'ar' ? `تم اختيار: ${file.name}` : `Selected: ${file.name}`);
    }
  };

  // Handle direct file upload (bypasses YouTube)
  const handleFileUpload = async (fileToUpload?: File, selectedMode?: ServiceMode) => {
    const file = fileToUpload || uploadedFile;
    const modeToUse = selectedMode || mode;

    if (!file) {
      showError(lang === 'ar' ? 'الرجاء اختيار ملف فيديو' : 'Please select a video file');
      return;
    }

    // Check backend
    if (backendOnline === false) {
      showError(lang === 'ar' ? 'الخادم غير متصل' : 'Server offline');
      return;
    }

    setState(ProcessingState.VALIDATING);
    showInfo(lang === 'ar' ? 'جاري رفع الفيديو...' : 'Uploading video...');

    setMetadata({
      url: '',
      title: file.name,
      smartSummary: '',
      thumbnail: '',
      mode: modeToUse
    });

    setMode(modeToUse);

    setState(ProcessingState.PROCESSING);

    try {
      const { taskId, success, error } = await uploadVideo(file, modeToUse, 'ar');

      if (!success || !taskId) {
        setErrorMsg(error || 'فشل رفع الملف');
        setState(ProcessingState.FAILED);
        showError(error || 'فشل رفع الملف');
        return;
      }

      showSuccess(lang === 'ar' ? 'تم رفع الفيديو! جاري المعالجة...' : 'Upload complete! Processing...');

      // Start polling for status
      const pollInterval = setInterval(async () => {
        try {
          const { status, completed, failed, result } = await getTaskStatus(taskId);
          setTaskStatus(status);

          if (completed) {
            clearInterval(pollInterval);
            // UPDATE URL WITH DUBBED VIDEO
            setMetadata(prev => prev ? {
              ...prev,
              title: result?.title || prev.title,
              thumbnail: result?.thumbnail || prev.thumbnail,
              url: result?.dubbed_video_url || prev.url,
            } : null);
            console.log('📹 Result URL:', result?.dubbed_video_url);
            setState(ProcessingState.COMPLETED);
            showSuccess(lang === 'ar' ? 'تمت الدبلجة بنجاح! 🎉' : 'Dubbing completed! 🎉');
            setUploadedFile(null);
          } else if (failed) {
            clearInterval(pollInterval);
            setErrorMsg(status.message || 'فشلت المعالجة');
            setState(ProcessingState.FAILED);
            showError(status.message || 'فشلت المعالجة');
          }
        } catch (err) {
          console.error('Polling error:', err);
        }
      }, 1500);

      setStopProcessing(() => () => clearInterval(pollInterval));

    } catch (err: any) {
      setErrorMsg(err.message || 'حدث خطأ غير متوقع');
      setState(ProcessingState.FAILED);
      showError(err.message || 'حدث خطأ غير متوقع');
    }
  };

  // Cleanup on unmount or reset
  useEffect(() => {
    return () => {
      if (stopProcessing) {
        stopProcessing();
      }
    };
  }, [stopProcessing]);

  const handleReset = useCallback(() => {
    if (stopProcessing) {
      stopProcessing();
      setStopProcessing(null);
    }
    setUrl('');
    setState(ProcessingState.IDLE);
    setMetadata(null);
    setTaskStatus({ taskId: '', progress: 0, stage: ProcessingStage.DOWNLOAD, message: '' });
    setErrorMsg('');
  }, [stopProcessing]);

  const handleLoginSuccess = () => {
    showSuccess(lang === 'ar' ? 'تم تسجيل الدخول بنجاح!' : 'Login successful!');
    setView('HOME');
  };

  const handleLogout = async () => {
    await signOut();
    setHistory([]);
    setView('HOME');
    showInfo(lang === 'ar' ? 'تم تسجيل الخروج' : 'Logged out');
  };

  const scrollToTop = () => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleNavigation = (targetView: AppView) => {
    setView(targetView);
    if (targetView === 'HOME') {
      handleReset();
    }
    scrollToTop();
  };

  const handlePlayHistoryItem = (item: HistoryItem) => {
    setMetadata({
      url: item.url,
      title: item.title,
      thumbnail: item.thumbnail,
      smartSummary: item.smartSummary,
      mode: item.mode
    });
    setState(ProcessingState.COMPLETED);
    setView('HOME');
    scrollToTop();
  };

  const renderContent = () => {
    switch (view) {
      case 'AUTH':
        return (
          <AuthPage
            onLoginSuccess={handleLoginSuccess}
            onBack={() => handleNavigation('HOME')}
            t={t}
          />
        );

      case 'HOW_IT_WORKS':
        return <HowItWorksPage t={t} onBack={() => handleNavigation('HOME')} />;

      case 'FEATURES':
        return <FeaturesPage t={t} onBack={() => handleNavigation('HOME')} />;

      case 'FAQ':
        return <FAQPage t={t} onBack={() => handleNavigation('HOME')} />;

      case 'CONTACT':
        return <ContactPage t={t} onBack={() => handleNavigation('HOME')} />;

      case 'MY_VIDEOS':
        return (
          <MyVideosPage
            history={history}
            t={t}
            onPlay={handlePlayHistoryItem}
            onBack={() => handleNavigation('HOME')}
          />
        );

      case 'SETTINGS':
        return (
          <SettingsPage
            t={t}
            onBack={() => handleNavigation('HOME')}
          />
        );

      case 'HOME':
      default:
        return (
          <>
            {/* State 1: IDLE / INPUT - NEW UNIFIED INTERFACE */}
            {state === ProcessingState.IDLE || state === ProcessingState.VALIDATING ? (
              <div className="w-full space-y-16 animate-in fade-in zoom-in duration-500">

                {/* MainInterface Component */}
                <MainInterface
                  onStartYouTube={(url, selectedMode) => {
                    setUrl(url);
                    setMode(selectedMode);
                    handleStart();
                  }}
                  onStartUpload={(file, selectedMode) => {
                    handleFileUpload(file, selectedMode);
                  }}
                  isLoading={state === ProcessingState.VALIDATING}
                  error={errorMsg}
                  lang={lang}
                  backendOnline={backendOnline}
                />

                {/* MARKETING SECTIONS */}
                <MarketingSections t={t} onStartClick={scrollToTop} />

              </div>
            ) : null}

            {/* State 2: PROCESSING */}
            {state === ProcessingState.PROCESSING && (
              <div className="w-full max-w-3xl space-y-12 animate-in fade-in slide-in-from-bottom-8 duration-700 py-12">
                <div className="text-center space-y-4">
                  <h2 className="text-3xl font-bold text-slate-900 dark:text-white">{t.processingTitle}</h2>
                  {metadata && (
                    <div className="bg-white dark:bg-slate-800/50 p-6 rounded-xl border border-slate-200 dark:border-slate-700 inline-block text-start max-w-2xl shadow-lg">
                      <div className="flex items-center gap-3 mb-2">
                        <h3 className="text-indigo-600 dark:text-indigo-400 text-sm font-bold flex items-center gap-2">
                          <Sparkles className="w-3 h-3" /> {t.geminiAnalysis}
                        </h3>
                        <span className="px-2 py-0.5 rounded text-xs font-bold bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300">
                          {mode === 'DUBBING' ? t.modeDubbing : mode === 'SUBTITLES' ? t.modeSubtitles : t.modeBoth}
                        </span>
                      </div>
                      <p className="font-bold text-slate-900 dark:text-white text-lg mb-1">{metadata.title}</p>
                      <p className="text-slate-600 dark:text-slate-400 text-sm leading-relaxed">{metadata.smartSummary}</p>
                    </div>
                  )}
                </div>

                <div className="bg-white dark:bg-slate-900/50 rounded-2xl p-8 border border-slate-200 dark:border-slate-800 shadow-xl">
                  <StageStepper currentStage={taskStatus.stage} mode={mode} t={t} />

                  {/* NEW: Smart Playlist Player (Progressive Playback) */}
                  <div className="mt-8">
                    <SmartVideoPlayer
                      jobId={taskStatus.taskId}
                      poster={metadata?.thumbnail || MOCK_YOUTUBE_THUMBNAIL}
                      onAllFinished={() => {
                        // Optional: Auto-transition logic could go here, 
                        // but App.tsx main polling handles the state transition to COMPLETED
                      }}
                    />
                  </div>
                </div>

                {/* Cancel button */}
                <div className="text-center">
                  <button
                    onClick={handleReset}
                    className="text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 text-sm font-medium"
                  >
                    {lang === 'ar' ? 'إلغاء المعالجة' : 'Cancel Processing'}
                  </button>
                </div>
              </div>
            )}

            {/* State 3: COMPLETED */}
            {state === ProcessingState.COMPLETED && (
              <div className="py-12 w-full">
                {/* Force remount when URL changes by using key prop */}
                <ResultPlayer key={metadata?.url} metadata={metadata} onReset={handleReset} t={t} />
              </div>
            )}

            {/* State 4: FAILED */}
            {state === ProcessingState.FAILED && (
              <div className="text-center max-w-md animate-in zoom-in duration-300 py-12">
                <div className="w-20 h-20 bg-red-100 dark:bg-red-500/10 rounded-full flex items-center justify-center mx-auto mb-6">
                  <AlertCircle className="w-10 h-10 text-red-600 dark:text-red-500" />
                </div>
                <h2 className="text-2xl font-bold mb-2 text-slate-900 dark:text-white">{t.errorTitle}</h2>
                <p className="text-slate-600 dark:text-slate-400 mb-8">{errorMsg || "حدث خطأ غير متوقع أثناء معالجة الفيديو. يرجى المحاولة مرة أخرى."}</p>
                <Button onClick={handleReset} variant="secondary">
                  {t.returnHome}
                </Button>
              </div>
            )}
          </>
        );
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-[#0f172a] text-slate-900 dark:text-white flex flex-col transition-colors duration-300 font-sans">
      <Header
        lang={lang}
        theme={theme}
        user={user ? { id: user.id, name: user.name || user.email, email: user.email, avatar: user.avatar_url } : null}
        t={t}
        onToggleLang={() => setLang(prev => prev === 'ar' ? 'en' : 'ar')}
        onToggleTheme={() => setTheme(prev => prev === 'light' ? 'dark' : 'light')}
        onLoginClick={() => setView('AUTH')}
        onLogoutClick={handleLogout}
        onNavigate={handleNavigation}
      />

      <main className={`flex-grow container mx-auto px-4 pt-32 ${view === 'AUTH' ? 'flex flex-col items-center justify-center' : 'flex flex-col items-center'}`}>
        {renderContent()}
      </main>

      <footer className="py-12 border-t border-slate-200 dark:border-slate-800 text-center bg-white dark:bg-[#0f172a] mt-auto">
        <div className="container mx-auto px-4">
          <div className="flex flex-col md:flex-row justify-between items-center gap-6">
            <div className="text-2xl font-black text-slate-900 dark:text-white tracking-tight">
              {t.appTitle}
            </div>
            <div className="text-slate-500 dark:text-slate-400 text-sm">
              © 2025 Arab Dubbing AI. All rights reserved.
            </div>
            <div className="flex gap-6">
              <a href="#" className="text-slate-500 hover:text-indigo-600 transition-colors">Twitter</a>
              <a href="#" className="text-slate-500 hover:text-indigo-600 transition-colors">LinkedIn</a>
              <a href="#" className="text-slate-500 hover:text-indigo-600 transition-colors">Instagram</a>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default App;
