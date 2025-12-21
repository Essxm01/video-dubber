import React, { useState, useEffect, useRef } from 'react';
import {
    Play, Pause, Loader2, RefreshCw, Volume2, VolumeX,
    Maximize, SkipForward, List, CheckCircle, AlertCircle, Clock, Lock
} from 'lucide-react';
import { getJobDetails, VideoSegment } from '../services/apiService';

interface SmartVideoPlayerProps {
    jobId: string;
    poster?: string;
    onAllFinished?: () => void;
}

export const SmartVideoPlayer: React.FC<SmartVideoPlayerProps> = ({ jobId, poster, onAllFinished }) => {
    // --- State ---
    const [segments, setSegments] = useState<VideoSegment[]>([]);
    const [currentIndex, setCurrentIndex] = useState(0);
    const [isPlaying, setIsPlaying] = useState(false);
    const [isMuted, setIsMuted] = useState(false);
    const [autoAdvance, setAutoAdvance] = useState(true);
    const [nextOverlayVisible, setNextOverlayVisible] = useState(false);

    // Refs
    const videoRef = useRef<HTMLVideoElement>(null);
    const containerRef = useRef<HTMLDivElement>(null);
    const pollInterval = useRef<ReturnType<typeof setTimeout> | null>(null);

    // --- Data Fetching ---
    const fetchSegments = async () => {
        try {
            const data = await getJobDetails(jobId);
            if (data && data.segments) {
                const sorted = data.segments.sort((a, b) => a.segment_index - b.segment_index);
                setSegments(prev => {
                    // Simple check to avoid unnecessary re-renders if length/status hasn't changed could go here
                    // For now, React's diffing is sufficient
                    return sorted;
                });
            }
        } catch (err) {
            console.error("Failed to fetch segments", err);
        }
    };

    useEffect(() => {
        fetchSegments();
        pollInterval.current = setInterval(fetchSegments, 3000);
        return () => {
            if (pollInterval.current) clearInterval(pollInterval.current);
        };
    }, [jobId]);

    // --- Logic ---
    const currentSegment = segments.find(s => s.segment_index === currentIndex);
    const nextSegment = segments.find(s => s.segment_index === currentIndex + 1);

    // Determine active statuses
    const isReady = currentSegment?.status === 'ready';
    const isProcessing = currentSegment?.status === 'processing' || currentSegment?.status === 'pending';
    const isFailed = currentSegment?.status === 'failed';

    // Auto-Play Logic
    useEffect(() => {
        // If playing state is active, valid video ref, and segment becomes ready
        if (isPlaying && isReady && videoRef.current && videoRef.current.paused) {
            videoRef.current.play().catch(e => console.log("Auto-play blocked", e));
        }
    }, [isReady, isPlaying, currentIndex]);

    // Handle Ended -> Netflix Style Advance
    const handleEnded = () => {
        if (!autoAdvance) {
            setIsPlaying(false);
            return;
        }

        if (nextSegment) {
            if (nextSegment.status === 'ready') {
                // Next is ready: Play immediately
                setNextOverlayVisible(false); // Hide overlay if it was shown
                setCurrentIndex(currentIndex + 1);
                setIsPlaying(true);
            } else {
                // Next is NOT ready: Show "Wait" Overlay logic
                setNextOverlayVisible(true);
                // We keep 'isPlaying' true so the Intent is to play.
                // The useEffect above or a watcher on nextSegment.status will trigger actual play when ready.
            }
        } else {
            // Finished all
            setIsPlaying(false);
            onAllFinished?.();
        }
    };

    // Watch next segment status if we are waiting for it
    useEffect(() => {
        if (nextOverlayVisible && nextSegment?.status === 'ready') {
            setNextOverlayVisible(false);
            setCurrentIndex(currentIndex + 1);
            setIsPlaying(true);
        }
    }, [nextSegment?.status, nextOverlayVisible]);

    // --- Handlers ---
    const togglePlay = () => {
        if (!videoRef.current || !isReady) return;
        if (isPlaying) {
            videoRef.current.pause();
            setIsPlaying(false);
        } else {
            videoRef.current.play().catch(e => console.error("Play failed:", e));
            setIsPlaying(true);
        }
    };

    const toggleMute = () => {
        if (videoRef.current) {
            videoRef.current.muted = !isMuted;
            setIsMuted(!isMuted);
        }
    };

    const toggleFullscreen = () => {
        if (!containerRef.current) return;
        if (document.fullscreenElement) {
            document.exitFullscreen();
        } else {
            containerRef.current.requestFullscreen();
        }
    };

    const selectSegment = (index: number) => {
        const seg = segments.find(s => s.segment_index === index);
        if (seg?.status === 'ready') {
            setCurrentIndex(index);
            setIsPlaying(true);
            setNextOverlayVisible(false);
        }
    };

    // --- Render ---
    return (
        <div ref={containerRef} className="flex flex-col lg:flex-row-reverse w-full max-w-7xl mx-auto h-[650px] bg-white rounded-3xl shadow-2xl overflow-hidden border border-gray-100">

            {/* --- RIGHT SIDEBAR (PLAYLIST) --- */}
            <div className="w-full lg:w-1/4 min-w-[320px] bg-gray-50 flex flex-col border-r border-gray-200" dir="rtl">
                {/* Header */}
                <div className="p-6 border-b border-gray-200 bg-white">
                    <div className="flex justify-between items-center mb-1">
                        <h2 className="text-xl font-bold text-gray-800">قائمة الأجزاء</h2>
                        <span className="bg-indigo-100 text-indigo-700 text-xs px-2 py-1 rounded-full font-bold">
                            {segments.length} مقاطع
                        </span>
                    </div>
                    <p className="text-gray-500 text-xs">يتم التشغيل تلقائياً</p>
                </div>

                {/* List */}
                <div className="flex-1 overflow-y-auto p-4 space-y-3 custom-scrollbar">
                    {segments.map((seg, idx) => {
                        const active = idx === currentIndex;
                        const ready = seg.status === 'ready';
                        const processing = seg.status === 'processing' || seg.status === 'pending';
                        const failed = seg.status === 'failed';

                        // Calculate status color/style
                        let cardStyle = "border-gray-200 bg-white hover:border-gray-300";
                        if (active) cardStyle = "border-indigo-500 bg-white shadow-lg ring-1 ring-indigo-500 transform scale-[1.02] z-10";
                        else if (ready) cardStyle = "border-green-200 bg-green-50/50";
                        else if (processing) cardStyle = "border-blue-200 bg-blue-50/50";
                        else if (failed) cardStyle = "border-red-200 bg-red-50";

                        return (
                            <button
                                key={seg.segment_index}
                                onClick={() => selectSegment(idx)}
                                disabled={!ready}
                                className={`
                                    relative w-full text-right p-4 rounded-xl border transition-all duration-200 flex flex-col gap-2 group
                                    ${cardStyle}
                                    ${!ready && !active ? 'opacity-70 grayscale-[0.3]' : ''}
                                `}
                            >
                                <div className="flex justify-between items-start w-full">
                                    <div className="flex items-center gap-3">
                                        <div className={`
                                            w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold
                                            ${active ? 'bg-indigo-600 text-white' : 'bg-gray-200 text-gray-500'}
                                        `}>
                                            {idx + 1}
                                        </div>
                                        <div>
                                            <h4 className={`font-bold text-sm ${active ? 'text-indigo-900' : 'text-gray-700'}`}>
                                                المقطع {idx + 1}
                                            </h4>
                                            <span className="text-xs text-gray-500 font-mono">05:00</span>
                                        </div>
                                    </div>

                                    {/* Status Icon */}
                                    <div className="mt-1">
                                        {ready && <CheckCircle className="w-5 h-5 text-green-500" />}
                                        {processing && <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />}
                                        {failed && <RefreshCw className="w-5 h-5 text-red-500" />}
                                        {!ready && !processing && !failed && <Lock className="w-4 h-4 text-gray-300" />}
                                    </div>
                                </div>

                                {/* Status Text / Progress */}
                                <div className="w-full">
                                    {ready && (
                                        <div className="flex items-center gap-1 text-xs text-green-600 font-medium">
                                            <CheckCircle className="w-3 h-3" /> جاهز للعرض
                                        </div>
                                    )}
                                    {processing && (
                                        <div className="space-y-1">
                                            <span className="text-xs text-blue-600 font-medium flex items-center gap-1">
                                                <Loader2 className="w-3 h-3 animate-spin" /> جاري التحضير...
                                            </span>
                                            {/* Fake Progress Bar since backend doesn't give realtime pct yet */}
                                            <div className="w-full h-1 bg-blue-100 rounded-full overflow-hidden">
                                                <div className="h-full bg-blue-500 animate-progress origin-right w-[45%]"></div>
                                            </div>
                                        </div>
                                    )}
                                </div>
                            </button>
                        );
                    })}
                </div>
            </div>

            {/* --- LEFT MAIN VIDEO --- */}
            <div className="flex-1 bg-black relative group overflow-hidden">

                {/* 1. Video Player */}
                {isReady ? (
                    <video
                        ref={videoRef}
                        src={currentSegment?.media_url}
                        className="w-full h-full object-contain"
                        controls={false}
                        playsInline
                        crossOrigin="anonymous"
                        onEnded={handleEnded}
                        onPlay={() => setIsPlaying(true)}
                        onPause={() => setIsPlaying(false)}
                        poster={currentIndex === 0 ? poster : undefined}
                    />
                ) : (
                    // Placeholder when current segment is processing/loading
                    <div className="absolute inset-0 flex flex-col items-center justify-center bg-zinc-900 text-white gap-4">
                        {isProcessing ? (
                            <>
                                <Loader2 className="w-16 h-16 text-indigo-500 animate-spin" />
                                <h3 className="text-xl font-bold">جاري تجهيز المقطع {currentIndex + 1}...</h3>
                            </>
                        ) : (
                            <div className="text-center">
                                <h3 className="text-xl font-bold mb-2">في انتظار البدء...</h3>
                            </div>
                        )}
                    </div>
                )}

                {/* 2. "Coming Up Next" Overlay (Netflix Style) */}
                {nextOverlayVisible && (
                    <div className="absolute inset-0 bg-black/80 backdrop-blur-sm z-30 flex flex-col items-center justify-center text-white animate-in fade-in duration-300">
                        <div className="text-center space-y-4">
                            <Loader2 className="w-12 h-12 text-indigo-500 animate-spin mx-auto" />
                            <h3 className="text-2xl font-bold">المقطع التالي قيد المعالجة...</h3>
                            <p className="text-zinc-400">سيتم التشغيل تلقائياً بمجرد الانتهاء</p>
                        </div>
                    </div>
                )}

                {/* 3. Big Play Button (Overlay) */}
                {!isPlaying && isReady && !nextOverlayVisible && (
                    <div className="absolute inset-0 flex items-center justify-center bg-black/30 cursor-pointer z-20 group-hover:bg-black/40 transition-all" onClick={togglePlay}>
                        <div className="w-20 h-20 bg-white/20 backdrop-blur-md rounded-full flex items-center justify-center hover:scale-110 transition-transform">
                            <Play className="w-10 h-10 text-white fill-current ml-1" />
                        </div>
                    </div>
                )}

                {/* 4. Controls Bar */}
                <div className="absolute bottom-0 left-0 right-0 p-6 bg-gradient-to-t from-black/90 via-black/50 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300 flex items-center gap-6 z-30" dir="ltr">
                    <button onClick={togglePlay} className="text-white hover:text-indigo-400 transition-colors">
                        {isPlaying ? <Pause className="w-8 h-8 fill-current" /> : <Play className="w-8 h-8 fill-current" />}
                    </button>

                    <div className="flex-1 h-1 bg-white/20 rounded-full overflow-hidden">
                        {/* Seek bar logic would go here */}
                        <div className="h-full bg-indigo-500 w-0"></div>
                    </div>

                    <div className="flex items-center gap-4 text-white">
                        <button onClick={toggleMute} className="hover:text-indigo-400">
                            {isMuted ? <VolumeX className="w-6 h-6" /> : <Volume2 className="w-6 h-6" />}
                        </button>
                        <button onClick={toggleFullscreen} className="hover:text-indigo-400">
                            <Maximize className="w-6 h-6" />
                        </button>
                    </div>
                </div>
            </div>

        </div>
    );
};
