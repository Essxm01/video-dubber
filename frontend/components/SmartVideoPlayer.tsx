import React, { useState, useEffect, useRef } from 'react';
import {
    Play, Pause, Loader2, RefreshCw, Volume2, VolumeX,
    Maximize, SkipForward, List, CheckCircle, AlertCircle, Clock, Lock, Captions
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
    const [volume, setVolume] = useState(1);
    const [currentTime, setCurrentTime] = useState(0);
    const [duration, setDuration] = useState(0); // Real duration from metadata
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
                    // Force update if needed, but for now simple set is okay
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

    const isReady = currentSegment?.status === 'ready';
    const isProcessing = currentSegment?.status === 'processing' || currentSegment?.status === 'pending';
    const isFailed = currentSegment?.status === 'failed';

    // Auto-Play Logic
    useEffect(() => {
        if (isPlaying && isReady && videoRef.current && videoRef.current.paused) {
            videoRef.current.play().catch(e => console.log("Auto-play blocked", e));
        }
    }, [isReady, isPlaying, currentIndex]);

    // Volume Effect
    useEffect(() => {
        if (videoRef.current) {
            videoRef.current.volume = volume;
            videoRef.current.muted = isMuted;
        }
    }, [volume, isMuted]);

    // Handle Ended -> Netflix Style Advance
    const handleEnded = () => {
        if (!autoAdvance) {
            setIsPlaying(false);
            return;
        }

        if (nextSegment) {
            if (nextSegment.status === 'ready') {
                setNextOverlayVisible(false);
                setCurrentIndex(currentIndex + 1);
                setIsPlaying(true);
            } else {
                setNextOverlayVisible(true);
            }
        } else {
            setIsPlaying(false);
            onAllFinished?.();
        }
    };

    // Watch next segment status
    useEffect(() => {
        if (nextOverlayVisible && nextSegment?.status === 'ready') {
            setNextOverlayVisible(false);
            setCurrentIndex(currentIndex + 1);
            setIsPlaying(true);
        }
    }, [nextSegment?.status, nextOverlayVisible]);

    // --- Media Handlers ---
    const handleTimeUpdate = () => {
        if (videoRef.current) {
            setCurrentTime(videoRef.current.currentTime);
        }
    };

    const handleLoadedMetadata = () => {
        if (videoRef.current) {
            setDuration(videoRef.current.duration);
            // If we just switched segments and were playing, try to play again
            if (isPlaying) videoRef.current.play().catch(() => { });
        }
    };

    const togglePlay = () => {
        if (!videoRef.current || !isReady) return;
        if (videoRef.current.paused) {
            videoRef.current.play().catch(console.error);
            setIsPlaying(true);
        } else {
            videoRef.current.pause();
            setIsPlaying(false);
        }
    };

    const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
        const time = parseFloat(e.target.value);
        if (videoRef.current) {
            videoRef.current.currentTime = time;
            setCurrentTime(time);
        }
    };

    const formatTime = (time: number) => {
        if (isNaN(time)) return "00:00";
        const min = Math.floor(time / 60);
        const sec = Math.floor(time % 60);
        return `${min.toString().padStart(2, '0')}:${sec.toString().padStart(2, '0')}`;
    };

    const toggleFullscreen = () => {
        if (!containerRef.current) return;
        if (document.fullscreenElement) document.exitFullscreen();
        else containerRef.current.requestFullscreen();
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
        <div ref={containerRef} className="flex flex-col lg:flex-row-reverse w-full max-w-7xl mx-auto bg-white rounded-3xl shadow-2xl overflow-hidden border border-gray-100">
            {/* FIX 2: Removed fixed h-[650px], ensuring responsive height based on content */}

            {/* --- RIGHT SIDEBAR (PLAYLIST) --- */}
            <div className="w-full lg:w-1/4 min-w-[320px] bg-gray-50 flex flex-col border-r border-gray-200 max-h-[600px] lg:max-h-full" dir="rtl">
                <div className="p-6 border-b border-gray-200 bg-white">
                    <div className="flex justify-between items-center mb-1">
                        <h2 className="text-xl font-bold text-gray-800">قائمة الأجزاء</h2>
                        <span className="bg-indigo-100 text-indigo-700 text-xs px-2 py-1 rounded-full font-bold">
                            {segments.length} مقاطع
                        </span>
                    </div>
                </div>

                <div className="flex-1 overflow-y-auto p-4 space-y-3 custom-scrollbar">
                    {segments.map((seg, idx) => {
                        const active = idx === currentIndex;
                        const ready = seg.status === 'ready';
                        const processing = seg.status === 'processing' || seg.status === 'pending';

                        return (
                            <button
                                key={seg.segment_index}
                                onClick={() => selectSegment(idx)}
                                disabled={!ready}
                                className={`
                                    relative w-full text-right p-4 rounded-xl border transition-all duration-200 flex flex-col gap-2 group
                                    ${active ? 'border-indigo-500 bg-white shadow-lg ring-1 ring-indigo-500 transform scale-[1.02] z-10' :
                                        ready ? 'border-green-200 bg-green-50/50 hover:bg-white' :
                                            processing ? 'border-blue-200 bg-blue-50/50' : 'border-red-200 bg-red-50'}
                                    ${!ready && !active ? 'opacity-70 grayscale-[0.3]' : ''}
                                `}
                            >
                                <div className="flex justify-between items-start w-full">
                                    <div className="flex items-center gap-3">
                                        <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold ${active ? 'bg-indigo-600 text-white' : 'bg-gray-200 text-gray-500'}`}>
                                            {idx + 1}
                                        </div>
                                        <div>
                                            <h4 className={`font-bold text-sm ${active ? 'text-indigo-900' : 'text-gray-700'}`}>
                                                المقطع {idx + 1}
                                            </h4>
                                            {/* FIX 1: Removed hardcoded duration. Ideally passed from BE, but cleaner to just show status or leave blank until played */}
                                            {active && duration > 0 && <span className="text-xs text-indigo-600 font-mono">{formatTime(duration)}</span>}
                                            {/* Status Icon */}
                                            <div className="mt-1 flex items-center gap-2">
                                                {/* Download Button (V2) */}
                                                {ready && seg.media_url && (
                                                    <a
                                                        href={seg.media_url}
                                                        download
                                                        target="_blank"
                                                        rel="noopener noreferrer"
                                                        className="p-1 hover:bg-gray-100 rounded-full text-gray-500 hover:text-indigo-600 transition-colors"
                                                        title="تحميل المقطع"
                                                        onClick={(e) => e.stopPropagation()}
                                                    >
                                                        <Upload className="w-4 h-4 rotate-180" />
                                                    </a>
                                                )}
                                                {ready && <CheckCircle className="w-5 h-5 text-green-500" />}
                                                {processing && <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />}
                                                {failed && <RefreshCw className="w-5 h-5 text-red-500" />}
                                                {!ready && !processing && !failed && <Lock className="w-4 h-4 text-gray-300" />}
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </button>
                        );
                    })}
                </div>
            </div>

            {/* --- LEFT MAIN VIDEO --- */}
            <div className="flex-1 bg-black relative group overflow-hidden flex flex-col justify-center min-h-[400px]">
                {/* FIX 2: Aspect Ratio Wrapper */}
                <div className="relative w-full aspect-video bg-black">
                    {isReady ? (
                        <video
                            ref={videoRef}
                            src={currentSegment?.media_url}
                            className="w-full h-full"
                            playsInline
                            crossOrigin="anonymous"
                            onEnded={handleEnded}
                            onTimeUpdate={handleTimeUpdate}
                            onLoadedMetadata={handleLoadedMetadata} // FIX 1: Get Real Duration
                            onClick={togglePlay}
                            poster={currentIndex === 0 ? poster : undefined}
                        />
                    ) : (
                        <div className="absolute inset-0 flex flex-col items-center justify-center bg-zinc-900 text-white gap-4">
                            {isProcessing ? (
                                <>
                                    <Loader2 className="w-16 h-16 text-indigo-500 animate-spin" />
                                    <h3 className="text-xl font-bold">جاري تجهيز المقطع {currentIndex + 1}...</h3>
                                </>
                            ) : (
                                <h3 className="text-xl font-bold">في انتظار البدء...</h3>
                            )}
                        </div>
                    )}

                    {/* Next Overlay */}
                    {nextOverlayVisible && (
                        <div className="absolute inset-0 bg-black/80 backdrop-blur-sm z-30 flex flex-col items-center justify-center text-white animate-in fade-in duration-300">
                            <Loader2 className="w-12 h-12 text-indigo-500 animate-spin mx-auto mb-4" />
                            <h3 className="text-2xl font-bold">المقطع التالي قيد المعالجة...</h3>
                        </div>
                    )}

                    {/* Big Play Button */}
                    {!isPlaying && isReady && !nextOverlayVisible && (
                        <div className="absolute inset-0 flex items-center justify-center bg-black/30 cursor-pointer z-20" onClick={togglePlay}>
                            <div className="w-20 h-20 bg-white/20 backdrop-blur-md rounded-full flex items-center justify-center hover:scale-110 transition-transform">
                                <Play className="w-10 h-10 text-white fill-current ml-1" />
                            </div>
                        </div>
                    )}
                </div>

                {/* FIX 3: REAL CONTROLS BAR */}
                {isReady && (
                    <div className="bg-zinc-900 text-white p-3 flex items-center gap-4 border-t border-zinc-800" dir="ltr">
                        <button onClick={togglePlay} className="hover:text-indigo-400">
                            {isPlaying ? <Pause className="w-6 h-6 fill-current" /> : <Play className="w-6 h-6 fill-current" />}
                        </button>

                        {/* Seek Bar */}
                        <div className="flex-1 flex items-center gap-2">
                            <span className="text-xs font-mono text-zinc-400">{formatTime(currentTime)}</span>
                            <input
                                type="range"
                                min="0"
                                max={duration || 100}
                                value={currentTime}
                                onChange={handleSeek}
                                className="flex-1 h-1 bg-zinc-700 rounded-lg appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:bg-indigo-500 [&::-webkit-slider-thumb]:rounded-full"
                            />
                            <span className="text-xs font-mono text-zinc-400">{formatTime(duration)}</span>
                        </div>

                        {/* Volume */}
                        <div className="flex items-center gap-2 w-32">
                            <button onClick={() => setIsMuted(!isMuted)}>
                                {isMuted || volume === 0 ? <VolumeX className="w-5 h-5" /> : <Volume2 className="w-5 h-5" />}
                            </button>
                            <input
                                type="range"
                                min="0"
                                max="1"
                                step="0.1"
                                value={isMuted ? 0 : volume}
                                onChange={(e) => {
                                    setVolume(parseFloat(e.target.value));
                                    setIsMuted(parseFloat(e.target.value) === 0);
                                }}
                                className="w-full h-1 bg-zinc-700 rounded-lg appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:bg-white [&::-webkit-slider-thumb]:rounded-full"
                            />
                        </div>

                        {/* Subtitles (Placeholder for V2) */}
                        <button disabled className="opacity-50 cursor-not-allowed" title="Subtitles coming soon">
                            <Captions className="w-5 h-5" />
                        </button>

                        <button onClick={toggleFullscreen} className="hover:text-indigo-400">
                            <Maximize className="w-5 h-5" />
                        </button>
                    </div>
                )}
            </div>
        </div>
    );
};

