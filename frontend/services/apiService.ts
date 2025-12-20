import axios from 'axios';
import { ProcessingStage, TaskStatus, ServiceMode } from '../types';

// ✅ LIVE RENDER BACKEND
export const API_BASE_URL = 'https://video-dubber-5zuo.onrender.com';
export const BACKEND_URL = API_BASE_URL;

// --- Interfaces ---
export interface TaskResponse {
  task_id: string;
  status: string;
  progress: number;
  message: string;
  result?: {
    dubbed_video_url?: string;
    title?: string;
    [key: string]: any;
  };
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
  voice: string = 'female',  // NEW: Voice selection
  generateSrt: boolean = true  // NEW: SRT generation
): Promise<{ taskId: string; success: boolean; error?: string }> => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('mode', mode);
  formData.append('target_lang', targetLanguage);
  formData.append('voice', voice);
  formData.append('generate_srt_file', generateSrt ? 'true' : 'false');

  try {
    const response = await axios.post<TaskResponse>(`${API_BASE_URL}/process-video`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 60000, // 60s timeout for initial handshake (job creation)
    });

    return {
      taskId: response.data.task_id,
      success: true
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
    const response = await axios.get<TaskResponse>(`${API_BASE_URL}/status/${taskId}`);
    const data = response.data;

    const status: TaskStatus = {
      taskId: taskId,
      progress: data.progress || 0,
      stage: mapStatusToStage(data.status),
      message: data.message || ''
    };

    // Ensure absolute URL for video
    if (data.result?.dubbed_video_url && !data.result.dubbed_video_url.startsWith('http')) {
      data.result.dubbed_video_url = `${API_BASE_URL}${data.result.dubbed_video_url}`;
    }

    return {
      status,
      completed: data.status === 'COMPLETED',
      failed: data.status === 'FAILED',
      result: data.result
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


