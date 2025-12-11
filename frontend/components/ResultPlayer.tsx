
import React, { useState, useRef, useEffect } from 'react';
import { Download, Share2, Wand2, Play, Pause, Volume2, VolumeX, Maximize, Minimize, RefreshCw, Loader2, Captions } from 'lucide-react';
import { Button } from './Button';
import { VideoMetadata } from '../types';
import { getOutputUrl, getDownloadUrl, BACKEND_URL } from '../services/apiService';

interface ResultPlayerProps {
  metadata: VideoMetadata | null;
  onReset: () => void;
  t: any;
  taskId?: string;
  result?: {
    dubbed_video_url?: string;
    srt_url?: string;
    title?: string;
    thumbnail?: string;
  };
}

// Helper to extract YouTube ID
const getYoutubeId = (url: string) => {
  if (!url) return null;
  // Regex to capture video ID from standard links, shorts, and embeds
  const regExp = /^.*((youtu.be\/)|(v\/)|(\/u\/\w\/)|(embed\/)|(watch\?))\??v?=?([^#&?]*).*/;
  const match = url.match(regExp);
  return (match && match[7].length >= 11) ? match[7] : null;
};

// Helper to format time (seconds -> mm:ss)
const formatTime = (time: number) => {
  if (isNaN(time)) return "00:00";
  const minutes = Math.floor(time / 60);
  const seconds = Math.floor(time % 60);
  return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
};

// Simulated download
const downloadMockFile = (filename: string, content: string, mimeType: string) => {
  const blob = new Blob([content], { type: mimeType });
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(url);
  document.body.removeChild(a);
};

const MOCK_DUBBED_VIDEO_URL = "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/TearsOfSteel.mp4";

export const ResultPlayer: React.FC<ResultPlayerProps> = ({ metadata, onReset, t, taskId, result }) => {
  const mode = metadata?.mode || 'BOTH';

  // Determine video source - use real backend URL if available
  const videoSource = result?.dubbed_video_url
    ? getOutputUrl(result.dubbed_video_url)
    : MOCK_DUBBED_VIDEO_URL;

  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(1);
  const [isMuted, setIsMuted] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [showControls, setShowControls] = useState(true);

  // Subtitle State
  const [showSubtitles, setShowSubtitles] = useState(mode === 'SUBTITLES' || mode === 'BOTH');
  const [vttUrl, setVttUrl] = useState<string | null>(null);

  const videoRef = useRef<HTMLVideoElement>(null);
  const playerContainerRef = useRef<HTMLDivElement>(null);
  const controlsTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const videoId = metadata?.url ? getYoutubeId(metadata.url) : null;
  const thumbnailUrl = videoId
    ? `https://img.youtube.com/vi/${videoId}/maxresdefault.jpg`
    : (metadata?.thumbnail || "https://picsum.photos/800/450");

  // Generate VTT Blob on mount
  useEffect(() => {
    const summary = metadata?.smartSummary || "شرح توضيحي لمحتوى الفيديو";
    // Create a simple WebVTT content
    const vttContent = `WEBVTT

00:00:01.000 --> 00:00:06.000
${summary}

00:00:06.500 --> 00:00:12.000
تمت الترجمة والدبلجة بواسطة منصة دبلجني للذكاء الاصطناعي

00:00:12.500 --> 00:00:20.000
نقدم لكم تجربة مشاهدة ممتعة مع دقة عالية في الترجمة`;

    const blob = new Blob([vttContent], { type: 'text/vtt' });
    const url = URL.createObjectURL(blob);
    setVttUrl(url);

    return () => {
      URL.revokeObjectURL(url);
    };
  }, [metadata]);

  // Sync state with text track mode
  useEffect(() => {
    if (videoRef.current && videoRef.current.textTracks && videoRef.current.textTracks[0]) {
      videoRef.current.textTracks[0].mode = showSubtitles ? 'showing' : 'hidden';
    }
  }, [showSubtitles, vttUrl]);


  // --- Video Event Handlers ---

  const togglePlay = () => {
    if (videoRef.current) {
      if (isPlaying) {
        videoRef.current.pause();
      } else {
        videoRef.current.play();
      }
      setIsPlaying(!isPlaying);
    }
  };

  const handleTimeUpdate = () => {
    if (videoRef.current) {
      setCurrentTime(videoRef.current.currentTime);
    }
  };

  const handleLoadedMetadata = () => {
    if (videoRef.current) {
      setDuration(videoRef.current.duration);
      // Ensure subtitles respect initial state
      if (videoRef.current.textTracks && videoRef.current.textTracks[0]) {
        videoRef.current.textTracks[0].mode = showSubtitles ? 'showing' : 'hidden';
      }
    }
  };

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const time = parseFloat(e.target.value);
    if (videoRef.current) {
      videoRef.current.currentTime = time;
      setCurrentTime(time);
    }
  };

  const handleVolumeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newVolume = parseFloat(e.target.value);
    setVolume(newVolume);
    if (videoRef.current) {
      videoRef.current.volume = newVolume;
      setIsMuted(newVolume === 0);
    }
  };

  const toggleMute = () => {
    if (videoRef.current) {
      const newMutedState = !isMuted;
      setIsMuted(newMutedState);
      videoRef.current.muted = newMutedState;
      if (newMutedState) {
        setVolume(0);
      } else {
        setVolume(1);
        videoRef.current.volume = 1;
      }
    }
  };

  const toggleSubtitles = () => {
    setShowSubtitles(!showSubtitles);
  };

  const toggleFullscreen = () => {
    if (!playerContainerRef.current) return;

    if (!document.fullscreenElement) {
      playerContainerRef.current.requestFullscreen().catch(err => {
        console.error(`Error attempting to enable fullscreen: ${err.message}`);
      });
    } else {
      document.exitFullscreen();
    }
  };

  // Listen for fullscreen changes to update state
  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };
    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => document.removeEventListener('fullscreenchange', handleFullscreenChange);
  }, []);

  // Auto-hide controls
  const handleMouseMove = () => {
    setShowControls(true);
    if (controlsTimeoutRef.current) clearTimeout(controlsTimeoutRef.current);
    if (isPlaying) {
      controlsTimeoutRef.current = setTimeout(() => {
        setShowControls(false);
      }, 2500);
    }
  };

  const handleVideoEnded = () => {
    setIsPlaying(false);
    setShowControls(true);
  };

  // --- Download Logic ---
  const handleDownload = (type: 'mp4' | 'wav' | 'srt') => {
    const timestamp = new Date().toISOString().split('T')[0];
    const safeTitle = metadata?.title?.replace(/[^a-z0-9]/gi, '_') || 'video';

    if (type === 'mp4') {
      // Use real backend URL if taskId exists
      if (taskId) {
        window.open(getDownloadUrl(taskId, 'video'), '_blank');
      } else if (result?.dubbed_video_url) {
        window.open(getOutputUrl(result.dubbed_video_url), '_blank');
      } else {
        downloadMockFile(`${safeTitle}_final_${timestamp}.mp4`, 'Mock Video Content', 'video/mp4');
      }
    } else if (type === 'wav') {
      if (taskId) {
        window.open(getDownloadUrl(taskId, 'audio'), '_blank');
      } else {
        downloadMockFile(`${safeTitle}_audio_${timestamp}.wav`, 'Mock Audio Content', 'audio/wav');
      }
    } else if (type === 'srt') {
      if (taskId) {
        window.open(getDownloadUrl(taskId, 'srt'), '_blank');
      } else if (result?.srt_url) {
        window.open(getOutputUrl(result.srt_url), '_blank');
      } else {
        const srtContent = `1\n00:00:01,000 --> 00:00:06,000\n${metadata?.smartSummary || 'ترجمة تجريبية للفيديو'}\n\n2\n00:00:06,500 --> 00:00:12,000\nتمت المعالجة بواسطة دبلجة العرب`;
        downloadMockFile(`${safeTitle}_subs_${timestamp}.srt`, srtContent, 'text/plain');
      }
    }
  };

  return (
    <div className="w-full max-w-5xl mx-auto animate-in fade-in slide-in-from-bottom-8 duration-700">

      <div className="mb-8 text-center">
        <div className="inline-flex items-center justify-center p-3 bg-green-100 dark:bg-green-500/10 rounded-full mb-4">
          <Wand2 className="w-8 h-8 text-green-600 dark:text-green-400" />
        </div>
        <h2 className="text-3xl font-bold text-slate-900 dark:text-white mb-2">{t.successTitle}</h2>
        <p className="text-slate-600 dark:text-slate-400">{t.successDesc}</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">

        {/* Main Player */}
        <div className="lg:col-span-2 space-y-4">
          <div
            ref={playerContainerRef}
            className="relative aspect-video bg-black rounded-2xl overflow-hidden border border-slate-200 dark:border-slate-700 shadow-2xl group select-none"
            onMouseMove={handleMouseMove}
            onMouseLeave={() => isPlaying && setShowControls(false)}
          >
            <video
              ref={videoRef}
              className="w-full h-full object-contain"
              poster={thumbnailUrl}
              src={videoSource}
              onClick={togglePlay}
              onTimeUpdate={handleTimeUpdate}
              onLoadedMetadata={handleLoadedMetadata}
              onEnded={handleVideoEnded}
              crossOrigin="anonymous"
            >
              {vttUrl && <track kind="subtitles" src={vttUrl} srcLang="ar" label="Arabic" default={showSubtitles} />}
              Your browser does not support the video tag.
            </video>

            {/* Big Center Play Button (Visible when paused or buffering) */}
            {!isPlaying && (
              <div className="absolute inset-0 flex items-center justify-center bg-black/40 backdrop-blur-[2px] transition-all duration-300">
                <button
                  onClick={togglePlay}
                  className="w-20 h-20 bg-white/20 hover:bg-white/30 backdrop-blur-md rounded-full flex items-center justify-center border border-white/40 shadow-2xl transform hover:scale-110 transition-all group-hover:shadow-indigo-500/40"
                  aria-label="Play Video"
                >
                  <Play className="w-8 h-8 text-white ml-1 fill-white" />
                </button>
              </div>
            )}

            {/* Mode Badge */}
            <div className="absolute top-4 left-4 z-10 pointer-events-none">
              <div className="bg-black/60 backdrop-blur-md text-white px-3 py-1 rounded-lg text-xs font-bold border border-white/10 shadow-lg">
                {mode === 'DUBBING' ? t.modeDubbing : mode === 'SUBTITLES' ? t.modeSubtitles : t.modeBoth}
              </div>
            </div>

            {/* Custom Control Bar - FORCED LTR */}
            <div
              dir="ltr"
              className={`absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/90 via-black/60 to-transparent px-4 py-4 transition-opacity duration-300 ${showControls ? 'opacity-100' : 'opacity-0'}`}
            >
              {/* Progress Bar */}
              <div dir="ltr" className="relative group/seeker h-1.5 mb-4 cursor-pointer">
                <div className="absolute inset-0 bg-white/30 rounded-full"></div>
                <div
                  className="absolute top-0 left-0 h-full bg-indigo-500 rounded-full"
                  style={{ width: `${(currentTime / duration) * 100}%` }}
                ></div>
                <input
                  type="range"
                  min="0"
                  max={duration || 100}
                  value={currentTime}
                  onChange={handleSeek}
                  className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                />
              </div>

              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  {/* Play/Pause Small */}
                  <button onClick={togglePlay} className="text-white hover:text-indigo-400 transition-colors">
                    {isPlaying ? <Pause className="w-6 h-6 fill-current" /> : <Play className="w-6 h-6 fill-current" />}
                  </button>

                  {/* Volume */}
                  <div dir="ltr" className="flex items-center gap-2 group/volume">
                    <button onClick={toggleMute} className="text-white hover:text-indigo-400 transition-colors">
                      {isMuted || volume === 0 ? <VolumeX className="w-5 h-5" /> : <Volume2 className="w-5 h-5" />}
                    </button>
                    <div className="w-0 overflow-hidden group-hover/volume:w-20 transition-all duration-300 ease-in-out">
                      <input
                        type="range"
                        min="0"
                        max="1"
                        step="0.1"
                        value={isMuted ? 0 : volume}
                        onChange={handleVolumeChange}
                        className="w-20 h-1 accent-indigo-500"
                      />
                    </div>
                  </div>

                  {/* Time Display */}
                  <span dir="ltr" className="text-white text-xs font-mono font-medium opacity-90">
                    {formatTime(currentTime)} / {formatTime(duration)}
                  </span>
                </div>

                <div className="flex items-center gap-3">
                  {/* Subtitles Toggle */}
                  <button
                    onClick={toggleSubtitles}
                    className={`transition-colors ${showSubtitles ? 'text-indigo-400' : 'text-white hover:text-indigo-400'}`}
                    title="Toggle Subtitles"
                  >
                    <Captions className="w-5 h-5" />
                  </button>

                  <button onClick={toggleFullscreen} className="text-white hover:text-indigo-400 transition-colors">
                    {isFullscreen ? <Minimize className="w-5 h-5" /> : <Maximize className="w-5 h-5" />}
                  </button>
                </div>
              </div>
            </div>
          </div>

          <div className="bg-white dark:bg-slate-800/50 rounded-xl p-6 border border-slate-200 dark:border-slate-700 shadow-sm">
            <div className="flex items-start justify-between">
              <div>
                <h3 className="text-xl font-bold text-slate-900 dark:text-white mb-2 leading-tight">{metadata?.title}</h3>
                <p className="text-sm text-slate-600 dark:text-slate-400 leading-relaxed max-w-2xl">{metadata?.smartSummary}</p>
              </div>
            </div>
          </div>
        </div>

        {/* Sidebar Actions */}
        <div className="space-y-4">
          <div className="bg-white dark:bg-slate-800 rounded-2xl p-6 border border-slate-200 dark:border-slate-700 shadow-lg h-full flex flex-col">
            <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-6 flex items-center gap-2">
              <Download className="w-5 h-5 text-indigo-500" />
              {t.exportOptions}
            </h3>

            <div className="space-y-4 flex-1">
              <Button
                variant="primary"
                className="w-full justify-between group h-14"
                icon={<Download className="w-5 h-5 group-hover:translate-y-0.5 transition-transform" />}
                onClick={() => handleDownload('mp4')}
              >
                <span>{t.downloadVideo}</span>
                <span className="text-xs font-bold bg-white/20 px-2 py-0.5 rounded text-white">HD</span>
              </Button>

              {/* Show Audio only if Dubbing or Both was selected */}
              {(mode === 'DUBBING' || mode === 'BOTH') && (
                <Button
                  variant="secondary"
                  className="w-full justify-between h-12"
                  icon={<Volume2 className="w-5 h-5" />}
                  onClick={() => handleDownload('wav')}
                >
                  <span>{t.downloadAudio}</span>
                  <span className="text-xs bg-slate-200 dark:bg-slate-600 px-2 py-0.5 rounded">WAV</span>
                </Button>
              )}

              {/* Show SRT only if Subtitles or Both was selected */}
              {(mode === 'SUBTITLES' || mode === 'BOTH') && (
                <Button
                  variant="outline"
                  className="w-full justify-between h-12"
                  icon={<Share2 className="w-5 h-5" />}
                  onClick={() => handleDownload('srt')}
                >
                  <span>{t.downloadSub}</span>
                  <span className="text-xs bg-indigo-5 dark:bg-indigo-900/50 px-2 py-0.5 rounded">SRT</span>
                </Button>
              )}
            </div>

            <div className="mt-8 pt-6 border-t border-slate-200 dark:border-slate-700 space-y-4">
              <button
                onClick={onReset}
                className="w-full py-3 rounded-xl border border-dashed border-slate-300 dark:border-slate-600 text-slate-500 hover:text-indigo-600 hover:border-indigo-500 dark:hover:text-indigo-400 dark:hover:border-indigo-400 transition-all font-medium flex items-center justify-center gap-2"
              >
                <RefreshCw className="w-4 h-4" />
                {t.dubAnother}
              </button>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
