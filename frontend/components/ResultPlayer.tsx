import React, { useRef, useEffect } from 'react';
import { Download, RefreshCw, Play, Pause, Volume2, Maximize } from 'lucide-react';
import { Button } from './Button';
import { VideoMetadata } from '../types';

interface ResultPlayerProps {
  metadata: VideoMetadata | null;
  onReset: () => void;
  t: any;
}

export function ResultPlayer({ metadata, onReset, t }: ResultPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);

  if (!metadata) return null;

  // Helper to check if it's a direct file (MP4) or YouTube
  const isDirectFile = (url: string) => {
    return url.includes('supabase.co') || url.endsWith('.mp4') || url.startsWith('blob:');
  };

  const isYouTube = (url: string) => {
    return url.includes('youtube.com') || url.includes('youtu.be');
  };

  // Extract YouTube ID if needed
  const getYouTubeId = (url: string) => {
    const regExp = /^.*(youtu.be\/|v\/|u\/\w\/|embed\/|watch\?v=|&v=)([^#&?]*).*/;
    const match = url.match(regExp);
    return (match && match[2].length === 11) ? match[2] : null;
  };

  useEffect(() => {
    // Force reload video source when URL changes
    if (videoRef.current && isDirectFile(metadata.url)) {
      videoRef.current.load();
    }
  }, [metadata.url]);

  const handleDownload = async (type: 'video' | 'audio') => {
    if (!metadata.url) return;
    
    try {
      // Create a temporary anchor tag to force download
      const link = document.createElement('a');
      link.href = metadata.url;
      link.download = `dubbed_video_${Date.now()}.mp4`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } catch (e) {
      console.error("Download failed", e);
      window.open(metadata.url, '_blank');
    }
  };

  return (
    <div className="w-full max-w-4xl mx-auto animate-in fade-in slide-in-from-bottom-8 duration-700">
      
      {/* Header Section */}
      <div className="text-center mb-8">
        <div className="inline-flex items-center justify-center p-3 bg-green-100 dark:bg-green-500/10 rounded-full mb-4">
          <Play className="w-8 h-8 text-green-600 dark:text-green-500 fill-current" />
        </div>
        <h2 className="text-3xl font-bold text-slate-900 dark:text-white mb-2">
          {t.successTitle || "تمت العملية بنجاح!"}
        </h2>
        <p className="text-slate-600 dark:text-slate-400">
          {t.successSubtitle || "الفيديو الخاص بك جاهز للمشاهدة والتحميل."}
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* --- VIDEO PLAYER SECTION --- */}
        <div className="lg:col-span-2 space-y-4">
          <div className="relative aspect-video bg-black rounded-2xl overflow-hidden shadow-2xl border border-slate-200 dark:border-slate-800 ring-1 ring-slate-900/5 group">
            
            {/* LOGIC: Show HTML5 Video for Supabase/MP4, Iframe for YouTube */}
            {isDirectFile(metadata.url) ? (
              <video
                ref={videoRef}
                className="w-full h-full object-contain"
                controls
                autoPlay
                playsInline
                poster={metadata.thumbnail}
              >
                <source src={metadata.url} type="video/mp4" />
                Your browser does not support the video tag.
              </video>
            ) : isYouTube(metadata.url) ? (
              <iframe
                className="w-full h-full"
                src={`https://www.youtube.com/embed/${getYouTubeId(metadata.url)}?autoplay=1`}
                title="YouTube video player"
                frameBorder="0"
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                allowFullScreen
              ></iframe>
            ) : (
              // Fallback for uploaded local files before processing
              <div className="w-full h-full flex items-center justify-center text-white">
                <p>Preview not available</p>
              </div>
            )}

            {/* Title Overlay */}
            <div className="absolute top-4 left-4 right-4 flex justify-between items-start z-10 pointer-events-none">
               <span className="px-3 py-1 bg-black/60 backdrop-blur-md text-white text-xs font-medium rounded-lg border border-white/10">
                 {metadata.mode || "DUBBING"}
               </span>
            </div>
          </div>
          
          <div className="bg-white dark:bg-slate-800 rounded-xl p-4 border border-slate-200 dark:border-slate-700 flex items-center justify-between">
             <div className="font-medium truncate pr-4 text-slate-900 dark:text-white" dir="auto">
               {metadata.title}
             </div>
             <div className="text-xs font-mono text-slate-500 bg-slate-100 dark:bg-slate-900 px-2 py-1 rounded">
               MP4
             </div>
          </div>
        </div>

        {/* --- ACTIONS SECTION --- */}
        <div className="space-y-6">
          <div className="bg-white dark:bg-slate-800 rounded-2xl p-6 border border-slate-200 dark:border-slate-700 shadow-sm h-full flex flex-col justify-center">
            <h3 className="font-bold text-slate-900 dark:text-white mb-6 flex items-center gap-2">
              <Download className="w-5 h-5 text-indigo-500" />
              {t.downloadOptions || "خيارات التحميل"}
            </h3>
            
            <div className="space-y-3">
              <button 
                onClick={() => handleDownload('video')}
                className="w-full flex items-center justify-between p-4 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl transition-all shadow-lg shadow-indigo-500/20 group"
              >
                <span className="font-bold">{t.downloadVideo || "تحميل الفيديو (MP4)"}</span>
                <span className="bg-white/20 px-2 py-0.5 rounded text-xs">HD</span>
              </button>
              
              <button 
                onClick={() => window.open(metadata.url, '_blank')}
                className="w-full flex items-center justify-between p-4 bg-slate-100 dark:bg-slate-700 hover:bg-slate-200 dark:hover:bg-slate-600 text-slate-900 dark:text-white rounded-xl transition-colors border border-slate-200 dark:border-slate-600"
              >
                <span className="font-medium">{t.downloadAudio || "فتح في نافذة جديدة"}</span>
                <Volume2 className="w-4 h-4 opacity-50" />
              </button>
            </div>

            <div className="my-6 border-t border-slate-100 dark:border-slate-700"></div>

            <Button 
              variant="outline" 
              onClick={onReset}
              className="w-full py-6 border-dashed border-2 hover:bg-slate-50 dark:hover:bg-slate-800/50"
            >
              <RefreshCw className="w-4 h-4 mx-2" />
              {t.processNewVideo || "معالجة فيديو آخر"}
            </Button>
          </div>
        </div>

      </div>
    </div>
  );
}