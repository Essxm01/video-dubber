
import React, { useState, useRef, useCallback } from 'react';
import { Youtube, Upload, Mic, FileText, Layers, Sparkles, Loader2, AlertCircle, X, CheckCircle2 } from 'lucide-react';
import { ServiceMode } from '../types';

interface MainInterfaceProps {
    onStartYouTube: (url: string, mode: ServiceMode) => void;
    onStartUpload: (file: File, mode: ServiceMode) => void;
    isLoading: boolean;
    error?: string;
    lang: 'ar' | 'en';
    backendOnline: boolean | null;
}

type InputMode = 'youtube' | 'file';

export const MainInterface: React.FC<MainInterfaceProps> = ({
    onStartYouTube,
    onStartUpload,
    isLoading,
    error,
    lang,
    backendOnline,
}) => {
    const [inputMode, setInputMode] = useState<InputMode>('youtube');
    const [selectedService, setSelectedService] = useState<ServiceMode>('DUBBING');
    const [youtubeUrl, setYoutubeUrl] = useState('');
    const [selectedFile, setSelectedFile] = useState<File | null>(null);
    const [isDragging, setIsDragging] = useState(false);
    const fileInputRef = useRef<HTMLInputElement>(null);

    const t = {
        ar: {
            badge: '✨ مجاني بالكامل 100%',
            headline1: 'دبلج وترجم فيديوهاتك',
            headline2: 'بذكاء اصطناعي متطور',
            subheadline: 'حول أي فيديو يوتيوب أو ملف محلي إلى اللغة العربية. اختر بين الدبلجة الصوتية الكاملة، أو ملفات الترجمة، أو كليهما معاً.',
            youtubeTab: 'رابط يوتيوب',
            uploadTab: 'رفع ملف',
            youtubePlaceholder: 'ضع رابط فيديو يوتيوب هنا...',
            dropzoneTitle: 'اسحب وأفلت الفيديو هنا',
            dropzoneSubtitle: 'أو اضغط لاختيار ملف من جهازك',
            dropzoneFormats: 'الحد الأقصى: 25MB • مدعوم: MP4, MKV, WebM, MOV, AVI',
            dubbing: 'دبلجة صوتية',
            dubbingDesc: 'تحويل صوت المتحدث إلى العربية مع مزامنة الشفاه',
            subtitles: 'ترجمة (Subtitles)',
            subtitlesDesc: 'إنشاء ملفات ترجمة وعرضها على الفيديو',
            both: 'شامل (دبلجة + ترجمة)',
            bothDesc: 'أفضل تجربة: صوت عربي مع نصوص مترجمة',
            startBtn: 'ابدأ المعالجة',
            processing: 'جاري المعالجة...',
            fileSelected: 'تم اختيار:',
            removeFile: 'إزالة',
            offlineWarning: 'الخادم غير متصل حالياً',
        },
        en: {
            badge: '✨ 100% Free',
            headline1: 'Dub & Translate Your Videos',
            headline2: 'with Advanced AI',
            subheadline: 'Convert any YouTube video or local file to Arabic. Choose voice dubbing, subtitles, or both.',
            youtubeTab: 'YouTube Link',
            uploadTab: 'Upload File',
            youtubePlaceholder: 'Paste YouTube video link here...',
            dropzoneTitle: 'Drag & Drop Video Here',
            dropzoneSubtitle: 'or click to browse files',
            dropzoneFormats: 'Max: 25MB • Supported: MP4, MKV, WebM, MOV, AVI',
            dubbing: 'Voice Dubbing',
            dubbingDesc: 'Convert speaker audio to Arabic with lip sync',
            subtitles: 'Subtitles Only',
            subtitlesDesc: 'Generate subtitle files and display on video',
            both: 'Complete (Dub + Subs)',
            bothDesc: 'Best experience: Arabic audio with translated text',
            startBtn: 'Start Processing',
            processing: 'Processing...',
            fileSelected: 'Selected:',
            removeFile: 'Remove',
            offlineWarning: 'Server is currently offline',
        },
    }[lang];

    const handleFileSelect = useCallback((file: File) => {
        const validTypes = ['video/mp4', 'video/webm', 'video/quicktime', 'video/x-matroska'];
        const maxSize = 25 * 1024 * 1024;

        if (!validTypes.includes(file.type) && !file.name.match(/\.(mp4|mkv|webm|mov)$/i)) {
            alert(lang === 'ar' ? 'نوع الملف غير مدعوم' : 'File type not supported');
            return;
        }

        if (file.size > maxSize) {
            alert(lang === 'ar' ? 'حجم الملف كبير جداً (الحد 25MB)' : 'File too large (max 25MB)');
            return;
        }

        setSelectedFile(file);
    }, [lang]);

    const handleDrop = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(false);
        const file = e.dataTransfer.files[0];
        if (file) handleFileSelect(file);
    }, [handleFileSelect]);

    const handleDragOver = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(true);
    }, []);

    const handleDragLeave = useCallback(() => {
        setIsDragging(false);
    }, []);

    const handleStart = () => {
        if (inputMode === 'youtube') {
            if (!youtubeUrl.trim()) return;
            onStartYouTube(youtubeUrl.trim(), selectedService);
        } else {
            if (!selectedFile) return;
            onStartUpload(selectedFile, selectedService);
        }
    };

    const canStart = inputMode === 'youtube' ? youtubeUrl.trim().length > 0 : selectedFile !== null;

    const services: { id: ServiceMode; icon: React.ReactNode; title: string; desc: string }[] = [
        { id: 'DUBBING', icon: <Mic className="w-5 h-5" />, title: t.dubbing, desc: t.dubbingDesc },
        { id: 'SUBTITLES', icon: <FileText className="w-5 h-5" />, title: t.subtitles, desc: t.subtitlesDesc },
        { id: 'BOTH', icon: <Layers className="w-5 h-5" />, title: t.both, desc: t.bothDesc },
    ];

    return (
        <div className="w-full max-w-3xl mx-auto px-4 py-8">

            {/* Hero Header */}
            <div className="text-center mb-10">
                {/* Badge */}
                <div className="inline-flex items-center px-4 py-2 rounded-full bg-gradient-to-r from-indigo-100 to-purple-100 dark:from-indigo-900/30 dark:to-purple-900/30 text-indigo-700 dark:text-indigo-300 text-sm font-bold mb-6 border border-indigo-200/50 dark:border-indigo-700/50">
                    <Sparkles className="w-4 h-4 ltr:mr-2 rtl:ml-2" />
                    {t.badge}
                </div>

                {/* Headlines */}
                <h1 className="text-4xl md:text-6xl font-black text-slate-900 dark:text-white mb-3 leading-tight">
                    {t.headline1}
                </h1>
                <h1 className="text-4xl md:text-6xl font-black mb-6 leading-tight">
                    <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-600 via-purple-600 to-indigo-600">
                        {t.headline2}
                    </span>
                </h1>

                {/* Subheadline */}
                <p className="text-lg text-slate-600 dark:text-slate-400 max-w-2xl mx-auto leading-relaxed">
                    {t.subheadline}
                </p>
            </div>

            {/* Backend Offline Warning */}
            {backendOnline === false && (
                <div className="mb-6 p-4 bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/30 rounded-xl flex items-center justify-center gap-2 text-amber-700 dark:text-amber-400">
                    <AlertCircle className="w-5 h-5 shrink-0" />
                    <span className="text-sm font-medium">{t.offlineWarning}</span>
                </div>
            )}

            {/* Main Card */}
            <div className="bg-white dark:bg-slate-800/80 rounded-3xl shadow-xl shadow-slate-200/50 dark:shadow-slate-900/50 border border-slate-200/80 dark:border-slate-700/80 overflow-hidden backdrop-blur-sm">

                {/* Tabs - Pill Style */}
                <div className="flex justify-center pt-6 pb-4">
                    <div className="inline-flex bg-slate-100 dark:bg-slate-700/50 rounded-full p-1.5">
                        <button
                            onClick={() => setInputMode('youtube')}
                            className={`flex items-center gap-2 px-5 py-2.5 rounded-full text-sm font-bold transition-all duration-300 ${inputMode === 'youtube'
                                    ? 'bg-white dark:bg-slate-600 text-slate-900 dark:text-white shadow-md'
                                    : 'text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-300'
                                }`}
                        >
                            <Youtube className="w-4 h-4" />
                            {t.youtubeTab}
                        </button>
                        <button
                            onClick={() => setInputMode('file')}
                            className={`flex items-center gap-2 px-5 py-2.5 rounded-full text-sm font-bold transition-all duration-300 ${inputMode === 'file'
                                    ? 'bg-white dark:bg-slate-600 text-slate-900 dark:text-white shadow-md'
                                    : 'text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-300'
                                }`}
                        >
                            <Upload className="w-4 h-4" />
                            {t.uploadTab}
                        </button>
                    </div>
                </div>

                {/* Input Area */}
                <div className="px-6 pb-6">
                    {inputMode === 'youtube' ? (
                        /* YouTube URL Input */
                        <div className="relative">
                            <div className="flex items-center bg-slate-50 dark:bg-slate-700/50 border border-slate-200 dark:border-slate-600 rounded-2xl overflow-hidden focus-within:ring-2 focus-within:ring-indigo-500 focus-within:border-transparent transition-all">
                                <input
                                    type="text"
                                    value={youtubeUrl}
                                    onChange={(e) => setYoutubeUrl(e.target.value)}
                                    placeholder={t.youtubePlaceholder}
                                    className="flex-1 px-5 py-4 bg-transparent border-none text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none text-base"
                                    dir="ltr"
                                />
                                <div className="px-4 text-slate-400">
                                    <Youtube className="w-6 h-6" />
                                </div>
                            </div>
                        </div>
                    ) : (
                        /* File Upload Dropzone */
                        <div
                            onDrop={handleDrop}
                            onDragOver={handleDragOver}
                            onDragLeave={handleDragLeave}
                            onClick={() => fileInputRef.current?.click()}
                            className={`relative border-2 border-dashed rounded-2xl p-10 text-center cursor-pointer transition-all duration-300 ${isDragging
                                    ? 'border-indigo-500 bg-gradient-to-br from-indigo-50 to-purple-50 dark:from-indigo-900/20 dark:to-purple-900/20'
                                    : selectedFile
                                        ? 'border-green-400 bg-gradient-to-br from-green-50 to-emerald-50 dark:from-green-900/20 dark:to-emerald-900/20'
                                        : 'border-slate-300 dark:border-slate-600 bg-gradient-to-br from-slate-50 to-slate-100/50 dark:from-slate-800/50 dark:to-slate-700/30 hover:border-indigo-400 hover:from-indigo-50/50 hover:to-purple-50/50'
                                }`}
                        >
                            <input
                                ref={fileInputRef}
                                type="file"
                                accept="video/mp4,video/webm,video/quicktime,.mp4,.mkv,.webm,.mov"
                                onChange={(e) => e.target.files?.[0] && handleFileSelect(e.target.files[0])}
                                className="hidden"
                            />

                            {selectedFile ? (
                                <div className="space-y-4">
                                    <div className="inline-flex items-center justify-center w-16 h-16 bg-green-100 dark:bg-green-500/20 rounded-full">
                                        <CheckCircle2 className="w-8 h-8 text-green-600 dark:text-green-400" />
                                    </div>
                                    <div>
                                        <p className="text-sm text-slate-500 dark:text-slate-400">{t.fileSelected}</p>
                                        <p className="font-bold text-slate-900 dark:text-white text-lg truncate max-w-sm mx-auto">{selectedFile.name}</p>
                                        <p className="text-sm text-slate-500 mt-1">{(selectedFile.size / 1024 / 1024).toFixed(1)} MB</p>
                                    </div>
                                    <button
                                        onClick={(e) => { e.stopPropagation(); setSelectedFile(null); }}
                                        className="inline-flex items-center gap-1.5 px-4 py-2 text-sm text-red-600 hover:bg-red-50 dark:hover:bg-red-500/10 rounded-xl transition-colors font-medium"
                                    >
                                        <X className="w-4 h-4" />
                                        {t.removeFile}
                                    </button>
                                </div>
                            ) : (
                                <div className="space-y-4">
                                    <div className="inline-flex items-center justify-center w-16 h-16 bg-indigo-100 dark:bg-indigo-500/20 rounded-full">
                                        <Upload className="w-8 h-8 text-indigo-500 dark:text-indigo-400" />
                                    </div>
                                    <div>
                                        <p className="font-bold text-slate-800 dark:text-slate-200 text-lg">{t.dropzoneTitle}</p>
                                        <p className="text-slate-500 dark:text-slate-400 mt-1">{t.dropzoneSubtitle}</p>
                                    </div>
                                    <p className="text-xs text-slate-400 dark:text-slate-500">{t.dropzoneFormats}</p>
                                </div>
                            )}
                        </div>
                    )}
                </div>

                {/* Service Selection - 3 Cards */}
                <div className="px-6 pb-6">
                    <div className="grid grid-cols-3 gap-3">
                        {services.map((service) => (
                            <button
                                key={service.id}
                                onClick={() => setSelectedService(service.id)}
                                className={`relative p-5 rounded-2xl border-2 transition-all duration-300 text-center group ${selectedService === service.id
                                        ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-500/10 shadow-lg shadow-indigo-500/10'
                                        : 'border-slate-200 dark:border-slate-600/50 bg-white dark:bg-slate-700/30 hover:border-indigo-300 dark:hover:border-indigo-500/50 hover:shadow-md'
                                    }`}
                            >
                                {/* Icon */}
                                <div className={`inline-flex items-center justify-center w-12 h-12 rounded-xl mb-3 transition-all ${selectedService === service.id
                                        ? 'bg-indigo-500 text-white shadow-lg shadow-indigo-500/30'
                                        : 'bg-slate-100 dark:bg-slate-600/50 text-slate-500 dark:text-slate-400 group-hover:bg-indigo-100 dark:group-hover:bg-indigo-900/30 group-hover:text-indigo-600'
                                    }`}>
                                    {service.icon}
                                </div>

                                {/* Title */}
                                <h3 className={`font-bold text-sm mb-1.5 transition-colors ${selectedService === service.id
                                        ? 'text-indigo-700 dark:text-indigo-300'
                                        : 'text-slate-800 dark:text-slate-200'
                                    }`}>
                                    {service.title}
                                </h3>

                                {/* Description */}
                                <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
                                    {service.desc}
                                </p>
                            </button>
                        ))}
                    </div>
                </div>

                {/* Action Button */}
                <div className="px-6 pb-6">
                    <button
                        onClick={handleStart}
                        disabled={!canStart || isLoading}
                        className={`w-full py-4 px-6 rounded-2xl font-bold text-lg transition-all duration-300 flex items-center justify-center gap-3 ${canStart && !isLoading
                                ? 'bg-gradient-to-r from-indigo-600 via-purple-600 to-indigo-600 hover:from-indigo-700 hover:via-purple-700 hover:to-indigo-700 text-white shadow-xl shadow-indigo-500/25 hover:shadow-2xl hover:shadow-indigo-500/30 hover:-translate-y-0.5'
                                : 'bg-slate-200 dark:bg-slate-700 text-slate-400 dark:text-slate-500 cursor-not-allowed'
                            }`}
                    >
                        {isLoading ? (
                            <>
                                <Loader2 className="w-5 h-5 animate-spin" />
                                {t.processing}
                            </>
                        ) : (
                            t.startBtn
                        )}
                    </button>
                </div>

                {/* Error Message */}
                {error && (
                    <div className="px-6 pb-6">
                        <div className="p-4 bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/30 rounded-xl flex items-center justify-center gap-2 text-red-600 dark:text-red-400">
                            <AlertCircle className="w-5 h-5 shrink-0" />
                            <span className="text-sm font-medium">{error}</span>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};
