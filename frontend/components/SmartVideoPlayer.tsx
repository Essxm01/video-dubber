import React, { useState, useEffect, useRef } from 'react';
import { Play, Loader2, RefreshCw } from 'lucide-react';
import { getJobDetails, VideoSegment } from '../services/apiService';

interface SmartVideoPlayerProps {
    jobId: string;
    poster?: string;
    onAllFinished?: () => void;
}

export const SmartVideoPlayer: React.FC<SmartVideoPlayerProps> = ({ jobId, poster, onAllFinished }) => {
    const [segments, setSegments] = useState<VideoSegment[]>([]);
    const [currentIndex, setCurrentIndex] = useState(0);
    const [isPlaying, setIsPlaying] = useState(false);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState('');

    const videoRef = useRef<HTMLVideoElement>(null);
    const pollInterval = useRef<ReturnType<typeof setTimeout> | null>(null);

    // Poll for segments updates
    useEffect(() => {
        const fetchSegments = async () => {
            try {
                const data = await getJobDetails(jobId);
                if (data && data.segments) {
                    // Sort by index just in case
                    const sorted = data.segments.sort((a, b) => a.segment_index - b.segment_index);
                    setSegments(sorted);
                }
            } catch (err) {
                console.error("Failed to fetch segments", err);
            }
        };

        fetchSegments(); // Initial fetch
        pollInterval.current = setInterval(fetchSegments, 3000); // Poll every 3s

        return () => {
            if (pollInterval.current) clearInterval(pollInterval.current);
        };
    }, [jobId]);

    // Current active segment
    const currentSegment = segments.find(s => s.segment_index === currentIndex);

    // Auto-play logic when segment becomes ready
    useEffect(() => {
        if (isPlaying && currentSegment?.status === 'ready' && videoRef.current) {
            // If we were waiting for this segment, start playing
            const playPromise = videoRef.current.play();
            if (playPromise !== undefined) {
                playPromise.catch(error => {
                    console.log("Auto-play prevented", error);
                    setIsPlaying(false);
                });
            }
        }
    }, [currentSegment?.status, isPlaying]);

    const handlePlayClick = () => {
        setIsPlaying(true);
        if (videoRef.current) videoRef.current.play();
    };

    const handleEnded = () => {
        // Check if there is a next segment
        const nextIndex = currentIndex + 1;
        const nextSegment = segments.find(s => s.segment_index === nextIndex);

        if (nextSegment) {
            setCurrentIndex(nextIndex);
            // Ensure the loop effect handles the actual play trigger when 'ready'
        } else {
            // Check if we are truly done (no more segments expected) or just waiting for split?
            // For now, assuming if we reached the end of known segments, we might be done or waiting.
            // If the last known segment was the End of File, onAllFinished()
            // But we don't know total count easily unless backend sends it.
            // We'll just stay in "waiting" state if we think there might be more.

            // For this MVP, let's just pause.
            // setIsPlaying(false); 
            // onAllFinished?.();
        }
    };

    // derived state for UI
    const isReady = currentSegment?.status === 'ready';
    const isProcessing = currentSegment?.status === 'processing' || currentSegment?.status === 'pending';
    const isFailed = currentSegment?.status === 'failed';

    return (
        <div className="relative w-full aspect-video bg-black rounded-xl overflow-hidden shadow-2xl group">
            {/* Video Element */}
            {isReady && (
                <video
                    ref={videoRef}
                    src={currentSegment.media_url || ''}
                    className="w-full h-full object-contain"
                    onEnded={handleEnded}
                    controls={false} // Custom controls or minimal default
                    playsInline
                    crossOrigin="anonymous"
                    poster={currentIndex === 0 ? poster : undefined}
                />
            )}

            {/* OVERLAYS */}

            {/* Initial Start (No Autoplay Rule) */}
            {!isPlaying && currentIndex === 0 && (
                <div className="absolute inset-0 flex items-center justify-center bg-black/40 backdrop-blur-sm z-20">
                    <button
                        onClick={handlePlayClick}
                        className="group/btn relative flex items-center justify-center w-20 h-20 bg-indigo-600 hover:bg-indigo-700 rounded-full transition-all hover:scale-105 active:scale-95 shadow-lg shadow-indigo-600/30"
                    >
                        <Play className="w-8 h-8 text-white fill-current ml-1" />
                        <span className="absolute -bottom-8 text-white font-medium text-sm tracking-wide opacity-0 group-hover/btn:opacity-100 transition-opacity">
                            Play Video
                        </span>
                    </button>
                </div>
            )}

            {/* Loading / Processing Next Segment */}
            {isPlaying && isProcessing && (
                <div className="absolute inset-0 flex flex-col items-center justify-center bg-zinc-900 z-10">
                    <Loader2 className="w-12 h-12 text-indigo-500 animate-spin mb-4" />
                    <h3 className="text-white font-bold text-lg">Generating Part {currentIndex + 1}...</h3>
                    <p className="text-zinc-400 text-sm max-w-xs text-center mt-2">
                        We utilize sequential processing to let you watch immediately.
                        Next segment will play automatically.
                    </p>
                </div>
            )}

            {/* Failed Segment */}
            {isFailed && (
                <div className="absolute inset-0 flex flex-col items-center justify-center bg-zinc-900 z-10">
                    <p className="text-red-500 mb-2">Segment {currentIndex + 1} Failed</p>
                    <button
                        onClick={() => window.location.reload()}
                        className="flex items-center gap-2 px-4 py-2 bg-zinc-800 rounded hover:bg-zinc-700 text-white"
                    >
                        <RefreshCw className="w-4 h-4" /> Retry
                    </button>
                </div>
            )}

            {/* Custom Controls (Simple) */}
            {isPlaying && isReady && (
                <div className="absolute bottom-0 left-0 right-0 p-4 bg-gradient-to-t from-black/80 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300">
                    <div className="text-white text-xs font-mono mb-1">
                        Segment {currentIndex + 1}
                    </div>
                    {/* Progress bar could go here */}
                </div>
            )}
        </div>
    );
};
