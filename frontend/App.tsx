
import React, { useState, useEffect, useCallback } from 'react';
import { Youtube, Wand2, Sparkles, AlertCircle, Mic, FileText, Layers } from 'lucide-react';
import { Header } from './components/Header';
import { Button } from './components/Button';
import { StageStepper } from './components/StageStepper';
import { ResultPlayer } from './components/ResultPlayer';
import { AuthPage } from './components/AuthPage';
import { HowItWorksPage } from './components/HowItWorksPage';
import { FeaturesPage } from './components/FeaturesPage';
import { FAQPage } from './components/FAQPage';
import { ContactPage } from './components/ContactPage';
import { MarketingSections } from './components/MarketingSections';
import { MyVideosPage } from './components/MyVideosPage';
import { simulateProcessing } from './services/mockBackend';
import { generateVideoInsights } from './services/geminiService';
import { ProcessingState, ProcessingStage, VideoMetadata, TaskStatus, Language, Theme, User, AppView, ServiceMode, HistoryItem } from './types';
import { MOCK_YOUTUBE_THUMBNAIL, TRANSLATIONS, getStepsForMode } from './constants';

function App() {
  // --- State Management ---
  const [url, setUrl] = useState('');
  const [mode, setMode] = useState<ServiceMode>('DUBBING'); // Default mode
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
  const [user, setUser] = useState<User | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);

  // Translations shortcut
  const t = TRANSLATIONS[lang];

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
    const youtubeRegex = /^(https?\:\/\/)?(www\.)?(youtube\.com|youtu\.?be)\/.+$/;
    
    if (!youtubeRegex.test(cleanUrl)) {
      setErrorMsg(lang === 'ar' ? "الرجاء إدخال رابط يوتيوب صحيح" : "Please enter a valid YouTube URL");
      return;
    }

    setState(ProcessingState.VALIDATING);
    
    // 2. Fetch Gemini Insights
    try {
      const insights = await generateVideoInsights(cleanUrl);
      setMetadata({
        url: cleanUrl,
        title: insights.title,
        smartSummary: insights.summary,
        thumbnail: MOCK_YOUTUBE_THUMBNAIL,
        mode: mode // Save selected mode in metadata
      });
      
      // 3. Move to Queue/Processing
      setState(ProcessingState.PROCESSING);
    } catch (err) {
      console.error(err);
      setErrorMsg(lang === 'ar' ? "حدث خطأ أثناء تحليل الفيديو" : "Error analyzing video");
      setState(ProcessingState.IDLE);
    }
  };

  // Effect to manage polling when state is PROCESSING
  useEffect(() => {
    if (state === ProcessingState.PROCESSING) {
      const stopSimulation = simulateProcessing(
        mode,
        (status) => setTaskStatus(status),
        () => setState(ProcessingState.COMPLETED),
        (msg) => {
          setErrorMsg(msg);
          setState(ProcessingState.FAILED);
        }
      );
      return () => stopSimulation();
    }
  }, [state, mode]);

  // Effect to save history when completed
  useEffect(() => {
    if (state === ProcessingState.COMPLETED && metadata && user) {
        // Simple check to avoid duplicates in this session based on exact URL and title
        setHistory(prev => {
            const exists = prev.some(item => item.url === metadata.url && item.mode === metadata.mode);
            if (exists) return prev;

            const newItem: HistoryItem = {
                id: Date.now().toString(),
                title: metadata.title || 'Video',
                thumbnail: metadata.thumbnail || '',
                date: new Date().toLocaleDateString(lang === 'ar' ? 'ar-EG' : 'en-US'),
                url: metadata.url,
                mode: metadata.mode,
                smartSummary: metadata.smartSummary
            };
            return [newItem, ...prev];
        });
    }
  }, [state, metadata, user, lang]);

  const handleReset = useCallback(() => {
    setUrl('');
    setState(ProcessingState.IDLE);
    setMetadata(null);
    setTaskStatus({ taskId: '', progress: 0, stage: ProcessingStage.DOWNLOAD, message: '' });
    setErrorMsg('');
  }, []);

  const handleLoginSuccess = (provider: string) => {
    setUser({
      id: '123',
      name: provider === 'google' ? 'Ahmed Ali' : 'User iCloud',
      email: 'ahmed@example.com'
    });
    // Add mock history for demonstration
    setHistory([
        {
            id: 'mock-1',
            title: lang === 'ar' ? 'شرح الذكاء الاصطناعي للمبتدئين' : 'AI for Beginners',
            thumbnail: 'https://picsum.photos/seed/ai/800/450',
            date: '2023-11-20',
            url: 'https://youtube.com/watch?v=mock1',
            mode: 'DUBBING',
            smartSummary: lang === 'ar' ? 'مقدمة شاملة عن تقنيات الذكاء الاصطناعي الحديثة.' : 'Comprehensive intro to modern AI.'
        },
        {
            id: 'mock-2',
            title: lang === 'ar' ? 'أفضل وصفات الطبخ الصحي' : 'Best Healthy Recipes',
            thumbnail: 'https://picsum.photos/seed/food/800/450',
            date: '2023-10-15',
            url: 'https://youtube.com/watch?v=mock2',
            mode: 'SUBTITLES',
            smartSummary: lang === 'ar' ? 'طريقة تحضير وجبات سريعة وصحية.' : 'How to prepare fast healthy meals.'
        }
    ]);
    setView('HOME');
  };

  const handleLogout = () => {
    setUser(null);
    setHistory([]);
    setView('HOME');
  };

  const scrollToTop = () => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  // Custom navigation handler to ensure we reset state when going HOME
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
    // Skip processing and go straight to completed
    setState(ProcessingState.COMPLETED);
    setView('HOME'); // ResultPlayer is part of HOME view logic
    scrollToTop();
  };

  const renderContent = () => {
    switch(view) {
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

      case 'HOME':
      default:
        return (
          <>
            {/* State 1: IDLE / INPUT */}
            {state === ProcessingState.IDLE || state === ProcessingState.VALIDATING ? (
              <div className="w-full space-y-16 animate-in fade-in zoom-in duration-500">
                
                {/* HERO SECTION */}
                <div className="max-w-4xl mx-auto text-center space-y-8">
                  <div className="space-y-6">
                    <div className="inline-flex items-center px-4 py-1.5 rounded-full bg-indigo-50 dark:bg-indigo-500/10 border border-indigo-200 dark:border-indigo-500/20 text-indigo-600 dark:text-indigo-400 text-sm font-bold shadow-sm">
                      <Sparkles className="w-4 h-4 ltr:mr-2 rtl:ml-2" />
                      {t.heroBadge}
                    </div>
                    <h1 className="text-5xl md:text-7xl font-black leading-tight text-slate-900 dark:text-white tracking-tight">
                      {t.heroTitle} <br />
                      <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-600 via-purple-600 to-indigo-600 animate-gradient-x">
                        {t.heroHighlight}
                      </span>
                    </h1>
                    <p className="text-xl md:text-2xl text-slate-600 dark:text-slate-400 max-w-2xl mx-auto leading-relaxed font-light">
                      {t.heroDesc}
                    </p>
                  </div>

                  <div className="mt-10 max-w-2xl mx-auto space-y-6">
                    {/* URL Input */}
                    <div className="relative group">
                        <div className="absolute -inset-1 bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500 rounded-2xl blur-lg opacity-30 group-hover:opacity-50 transition duration-1000"></div>
                        <div className="relative bg-white dark:bg-slate-900 rounded-2xl p-2 flex items-center shadow-2xl border border-slate-200 dark:border-slate-800">
                        <div className="pl-5 pr-3 text-slate-400">
                            <Youtube className="w-7 h-7" />
                        </div>
                        <input
                            type="text"
                            placeholder={t.placeholder}
                            className="flex-grow bg-transparent border-none text-slate-900 dark:text-white placeholder-slate-400 focus:ring-0 text-lg py-4 font-medium outline-none"
                            value={url}
                            onChange={handleInputChange}
                            dir="ltr"
                        />
                        </div>
                    </div>
                    
                    {/* Mode Selection Cards */}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                       <button 
                         onClick={() => setMode('DUBBING')}
                         className={`p-4 rounded-xl border-2 text-start transition-all duration-200 flex flex-col gap-2 ${mode === 'DUBBING' ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-900/20 ring-2 ring-indigo-500/20' : 'border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 hover:border-indigo-300'}`}
                       >
                          <div className={`p-2 rounded-lg w-fit ${mode === 'DUBBING' ? 'bg-indigo-500 text-white' : 'bg-slate-100 dark:bg-slate-700 text-slate-500'}`}>
                             <Mic className="w-5 h-5" />
                          </div>
                          <div>
                            <div className="font-bold text-slate-900 dark:text-white">{t.modeDubbing}</div>
                            <div className="text-xs text-slate-500 dark:text-slate-400 mt-1">{t.modeDubbingDesc}</div>
                          </div>
                       </button>

                       <button 
                         onClick={() => setMode('SUBTITLES')}
                         className={`p-4 rounded-xl border-2 text-start transition-all duration-200 flex flex-col gap-2 ${mode === 'SUBTITLES' ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-900/20 ring-2 ring-indigo-500/20' : 'border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 hover:border-indigo-300'}`}
                       >
                          <div className={`p-2 rounded-lg w-fit ${mode === 'SUBTITLES' ? 'bg-indigo-500 text-white' : 'bg-slate-100 dark:bg-slate-700 text-slate-500'}`}>
                             <FileText className="w-5 h-5" />
                          </div>
                          <div>
                            <div className="font-bold text-slate-900 dark:text-white">{t.modeSubtitles}</div>
                            <div className="text-xs text-slate-500 dark:text-slate-400 mt-1">{t.modeSubtitlesDesc}</div>
                          </div>
                       </button>

                       <button 
                         onClick={() => setMode('BOTH')}
                         className={`p-4 rounded-xl border-2 text-start transition-all duration-200 flex flex-col gap-2 ${mode === 'BOTH' ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-900/20 ring-2 ring-indigo-500/20' : 'border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 hover:border-indigo-300'}`}
                       >
                          <div className={`p-2 rounded-lg w-fit ${mode === 'BOTH' ? 'bg-indigo-500 text-white' : 'bg-slate-100 dark:bg-slate-700 text-slate-500'}`}>
                             <Layers className="w-5 h-5" />
                          </div>
                          <div>
                            <div className="font-bold text-slate-900 dark:text-white">{t.modeBoth}</div>
                            <div className="text-xs text-slate-500 dark:text-slate-400 mt-1">{t.modeBothDesc}</div>
                          </div>
                       </button>
                    </div>

                    <Button 
                        onClick={handleStart} 
                        isLoading={state === ProcessingState.VALIDATING}
                        className="w-full h-14 text-xl shadow-xl shadow-indigo-500/20"
                    >
                        {t.startBtn}
                    </Button>

                  </div>

                  {errorMsg && (
                    <div className="flex items-center justify-center text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-400/10 border border-red-200 dark:border-transparent p-3 rounded-xl animate-pulse max-w-md mx-auto">
                      <AlertCircle className="w-5 h-5 ltr:mr-2 rtl:ml-2" />
                      {errorMsg}
                    </div>
                  )}
                </div>
                
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
                    <StageStepper currentStage={taskStatus.stage} t={t} />
                    
                    <div className="mt-8 space-y-2">
                      <div className="flex justify-between text-sm font-medium text-slate-500 dark:text-slate-400">
                        <span>{taskStatus.message}</span>
                        <span>{Math.round(taskStatus.progress)}%</span>
                      </div>
                      <div className="h-2 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                        <div 
                          className="h-full bg-gradient-to-l from-indigo-500 to-purple-500 transition-all duration-300 ease-out"
                          style={{ width: `${taskStatus.progress}%` }}
                        ></div>
                      </div>
                    </div>
                </div>
              </div>
            )}

            {/* State 3: COMPLETED */}
            {state === ProcessingState.COMPLETED && (
              <div className="py-12 w-full">
                <ResultPlayer metadata={metadata} onReset={handleReset} t={t} />
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
        user={user}
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
