/**
 * API Service for Arab Dubbing Platform
 * Connects frontend to FastAPI backend
 */

import { ProcessingStage, TaskStatus, ServiceMode } from '../types';

// Backend URL - configurable via environment variable
const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000';

// Use mock backend for development when real backend is not available
const USE_MOCK = import.meta.env.VITE_USE_MOCK_BACKEND === 'true';

interface ProcessRequest {
  url: string;
  target_lang: string;
  mode: ServiceMode;
}

interface ProcessResponse {
  task_id: string;
  status: string;
  progress: number;
  message: string;
  stage?: string;
  result?: {
    title?: string;
    thumbnail?: string;
    original_text?: string;
    translated_text?: string;
    // Support ALL possible video URL keys from backend
    dubbed_video_url?: string;
    translated_video_url?: string;
    output_video_url?: string;
    video_url?: string;
    url?: string;
    // SRT
    srt_url?: string;
    subtitle_url?: string;
    // Other fields
    mode?: string;
    detected_language?: string;
    segments_count?: number;
  };
}

/**
 * Normalize video URL from result - handles different key names
 */
function normalizeVideoUrl(result: ProcessResponse['result']): string | undefined {
  if (!result) return undefined;
  return result.dubbed_video_url
    || result.translated_video_url
    || result.output_video_url
    || result.video_url
    || result.url;
}

/**
 * Normalize SRT URL from result - handles different key names
 */
function normalizeSrtUrl(result: ProcessResponse['result']): string | undefined {
  if (!result) return undefined;
  return result.srt_url || result.subtitle_url;
}

/**
 * Map backend stage to frontend ProcessingStage enum
 */
function mapStageToEnum(stage: string): ProcessingStage {
  const stageMap: Record<string, ProcessingStage> = {
    'PENDING': ProcessingStage.DOWNLOAD,
    'DOWNLOAD': ProcessingStage.DOWNLOAD,
    'DOWNLOADING': ProcessingStage.DOWNLOAD,
    'EXTRACTING': ProcessingStage.DOWNLOAD,
    'TRANSCRIPTION': ProcessingStage.TRANSCRIPTION,
    'TRANSCRIBING': ProcessingStage.TRANSCRIPTION,
    'TRANSLATION': ProcessingStage.TRANSLATION,
    'TRANSLATING': ProcessingStage.TRANSLATION,
    'VOICE_GENERATION': ProcessingStage.VOICE_GENERATION,
    'GENERATING_AUDIO': ProcessingStage.VOICE_GENERATION,
    'VOICE': ProcessingStage.VOICE_GENERATION,
    'SUBTITLE_GENERATION': ProcessingStage.SUBTITLE_GENERATION,
    'GENERATING_SUBTITLES': ProcessingStage.SUBTITLE_GENERATION,
    'GENERATING_SRT': ProcessingStage.SUBTITLE_GENERATION,
    'SYNCING': ProcessingStage.SYNCING,
    'MERGING': ProcessingStage.SYNCING,
    'UPLOADING': ProcessingStage.SYNCING,
    'FINALIZING': ProcessingStage.FINALIZING,
    'COMPLETED': ProcessingStage.FINALIZING,
    'FAILED': ProcessingStage.DOWNLOAD,
  };
  return stageMap[stage] || ProcessingStage.DOWNLOAD;
}

/**
 * Start a new processing job
 */
export async function startProcessing(
  url: string,
  mode: ServiceMode,
  targetLang: string = 'ar'
): Promise<{ taskId: string; success: boolean; error?: string }> {
  try {
    const response = await fetch(`${BACKEND_URL}/process`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        url,
        mode,
        target_lang: targetLang,
      } as ProcessRequest),
    });

    if (!response.ok) {
      const error = await response.json();
      return { taskId: '', success: false, error: error.detail || 'فشل بدء المعالجة' };
    }

    const data: ProcessResponse = await response.json();
    return { taskId: data.task_id, success: true };
  } catch (error) {
    console.error('API Error:', error);
    return { taskId: '', success: false, error: 'تعذر الاتصال بالخادم' };
  }
}

/**
 * Upload video file directly for processing (bypasses YouTube restrictions)
 */
export async function uploadVideo(
  file: File,
  mode: ServiceMode,
  targetLang: string = 'ar',
  onProgress?: (progress: number) => void
): Promise<{ taskId: string; success: boolean; error?: string }> {
  try {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('mode', mode);
    formData.append('target_lang', targetLang);

    const response = await fetch(`${BACKEND_URL}/upload`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json();
      return { taskId: '', success: false, error: error.detail || 'فشل رفع الملف' };
    }

    const data: ProcessResponse = await response.json();
    return { taskId: data.task_id, success: true };
  } catch (error) {
    console.error('Upload Error:', error);
    return { taskId: '', success: false, error: 'فشل رفع الملف. تحقق من الاتصال.' };
  }
}

/**
 * Poll for task status
 */
export async function getTaskStatus(taskId: string): Promise<{
  status: TaskStatus;
  completed: boolean;
  failed: boolean;
  result?: ProcessResponse['result'];
}> {
  try {
    const response = await fetch(`${BACKEND_URL}/status/${taskId}`);

    if (!response.ok) {
      throw new Error('Failed to get status');
    }

    const data: ProcessResponse = await response.json();

    // Normalize the result to ensure consistent video URL key
    let normalizedResult = data.result;
    if (data.result) {
      const videoUrl = normalizeVideoUrl(data.result);
      const srtUrl = normalizeSrtUrl(data.result);

      // Create normalized result with consistent key names
      normalizedResult = {
        ...data.result,
        dubbed_video_url: videoUrl,  // Always use this key
        srt_url: srtUrl,  // Always use this key
      };

      console.log('📹 Video URL:', videoUrl);
      console.log('📄 SRT URL:', srtUrl);
    }

    return {
      status: {
        taskId: data.task_id,
        progress: data.progress,
        stage: mapStageToEnum(data.stage || 'PENDING'),
        message: data.message,
      },
      completed: data.status === 'COMPLETED',
      failed: data.status === 'FAILED',
      result: normalizedResult,
    };
  } catch (error) {
    console.error('Status polling error:', error);
    throw error;
  }
}

/**
 * Get download URL for processed files
 */
export function getDownloadUrl(taskId: string, fileType: 'video' | 'audio' | 'srt'): string {
  return `${BACKEND_URL}/download/${taskId}/${fileType}`;
}

/**
 * Get static file URL (for streaming video)
 * Handles: Supabase public URLs, local /output/ paths, and relative paths
 */
export function getOutputUrl(path: string): string {
  if (!path) return '';

  // Already a full URL (Supabase public URL)
  if (path.startsWith('http://') || path.startsWith('https://')) {
    return path;
  }

  // Local output path
  if (path.startsWith('/output/')) {
    return `${BACKEND_URL}${path}`;
  }

  // Relative path
  return `${BACKEND_URL}/output/${path}`;
}

/**
 * Check if backend is healthy
 * Uses root "/" endpoint for Render health check compatibility
 */
export async function checkBackendHealth(): Promise<boolean> {
  try {
    // Use AbortController for timeout (Render free tier can be slow to wake up)
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 10000); // 10 second timeout

    const response = await fetch(`${BACKEND_URL}/`, {
      method: 'GET',
      signal: controller.signal
    });

    clearTimeout(timeoutId);
    return response.ok;
  } catch (error) {
    console.warn('Backend health check failed:', error);
    return false;
  }
}

/**
 * Real-time processing with callbacks
 * This replaces the mock simulateProcessing function
 */
export function startRealProcessing(
  url: string,
  mode: ServiceMode,
  onUpdate: (status: TaskStatus) => void,
  onComplete: (result: ProcessResponse['result']) => void,
  onError: (msg: string) => void,
  targetLang: string = 'ar'
): () => void {
  let isActive = true;
  let pollInterval: ReturnType<typeof setInterval> | null = null;

  const startPolling = async () => {
    try {
      // Start the processing job
      const { taskId, success, error } = await startProcessing(url, mode, targetLang);

      if (!success || !taskId) {
        onError(error || 'فشل بدء المعالجة');
        return;
      }

      // Poll for status
      pollInterval = setInterval(async () => {
        if (!isActive) {
          if (pollInterval) clearInterval(pollInterval);
          return;
        }

        try {
          const { status, completed, failed, result } = await getTaskStatus(taskId);

          onUpdate(status);

          if (completed) {
            if (pollInterval) clearInterval(pollInterval);
            onComplete(result);
          } else if (failed) {
            if (pollInterval) clearInterval(pollInterval);
            onError(status.message || 'فشلت المعالجة');
          }
        } catch (err) {
          console.error('Polling error:', err);
        }
      }, 1500); // Poll every 1.5 seconds
    } catch (err) {
      onError('حدث خطأ غير متوقع');
    }
  };

  startPolling();

  // Return cleanup function
  return () => {
    isActive = false;
    if (pollInterval) clearInterval(pollInterval);
  };
}

export { USE_MOCK, BACKEND_URL };
