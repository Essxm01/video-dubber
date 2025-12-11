
// Enums for application state management
export enum ProcessingState {
  IDLE = 'IDLE',
  VALIDATING = 'VALIDATING',
  QUEUED = 'QUEUED',
  PROCESSING = 'PROCESSING',
  COMPLETED = 'COMPLETED',
  FAILED = 'FAILED',
}

export enum ProcessingStage {
  DOWNLOAD = 'DOWNLOAD',
  TRANSCRIPTION = 'TRANSCRIPTION',
  TRANSLATION = 'TRANSLATION',
  VOICE_GENERATION = 'VOICE_GENERATION',
  SUBTITLE_GENERATION = 'SUBTITLE_GENERATION',
  SYNCING = 'SYNCING',
  FINALIZING = 'FINALIZING'
}

export type ServiceMode = 'DUBBING' | 'SUBTITLES' | 'BOTH';

export interface VideoMetadata {
  url: string;
  title?: string;
  thumbnail?: string;
  duration?: string;
  originalLanguage?: string;
  smartSummary?: string;
  mode?: ServiceMode;
}

export interface TaskStatus {
  taskId: string;
  progress: number;
  stage: ProcessingStage;
  message: string;
}

export interface HistoryItem {
  id: string;
  title: string;
  thumbnail: string;
  date: string;
  url: string;
  mode?: ServiceMode;
  smartSummary?: string;
}

export type Language = 'ar' | 'en';
export type Theme = 'light' | 'dark';

// Updated AppView with SETTINGS
export type AppView = 'HOME' | 'AUTH' | 'HOW_IT_WORKS' | 'MY_VIDEOS' | 'FEATURES' | 'FAQ' | 'CONTACT' | 'SETTINGS';

export interface User {
  id: string;
  name: string;
  email: string;
  avatar?: string;
}

// API Response types
export interface ProcessingResult {
  title?: string;
  thumbnail?: string;
  original_text?: string;
  translated_text?: string;
  dubbed_video_url?: string;
  srt_url?: string;
  detected_language?: string;
}
