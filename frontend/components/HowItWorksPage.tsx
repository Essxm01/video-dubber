import React from 'react';
import { Download, FileAudio, Languages, Mic, RefreshCw, ArrowRight } from 'lucide-react';

interface HowItWorksPageProps {
  t: any;
  onBack: () => void;
}

export const HowItWorksPage: React.FC<HowItWorksPageProps> = ({ t, onBack }) => {
  const steps = [
    { icon: <Download className="w-6 h-6" />, title: t.step1Title, desc: t.step1Desc },
    { icon: <FileAudio className="w-6 h-6" />, title: t.step2Title, desc: t.step2Desc },
    { icon: <Mic className="w-6 h-6" />, title: t.step3Title, desc: t.step3Desc },
    { icon: <RefreshCw className="w-6 h-6" />, title: t.step4Title, desc: t.step4Desc },
  ];

  return (
    <div className="w-full max-w-5xl mx-auto py-12 px-4 animate-in fade-in zoom-in duration-500">
      <div className="text-center mb-16">
        <h2 className="text-4xl font-black text-slate-900 dark:text-white mb-4">{t.howTitle}</h2>
        <p className="text-xl text-slate-600 dark:text-slate-400">{t.howDesc}</p>
      </div>

      <div className="relative">
        {/* Connecting Line (Desktop) */}
        <div className="hidden md:block absolute left-1/2 top-0 bottom-0 w-0.5 bg-gradient-to-b from-indigo-500 via-purple-500 to-transparent -translate-x-1/2"></div>

        <div className="space-y-12 md:space-y-24">
          {steps.map((step, idx) => (
            <div key={idx} className={`flex flex-col md:flex-row items-center gap-8 ${idx % 2 !== 0 ? 'md:flex-row-reverse' : ''}`}>
              
              {/* Content Side */}
              <div className={`flex-1 text-center ${idx % 2 !== 0 ? 'md:text-start' : 'md:text-end'}`}>
                <h3 className="text-2xl font-bold text-slate-900 dark:text-white mb-2">{step.title}</h3>
                <p className="text-slate-600 dark:text-slate-400 leading-relaxed">{step.desc}</p>
              </div>

              {/* Icon Center */}
              <div className="relative z-10 flex-shrink-0 w-16 h-16 rounded-2xl bg-gradient-to-br from-indigo-600 to-purple-600 flex items-center justify-center text-white shadow-xl shadow-indigo-500/30 transform hover:scale-110 transition-transform duration-300">
                {step.icon}
              </div>

              {/* Empty Side for balance */}
              <div className="flex-1 hidden md:block"></div>
            </div>
          ))}
        </div>
      </div>

      <div className="text-center mt-20">
        <button 
          onClick={onBack}
          className="inline-flex items-center gap-2 px-8 py-3 bg-white dark:bg-slate-800 text-slate-900 dark:text-white rounded-full font-bold shadow-lg hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors"
        >
          {t.returnHome} <ArrowRight className="w-4 h-4 rtl:rotate-180" />
        </button>
      </div>
    </div>
  );
};