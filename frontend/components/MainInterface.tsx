
import React, { useState, useRef, useCallback } from 'react';
import { Link2, Upload, Mic, FileText, Layers, Sparkles, Loader2, AlertCircle, X, CheckCircle2 } from 'lucide-react';
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
    const [inputMode, setInputMode] = useState<InputMode>('file'); // Default to file upload
    const [selectedService, setSelectedService] = useState<ServiceMode>('DUBBING');
    const [youtubeUrl, setYoutubeUrl] = useState('');
    const [selectedFile, setSelectedFile] = useState<File | null>(null);
    const [isDragging, setIsDragging] = useState(false);
    const fileInputRef = useRef<HTMLInputElement>(null);

    const t = {
        ar: {
            headline: 'دبلج وترجم فيديوهاتك',
            headlineHighlight: 'بذكاء اصطناعي',
            subheadline: 'حول أي فيديو إلى العربية. اختر الدبلجة الصوتية، الترجمة النصية، أو كليهما معاً.',
            youtubeTab: '🔗 رابط يوتيوب',
            uploadTab: '📂 رفع ملف',
            youtubePlaceholder: 'ضع رابط فيديو يوتيوب هنا...',
            dropzoneTitle: 'اسحب الملف هنا',
            dropzoneSubtitle: 'أو اضغط لاختيار ملف',
            dropzoneFormats: 'MP4, MKV, WebM, MOV • الحد الأقصى: 25MB',
            serviceTitle: 'اختر نوع الخدمة',
            dubbing: 'دبلجة صوتية',
            dubbingDesc: 'تحويل الصوت للعربية',
            subtitles: 'ترجمة نصية',
            subtitlesDesc: 'إنشاء ملف SRT',
            both: 'شامل',
            bothDesc: 'دبلجة + ترجمة',
            startBtn: 'ابدأ المعالجة',
            processing: 'جاري المعالجة...',
            fileSelected: 'تم اختيار:',
            removeFile: 'إزالة',
            offlineWarning: 'الخادم غير متصل حالياً',
            youtubeWarning: '⚠️ روابط يوتيوب قد لا تعمل بسبب قيود الخادم. استخدم رفع الملف للنتائج الأفضل.',
        },
        en: {
            headline: 'Dub & Translate Your Videos',
            headlineHighlight: 'with AI',
            subheadline: 'Convert any video to Arabic. Choose voice dubbing, subtitles, or both.',
            youtubeTab: '🔗 YouTube Link',
            uploadTab: '📂 Upload File',
            youtubePlaceholder: 'Paste YouTube video link here...',
            dropzoneTitle: 'Drop file here',
            dropzoneSubtitle: 'or click to browse',
            dropzoneFormats: 'MP4, MKV, WebM, MOV • Max: 25MB',
            serviceTitle: 'Select Service Type',
            dubbing: 'Voice Dubbing',
            dubbingDesc: 'Convert audio to Arabic',
            subtitles: 'Subtitles Only',
            subtitlesDesc: 'Generate SRT file',
            both: 'Complete',
            bothDesc: 'Dubbing + Subtitles',
            startBtn: 'Start Processing',
            processing: 'Processing...',
            fileSelected: 'Selected:',
            removeFile: 'Remove',
            offlineWarning: 'Server is currently offline',
            youtubeWarning: '⚠️ YouTube links may not work due to server restrictions. Use file upload for best results.',
        },
    }[lang];

    const handleFileSelect = useCallback((file: File) => {
        const validTypes = ['video/mp4', 'video/webm', 'video/quicktime', 'video/x-matroska'];
        const maxSize = 25 * 1024 * 1024; // 25MB

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
        { id: 'DUBBING', icon: <Mic className="w-6 h-6" />, title: t.dubbing, desc: t.dubbingDesc },
        { id: 'SUBTITLES', icon: <FileText className="w-6 h-6" />, title: t.subtitles, desc: t.subtitlesDesc },
        { id: 'BOTH', icon: <Layers className="w-6 h-6" />, title: t.both, desc: t.bothDesc },
    ];

    return (
        <div className="w-full max-w-2xl mx-auto px-4">
            {/* Hero Header */}
            <div className="text-center mb-8">
                <div className="inline-flex items-center px-4 py-1.5 rounded-full bg-indigo-100 dark:bg-indigo-500/20 text-indigo-700 dark:text-indigo-300 text-sm font-bold mb-4">
                    <Sparkles className="w-4 h-4 ltr:mr-2 rtl:ml-2" />
                    {lang === 'ar' ? '100% مجاني' : '100% Free'}
                </div>
                <h1 className="text-4xl md:text-5xl font-black text-slate-900 dark:text-white mb-4 leading-tight">
                    {t.headline}{' '}
                    <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-600 via-purple-600 to-pink-600">
                        {t.headlineHighlight}
                    </span>
                </h1>
                <p className="text-lg text-slate-600 dark:text-slate-400 max-w-lg mx-auto">
                    {t.subheadline}
                </p>
            </div>

            {/* Backend Offline Warning */}
            {backendOnline === false && (
                <div className="mb-4 p-3 bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/30 rounded-xl flex items-center gap-2 text-amber-700 dark:text-amber-400">
                    <AlertCircle className="w-5 h-5 shrink-0" />
                    <span className="text-sm font-medium">{t.offlineWarning}</span>
                </div>
            )}

            {/* Main Card */}
            <div className="bg-white dark:bg-slate-800 rounded-3xl shadow-2xl shadow-slate-200/50 dark:shadow-slate-900/50 border border-slate-200 dark:border-slate-700 overflow-hidden">

                {/* Input Mode Tabs */}
                <div className="flex border-b border-slate-200 dark:border-slate-700">
                    <button
                        onClick={() => setInputMode('youtube')}
                        className={`flex-1 py-4 px-4 text-center font-bold transition-all flex items-center justify-center gap-2 ${inputMode === 'youtube'
                                ? 'bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border-b-2 border-indigo-500'
                                : 'text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700/50'
                            }`}
                    >
                        <Link2 className="w-5 h-5" />
                        {t.youtubeTab}
                    </button>
                    <button
                        onClick={() => setInputMode('file')}
                        className={`flex-1 py-4 px-4 text-center font-bold transition-all flex items-center justify-center gap-2 ${inputMode === 'file'
                                ? 'bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border-b-2 border-indigo-500'
                                : 'text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700/50'
                            }`}
                    >
                        <Upload className="w-5 h-5" />
                        {t.uploadTab}
                    </button>
                </div>

                {/* Input Area */}
                <div className="p-6">
                    {inputMode === 'youtube' ? (
                        <div className="space-y-3">
                            {/* YouTube Warning */}
                            <div className="p-3 bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/30 rounded-xl text-amber-700 dark:text-amber-400 text-sm">
                                {t.youtubeWarning}
                            </div>
                            <div className="relative">
                                <input
                                    type="text"
                                    value={youtubeUrl}
                                    onChange={(e) => setYoutubeUrl(e.target.value)}
                                    placeholder={t.youtubePlaceholder}
                                    className="w-full px-5 py-4 bg-slate-50 dark:bg-slate-700 border border-slate-200 dark:border-slate-600 rounded-xl text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent text-lg"
                                    dir="ltr"
                                />
                            </div>
                        </div>
                    ) : (
                        <div
                            onDrop={handleDrop}
                            onDragOver={handleDragOver}
                            onDragLeave={handleDragLeave}
                            onClick={() => fileInputRef.current?.click()}
                            className={`relative border-2 border-dashed rounded-2xl p-8 text-center cursor-pointer transition-all ${isDragging
                                    ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-500/10'
                                    : selectedFile
                                        ? 'border-green-400 bg-green-50 dark:bg-green-500/10'
                                        : 'border-slate-300 dark:border-slate-600 hover:border-indigo-400 hover:bg-slate-50 dark:hover:bg-slate-700/50'
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
                                <div className="space-y-3">
                                    <div className="inline-flex items-center justify-center w-14 h-14 bg-green-100 dark:bg-green-500/20 rounded-full">
                                        <CheckCircle2 className="w-7 h-7 text-green-600 dark:text-green-400" />
                                    </div>
                                    <div>
                                        <p className="text-sm text-slate-500 dark:text-slate-400">{t.fileSelected}</p>
                                        <p className="font-bold text-slate-900 dark:text-white truncate max-w-xs mx-auto">{selectedFile.name}</p>
                                        <p className="text-sm text-slate-500">{(selectedFile.size / 1024 / 1024).toFixed(1)} MB</p>
                                    </div>
                                    <button
                                        onClick={(e) => { e.stopPropagation(); setSelectedFile(null); }}
                                        className="inline-flex items-center gap-1 px-3 py-1.5 text-sm text-red-600 hover:bg-red-50 dark:hover:bg-red-500/10 rounded-lg transition-colors"
                                    >
                                        <X className="w-4 h-4" />
                                        {t.removeFile}
                                    </button>
                                </div>
                            ) : (
                                <div className="space-y-3">
                                    <div className="inline-flex items-center justify-center w-14 h-14 bg-slate-100 dark:bg-slate-700 rounded-full">
                                        <Upload className="w-7 h-7 text-slate-400" />
                                    </div>
                                    <div>
                                        <p className="font-bold text-slate-700 dark:text-slate-200">{t.dropzoneTitle}</p>
                                        <p className="text-sm text-slate-500 dark:text-slate-400">{t.dropzoneSubtitle}</p>
                                    </div>
                                    <p className="text-xs text-slate-400">{t.dropzoneFormats}</p>
                                </div>
                            )}
                        </div>
                    )}
                </div>

                {/* Service Selection */}
                <div className="px-6 pb-2">
                    <p className="text-sm font-medium text-slate-500 dark:text-slate-400 mb-3 text-center">{t.serviceTitle}</p>
                    <div className="grid grid-cols-3 gap-3">
                        {services.map((service) => (
                            <button
                                key={service.id}
                                onClick={() => setSelectedService(service.id)}
                                className={`p-4 rounded-xl border-2 transition-all text-center ${selectedService === service.id
                                        ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-500/10 ring-2 ring-indigo-500/20'
                                        : 'border-slate-200 dark:border-slate-600 hover:border-indigo-300 dark:hover:border-indigo-500/50'
                                    }`}
                            >
                                <div className={`inline-flex p-2 rounded-lg mb-2 ${selectedService === service.id
                                        ? 'bg-indigo-500 text-white'
                                        : 'bg-slate-100 dark:bg-slate-700 text-slate-500 dark:text-slate-400'
                                    }`}>
                                    {service.icon}
                                </div>
                                <div className="font-bold text-slate-900 dark:text-white text-sm">{service.title}</div>
                                <div className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">{service.desc}</div>
                            </button>
                        ))}
                    </div>
                </div>

                {/* Action Button */}
                <div className="p-6 pt-4">
                    <button
                        onClick={handleStart}
                        disabled={!canStart || isLoading}
                        className={`w-full py-4 px-6 rounded-xl font-bold text-lg transition-all flex items-center justify-center gap-3 ${canStart && !isLoading
                                ? 'bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white shadow-lg shadow-indigo-500/30 hover:shadow-xl hover:shadow-indigo-500/40'
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
                        <div className="p-3 bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/30 rounded-xl flex items-center gap-2 text-red-600 dark:text-red-400">
                            <AlertCircle className="w-5 h-5 shrink-0" />
                            <span className="text-sm">{error}</span>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};
