import React from 'react';
import { CheckCircle2, Circle, Download, FileAudio, Languages, Mic, RefreshCw, Loader2 } from 'lucide-react';
import { ProcessingStage } from '../types';
import { STEPS } from '../constants';

interface StageStepperProps {
  currentStage: ProcessingStage;
  t: any;
}

const getIcon = (id: string, active: boolean, completed: boolean) => {
  const className = `w-5 h-5 ${active ? 'animate-pulse' : ''}`;
  switch (id) {
    case ProcessingStage.DOWNLOAD: return <Download className={className} />;
    case ProcessingStage.TRANSCRIPTION: return <FileAudio className={className} />;
    case ProcessingStage.TRANSLATION: return <Languages className={className} />;
    case ProcessingStage.VOICE_GENERATION: return <Mic className={className} />;
    case ProcessingStage.SYNCING: return <RefreshCw className={className} />;
    default: return <Circle className={className} />;
  }
};

export const StageStepper: React.FC<StageStepperProps> = ({ currentStage, t }) => {
  const currentStepIndex = STEPS.findIndex(s => s.id === currentStage);

  return (
    <div className="w-full max-w-2xl mx-auto py-8">
      <div className="relative flex justify-between" dir="ltr">
        {STEPS.map((step, index) => {
          const isCompleted = index < currentStepIndex;
          const isCurrent = index === currentStepIndex;
          const isPending = index > currentStepIndex;

          return (
            <div key={step.id} className="flex flex-col items-center relative z-10 w-24 group">
              <div 
                className={`
                  w-12 h-12 rounded-full flex items-center justify-center border-2 transition-all duration-300
                  ${isCompleted ? 'bg-green-500 border-green-500 text-white' : ''}
                  ${isCurrent ? 'bg-indigo-600 border-indigo-500 text-white shadow-[0_0_15px_rgba(79,70,229,0.5)] scale-110' : ''}
                  ${isPending ? 'bg-slate-100 dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-400 dark:text-slate-500' : ''}
                `}
              >
                {isCompleted ? <CheckCircle2 className="w-6 h-6" /> : 
                 isCurrent ? <Loader2 className="w-6 h-6 animate-spin" /> : 
                 getIcon(step.id, false, false)}
              </div>
              <span 
                className={`
                  mt-3 text-xs font-medium text-center absolute top-14 w-32
                  ${isCurrent ? 'text-indigo-600 dark:text-indigo-400 font-bold' : 'text-slate-500 dark:text-slate-500'}
                `}
              >
                {t[step.label] || step.label}
              </span>
            </div>
          );
        })}
        
        {/* Progress Line Background */}
        <div className="absolute top-6 left-0 right-0 h-0.5 bg-slate-200 dark:bg-slate-800 -z-0 mx-8"></div>
        
        {/* Active Progress Line */}
        <div 
          className="absolute top-6 left-0 h-0.5 bg-indigo-500 -z-0 mx-8 transition-all duration-500 ease-out"
          style={{ width: `${(currentStepIndex / (STEPS.length - 1)) * 100}%` }}
        ></div>
      </div>
    </div>
  );
};