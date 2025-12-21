import React, { useState, useEffect, useRef } from 'react';
import {
    Play, Pause, Loader2, RefreshCw, Volume2, VolumeX,
    Maximize, SkipForward, List, CheckCircle, AlertCircle, Clock
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
    const [showPlaylist, setShowPlaylist] = useState(true);
    const [autoAdvance, setAutoAdvance] = useState(true);

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
                    // Only update if changes to avoid re-renders? 
                    // For now, simpler to just set, React handles diffing.
                    // Ideally check if status changed.
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

    // --- Current Segment Logic ---
    const currentSegment = segments.find(s => s.segment_index === currentIndex);
    const nextSegment = segments.find(s => s.segment_index === currentIndex + 1);

    const isReady = currentSegment?.status === 'ready';
    const isProcessing = currentSegment?.status === 'processing' || currentSegment?.status === 'pending';
    const isFailed = currentSegment?.status === 'failed';

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

    const skipToNext = () => {
        if (nextSegment && nextSegment.status === 'ready') {
            setCurrentIndex(currentIndex + 1);
            setIsPlaying(true); // Auto play next if skipped manually
        }
    };

    const handleSegmentClick = (index: number) => {
        const target = segments.find(s => s.segment_index === index);
        if (target?.status === 'ready') {
            setCurrentIndex(index);
            setIsPlaying(true);
        }
    };

    // --- Audio/Video Events ---
    const handleEnded = () => {
        if (!autoAdvance) {
            setIsPlaying(false);
            return;
        }

        if (nextSegment) {
            if (nextSegment.status === 'ready') {
                setCurrentIndex(currentIndex + 1);
                // The useEffect below will trigger play
            } else {
                // Next not ready, enters "waiting" state naturally via UI
                // We keep isPlaying=true so it resumes automatically when ready
            }
        } else {
            // End of all known segments
            setIsPlaying(false);
            onAllFinished?.();
        }
    };

    // --- Auto-play Effect ---
    useEffect(() => {
        // If we are "playing" but waiting for a segment, and it becomes ready:
        if (isPlaying && isReady && videoRef.current) {
            const playPromise = videoRef.current.play();
            if (playPromise !== undefined) {
                playPromise.catch(() => setIsPlaying(false));
            }
        }
    }, [currentIndex, isReady, isPlaying]); // Re-run when index changes or status changes

    // --- Render Helpers ---
    const getStatusIcon = (status: string) => {
        switch (status) {
            case 'ready': return <Play className="w-4 h-4 text-green-400" />;
            case 'processing': return <Loader2 className="w-4 h-4 text-indigo-400 animate-spin" />;
            case 'failed': return <AlertCircle className="w-4 h-4 text-red-500" />;
            default: return <Clock className="w-4 h-4 text-zinc-600" />;
        }
    };

    return (
        <div className="flex flex-col lg:flex-row gap-6 w-full max-w-6xl mx-auto p-4">

            {/* MAIN PLAYER CONTAINER */}
            <div
                ref={containerRef}
                className="flex-1 relative aspect-video bg-black rounded-2xl overflow-hidden shadow-2xl ring-1 ring-white/10 group"
            >
                {/* VIDEO ELEMENT */}
                {isReady ? (
                    <video
                        ref={videoRef}
                        src={currentSegment?.media_url}
                        className="w-full h-full object-contain"
                        onEnded={handleEnded}
                        onPlay={() => setIsPlaying(true)}
                        onPause={() => setIsPlaying(false)}
                        playsInline
                        crossOrigin="anonymous"
                        poster={currentIndex === 0 ? poster : undefined}
                    />
                ) : (
                    // PLACEHOLDER / LOADING STATE
                    <div className="absolute inset-0 flex flex-col items-center justify-center bg-zinc-900/90 backdrop-blur-sm">
                        {isProcessing && (
                            <>
                                <Loader2 className="w-16 h-16 text-indigo-500 animate-spin mb-6" />
                                <h3 className="text-2xl font-bold text-white mb-2">Generating Part {currentIndex + 1}</h3>
                                <p className="text-zinc-400 animate-pulse">Running AI Dubbing Pipeline...</p>
                            </>
                        )}
                        {isFailed && (
                            <>
                                <AlertCircle className="w-16 h-16 text-red-500 mb-6" />
                                <h3 className="text-2xl font-bold text-white mb-2">Generation Failed</h3>
                                <button
                                    onClick={() => window.location.reload()}
                                    className="mt-4 px-6 py-2 bg-red-600/20 hover:bg-red-600/40 text-red-400 rounded-full flex items-center gap-2 transition-all"
                                >
                                    <RefreshCw className="w-4 h-4" /> Retry Segment
                                </button>
                            </>
                        )}
                    </div>
                )}

                {/* BIG PLAY BUTTON (Initial) */}
                {!isPlaying && currentIndex === 0 && isReady && (
                    <div className="absolute inset-0 flex items-center justify-center bg-black/40 z-20 group-hover:bg-black/20 transition-all cursor-pointer" onClick={togglePlay}>
                        <div className="w-24 h-24 bg-indigo-600 rounded-full flex items-center justify-center shadow-lg shadow-indigo-600/30 scale-100 group-hover:scale-110 transition-transform duration-300">
                            <Play className="w-10 h-10 text-white fill-current ml-1" />
                        </div>
                    </div>
                )}

                {/* CUSTOM CONTROLS BAR */}
                <div className="absolute bottom-0 left-0 right-0 p-4 bg-gradient-to-t from-black/90 via-black/60 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300 flex items-center gap-4 z-30">

                    {/* Play/Pause */}
                    <button onClick={togglePlay} className="p-2 hover:bg-white/10 rounded-full text-white transition-colors">
                        {isPlaying ? <Pause className="w-6 h-6 fill-current" /> : <Play className="w-6 h-6 fill-current" />}
                    </button>

                    {/* Next Button */}
                    <button
                        onClick={skipToNext}
                        disabled={!nextSegment || nextSegment.status !== 'ready'}
                        className="p-2 hover:bg-white/10 rounded-full text-white transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                        title="Next Segment"
                    >
                        <SkipForward className="w-6 h-6" />
                    </button>

                    {/* Progress Text */}
                    <div className="flex-1 text-sm font-medium text-white/90">
                        <span className="text-indigo-400">Part {currentIndex + 1}</span>
                        <span className="text-zinc-500 mx-2">/</span>
                        <span className="text-zinc-400">{segments.length || '?'}</span>
                    </div>

                    {/* Volume */}
                    <button onClick={toggleMute} className="p-2 hover:bg-white/10 rounded-full text-white transition-colors">
                        {isMuted ? <VolumeX className="w-5 h-5" /> : <Volume2 className="w-5 h-5" />}
                    </button>

                    {/* Playlist Toggle (Mobile) */}
                    <button
                        onClick={() => setShowPlaylist(!showPlaylist)}
                        className="lg:hidden p-2 hover:bg-white/10 rounded-full text-white transition-colors"
                    >
                        <List className="w-5 h-5" />
                    </button>

                    {/* Fullscreen */}
                    <button onClick={toggleFullscreen} className="p-2 hover:bg-white/10 rounded-full text-white transition-colors">
                        <Maximize className="w-5 h-5" />
                    </button>
                </div>
            </div>

            {/* PLAYLIST SIDEBAR */}
            <div className={`
                ${showPlaylist ? 'flex' : 'hidden'} lg:flex 
                flex-col w-full lg:w-80 bg-zinc-900 border border-zinc-800 rounded-2xl overflow-hidden h-[500px] lg:h-auto shadow-xl
            `}>
                <div className="p-4 border-b border-zinc-800 bg-zinc-900/50 backdrop-blur sticky top-0 z-10 flex justify-between items-center">
                    <h3 className="font-bold text-white flex items-center gap-2">
                        <List className="w-4 h-4 text-indigo-500" />
                        Segments Playlist
                    </h3>
                    <div className="flex items-center gap-2">
                        <label className="text-xs text-zinc-400 flex items-center gap-2 cursor-pointer select-none">
                            <input
                                type="checkbox"
                                checked={autoAdvance}
                                onChange={(e) => setAutoAdvance(e.target.checked)}
                                className="rounded border-zinc-700 bg-zinc-800 text-indigo-600 focus:ring-indigo-500/30"
                            />
                            Auto-play
                        </label>
                    </div>
                </div>

                <div className="flex-1 overflow-y-auto p-2 space-y-2 custom-scrollbar">
                    {segments.length === 0 && (
                        <div className="text-center py-10 text-zinc-500 text-sm">
                            No segments yet...
                        </div>
                    )}

                    {segments.map((seg, idx) => {
                        const active = idx === currentIndex;
                        const ready = seg.status === 'ready';
                        const processing = seg.status === 'processing';

                        return (
                            <div
                                key={seg.segment_index}
                                onClick={() => handleSegmentClick(idx)}
                                className={`
                                    relative p-3 rounded-xl border transition-all duration-200 group cursor-pointer
                                    ${active
                                        ? 'bg-indigo-600/10 border-indigo-500/50 shadow-[0_0_15px_rgba(79,70,229,0.1)]'
                                        : 'bg-zinc-800/30 border-transparent hover:bg-zinc-800 hover:border-zinc-700'
                                    }
                                    ${!ready && !processing && active ? 'opacity-100' : ''}
                                    ${!ready && !active ? 'opacity-50 cursor-not-allowed' : ''}
                                `}
                            >
                                <div className="flex items-center justify-between mb-1">
                                    <span className={`text-xs font-bold uppercase tracking-wider ${active ? 'text-indigo-400' : 'text-zinc-500'}`}>
                                        Part {idx + 1}
                                    </span>
                                    <div className="flex items-center gap-2" title={seg.status}>
                                        {active && isPlaying && ready && (
                                            <span className="flex w-2 h-2">
                                                <span className="animate-ping absolute inline-flex h-2 w-2 rounded-full bg-green-400 opacity-75"></span>
                                                <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
                                            </span>
                                        )}
                                        {getStatusIcon(seg.status)}
                                    </div>
                                </div>

                                <div className="flex items-center justify-between">
                                    <span className={`text-sm font-medium ${active ? 'text-white' : 'text-zinc-400 group-hover:text-zinc-300'}`}>
                                        {ready ? "Ready to watch" : processing ? "Processing..." : "Waiting..."}
                                    </span>
                                    {ready && (
                                        <span className="text-[10px] bg-zinc-950/50 px-2 py-1 rounded text-zinc-500 font-mono">
                                            05:00
                                        </span>
                                    )}
                                </div>

                                {/* Progress Bar for specific segment processing? Future feature */}
                                {processing && (
                                    <div className="absolute bottom-0 left-0 right-0 h-1 bg-zinc-800 overflow-hidden rounded-b-xl">
                                        <div className="h-full bg-indigo-500/50 animate-progress origin-left"></div>
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>
            </div>
        </div>
    );
};

