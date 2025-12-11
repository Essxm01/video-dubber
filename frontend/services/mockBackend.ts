/**
 * Processing Service for Arab Dubbing Platform
 * Handles both mock and real backend processing
 */

import { ProcessingStage, TaskStatus, ServiceMode } from '../types';
import { getStepsForMode } from '../constants';
import { startRealProcessing, USE_MOCK, checkBackendHealth } from './apiService';

/**
 * Helper to get simulation message in Arabic
 */
function getSimulationMessage(stage: ProcessingStage): string {
  switch (stage) {
    case ProcessingStage.DOWNLOAD: return "جاري تحميل الفيديو...";
    case ProcessingStage.TRANSCRIPTION: return "تحليل الصوت واستخراج النص...";
    case ProcessingStage.TRANSLATION: return "ترجمة النص باستخدام الذكاء الاصطناعي...";
    case ProcessingStage.VOICE_GENERATION: return "توليد الدبلجة الصوتية...";
    case ProcessingStage.SUBTITLE_GENERATION: return "تنسيق ملفات الترجمة...";
    case ProcessingStage.SYNCING: return "دمج ومزامنة المحتوى...";
    case ProcessingStage.FINALIZING: return "تحضير الملف النهائي...";
    default: return "جاري المعالجة...";
  }
}

/**
 * Mock processing simulation for development
 */
function simulateMockProcessing(
  mode: ServiceMode,
  onUpdate: (status: TaskStatus) => void,
  onComplete: () => void,
  onError: (msg: string) => void
): () => void {
  const taskId = `task_${Date.now()}`;
  let progress = 0;

  // Dynamically get relevant stages from constants helper
  const stepsDef = getStepsForMode(mode);

  // Map steps definition to simulation config
  const stages = stepsDef.map(step => ({
    stage: step.id,
    duration: step.id === ProcessingStage.VOICE_GENERATION ? 4000 : 2000,
    msg: getSimulationMessage(step.id)
  }));

  let currentStageIndex = 0;

  const interval = setInterval(() => {
    progress += 2;

    const currentStageConfig = stages[currentStageIndex];

    // Check if we need to advance stage
    const stageProgressThreshold = ((currentStageIndex + 1) / stages.length) * 100;

    if (progress > stageProgressThreshold && currentStageIndex < stages.length - 1) {
      currentStageIndex++;
    }

    // Safety cap
    if (progress >= 100) {
      progress = 100;
      clearInterval(interval);
      onUpdate({
        taskId,
        progress: 100,
        stage: ProcessingStage.FINALIZING,
        message: "تمت العملية بنجاح!"
      });
      setTimeout(onComplete, 500);
      return;
    }

    onUpdate({
      taskId,
      progress: Math.min(progress, 99),
      stage: currentStageConfig.stage,
      message: currentStageConfig.msg
    });

  }, 150);

  return () => clearInterval(interval);
}

/**
 * Main processing function - uses real backend or mock based on config
 */
export async function simulateProcessing(
  url: string,
  mode: ServiceMode,
  onUpdate: (status: TaskStatus) => void,
  onComplete: (result?: any) => void,
  onError: (msg: string) => void
): Promise<() => void> {
  // Check if we should use real backend
  if (!USE_MOCK) {
    // Try to connect to real backend
    const isHealthy = await checkBackendHealth();

    if (isHealthy) {
      console.log('✅ Using real backend for processing');
      return startRealProcessing(
        url,
        mode,
        onUpdate,
        onComplete,
        onError
      );
    } else {
      console.warn('⚠️ Backend not available, falling back to mock');
    }
  }

  // Use mock processing
  console.log('🔧 Using mock backend for development');
  return simulateMockProcessing(mode, onUpdate, () => onComplete(), onError);
}

/**
 * Legacy export for backwards compatibility
 * This is the function currently used in App.tsx
 */
export const simulateProcessingLegacy = (
  mode: ServiceMode,
  onUpdate: (status: TaskStatus) => void,
  onComplete: () => void,
  onError: (msg: string) => void
): (() => void) => {
  return simulateMockProcessing(mode, onUpdate, onComplete, onError);
};

// Default export for existing imports
export { simulateMockProcessing as default };
