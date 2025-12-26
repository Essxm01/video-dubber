import axios from 'axios';
import { ProcessingStage, TaskStatus, ServiceMode } from '../types';

// ===========================================================================
// 🌍 CONFIGURATION: DYNAMIC BACKEND LINKING
// ===========================================================================
// Priority 1: Vercel/Netlify Environment Variable (Production)
// Priority 2: Localhost (Development)
// ❌ STRICTLY FORBIDDEN: Hardcoded URLs like 'onrender.com' or 'koyeb.app'
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
export const BACKEND_URL = API_BASE_URL;

// Debug: Log active connection to console
console.log(`🔌 [API Service] Initialized (Force Build 🚀).`);
console.log(`🎯 [API Service] Connected to: ${API_BASE_URL}`);
// ===========================================================================

// --- Interfaces ---
export interface TaskResponse {
  task_id: string;
  status: string;
  progress?: number;
  message?: string;
  result?: {
    dubbed_video_url?: string;
    title?: string;
    [key: string]: any;
  };
  thumbnail_url?: string;
}

export interface VideoSegment {
  job_id: string;
  segment_index: number;
  status: 'pending' | 'processing' | 'ready' | 'failed';
  media_url?: string;
  gcs_path?: string;
}

export interface JobDetails {
  job_id: string;
  segments: VideoSegment[];
}

// --- Helper: Map backend status to ProcessingStage ---
function mapStatusToStage(status: string): ProcessingStage {
  const map: Record<string, ProcessingStage> = {
    'PENDING': ProcessingStage.DOWNLOAD,
    'EXTRACTING': ProcessingStage.DOWNLOAD,
    'TRANSCRIBING': ProcessingStage.TRANSCRIPTION,
    'TRANSLATING': ProcessingStage.TRANSLATION,
    'GENERATING_AUDIO': ProcessingStage.VOICE_GENERATION,
    'MERGING': ProcessingStage.SYNCING,
    'UPLOADING': ProcessingStage.SYNCING,
    'COMPLETED': ProcessingStage.FINALIZING,
    'FAILED': ProcessingStage.DOWNLOAD,
  };
  return map[status] || ProcessingStage.DOWNLOAD;
}

// --- Core Functions ---

/**
 * Upload video file for processing
 * Returns: { taskId, success, error }
 */
export const uploadVideo = async (
  file: File,
  mode: ServiceMode,
  targetLanguage: string = 'ar',
  voice: string = 'female',
  generateSrt: boolean = true
): Promise<{ taskId: string; task_id?: string; thumbnail_url?: string; success: boolean; error?: string }> => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('mode', mode);
  formData.append('target_lang', targetLanguage);

  // V9 Backend simply requires file + mode + target_lang
  // voice/srt params might be ignored by V9 simple pipeline but request them just in case
  formData.append('voice', voice);
  formData.append('generate_srt_file', generateSrt ? 'true' : 'false');

  try {
    // USE NEW /upload ENDPOINT (Async)
    const response = await axios.post(`${API_BASE_URL}/upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 120000, // 2 mins to be safe
    });

    const data = response.data;
    const jobId = data.job_id || data.task_id;

    return {
      taskId: jobId,
      task_id: jobId,
      success: true,
      thumbnail_url: data.thumbnail_url
    };
  } catch (error: any) {
    console.error("Upload Error:", error);
    const errorMsg = error.response?.data?.detail || error.message || 'فشل رفع الملف';
    return {
      taskId: '',
      success: false,
      error: errorMsg
    };
  }
};

/**
 * Get task status with completed/failed flags
 * Returns: { status, completed, failed, result }
 */
export const getTaskStatus = async (taskId: string): Promise<{
  status: TaskStatus;
  completed: boolean;
  failed: boolean;
  result?: TaskResponse['result'];
}> => {
  try {
    // Use NEW /job endpoint
    const response = await axios.get<JobDetails>(`${API_BASE_URL}/job/${taskId}`);
    const data = response.data;
    const segments = data.segments || [];

    // Calculate aggregated status
    const total = segments.length;
    const readyCount = segments.filter(s => s.status === 'ready').length;
    const failedCount = segments.filter(s => s.status === 'failed').length;

    let progress = 0;
    if (total > 0) {
      progress = Math.round((readyCount / total) * 100);
    }

    const isCompleted = total > 0 && readyCount === total;
    const isFailed = failedCount > 0;

    // Determine overall status string for mapping stage
    let statusStr = 'PROCESSING';
    if (isCompleted) statusStr = 'COMPLETED';
    else if (isFailed) statusStr = 'FAILED';
    else if (total === 0) statusStr = 'PENDING';

    const status: TaskStatus = {
      taskId: taskId,
      progress: progress,
      stage: mapStatusToStage(statusStr),
      message: isCompleted ? 'تمت الدبلجة بنجاح!' : `جاري المعالجة (${readyCount}/${total})...`
    };

    // Synthesize result
    let result = undefined;
    if (isCompleted && segments.length > 0) {
      // Find first media url
      const firstUrl = segments[0].media_url;
      result = {
        dubbed_video_url: firstUrl?.startsWith('http') || firstUrl?.startsWith('/') ? firstUrl : `${API_BASE_URL}${firstUrl}`,
        segments_count: total
      };

      // Ensure absolute URL if it's relative
      if (result.dubbed_video_url && result.dubbed_video_url.startsWith('/')) {
        result.dubbed_video_url = `${API_BASE_URL}${result.dubbed_video_url}`;
      }
    }

    return {
      status,
      completed: isCompleted,
      failed: isFailed,
      result: result
    };
  } catch (error) {
    console.error("Status Check Error:", error);
    return {
      status: { taskId, progress: 0, stage: ProcessingStage.DOWNLOAD, message: 'خطأ في الاتصال' },
      completed: false,
      failed: true,
      result: undefined
    };
  }
};

// Alias for backward compatibility
export const checkStatus = getTaskStatus;

/**
 * Check if backend is healthy
 */
export const checkBackendHealth = async (): Promise<boolean> => {
  try {
    const response = await axios.get(`${API_BASE_URL}/health`, { timeout: 5000 });
    return response.status === 200;
  } catch {
    // Try root endpoint as fallback
    try {
      await axios.get(API_BASE_URL, { timeout: 5000 });
      return true;
    } catch {
      return false;
    }
  }
};

/**
 * Start real processing for YouTube URLs
 * NOTE: Currently returns cleanup function that polls for status
 */
export const startRealProcessing = (
  videoUrl: string,
  mode: ServiceMode,
  onUpdate: (status: TaskStatus) => void,
  onComplete: (result?: TaskResponse['result']) => void,
  onError: (msg: string) => void,
  targetLang: string = 'ar'
): (() => void) => {
  // For now, YouTube processing is not implemented
  // Show error immediately
  setTimeout(() => {
    onError('معالجة روابط يوتيوب غير متاحة حالياً. الرجاء رفع الفيديو مباشرة.');
  }, 100);

  // Return empty cleanup function
  return () => { };
};

// Export for backward compatibility
export type { ServiceMode } from '../types';

/**
 * Fetch job details and segments
 */
export const getJobDetails = async (jobId: string): Promise<JobDetails | null> => {
  try {
    const response = await axios.get<JobDetails>(`${API_BASE_URL}/job/${jobId}`);
    return response.data;
  } catch (error) {
    console.error("Fetch Job Details Error:", error);
    return null;
  }
};


