import axios from 'axios';

// ✅ FIXED: Point to the live Render Backend
const API_BASE_URL = 'https://video-dubber-5zuo.onrender.com';

export type ServiceMode = 'DUBBING' | 'TRANSLATION' | 'SUBTITLES';

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

export const uploadVideo = async (file: File, mode: ServiceMode, targetLanguage: string = 'ar') => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('mode', mode);
  // ✅ FIXED: Ensure target_lang is sent correctly to backend
  formData.append('target_lang', targetLanguage);

  try {
    const response = await axios.post<TaskResponse>(`${API_BASE_URL}/upload`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  } catch (error) {
    console.error("Upload Error:", error);
    throw error;
  }
};

export const checkStatus = async (taskId: string) => {
  try {
    const response = await axios.get<TaskResponse>(`${API_BASE_URL}/status/${taskId}`);
    return response.data;
  } catch (error) {
    console.error("Status Check Error:", error);
    throw error;
  }
};

export const startRealProcessing = async (videoUrl: string, mode: ServiceMode, targetLanguage: string = 'ar') => {
  try {
    console.warn("YouTube URL processing via backend is under development.");
    return null;
  } catch (error) {
    console.error("Processing Error:", error);
    throw error;
  }
};

// Export for backwards compatibility
export { API_BASE_URL as BACKEND_URL };
export const checkBackendHealth = async () => {
  try {
    const response = await axios.get(`${API_BASE_URL}/health`);
    return response.status === 200;
  } catch {
    return false;
  }
};
