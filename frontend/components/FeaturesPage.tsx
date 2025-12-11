
import React from 'react';
import { Zap, Mic2, Video, Globe2, Layers, Cpu, CheckCircle2, ArrowRight } from 'lucide-react';
import { Button } from './Button';

interface FeaturesPageProps {
  t: any;
  onBack: () => void;
}

export const FeaturesPage: React.FC<FeaturesPageProps> = ({ t, onBack }) => {
  const icons = [Zap, Mic2, Video, Globe2, Layers, Cpu];

  return (
    <div className="w-full max-w-6xl mx-auto py-12 px-4 animate-in fade-in zoom-in duration-500">
      <div className="text-center mb-16 space-y-4">
        <h2 className="text-4xl font-black text-slate-900 dark:text-white">{t.featuresSectionTitle}</h2>
        <p className="text-xl text-slate-600 dark:text-slate-400 max-w-2xl mx-auto">{t.featuresSectionDesc}</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8 mb-20">
        {t.featureCards.map((feat: any, idx: number) => {
          const Icon = icons[idx] || Zap;
          return (
            <div key={idx} className="group p-8 rounded-3xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 hover:border-indigo-500 dark:hover:border-indigo-500 transition-all duration-300 hover:shadow-2xl hover:-translate-y-2">
              <div className="w-16 h-16 rounded-2xl bg-indigo-50 dark:bg-indigo-500/10 flex items-center justify-center text-indigo-600 dark:text-indigo-400 mb-6 group-hover:scale-110 transition-transform">
                <Icon className="w-8 h-8" />
              </div>
              <h3 className="text-2xl font-bold text-slate-900 dark:text-white mb-4">
                {feat.title}
              </h3>
              <p className="text-slate-600 dark:text-slate-400 leading-relaxed text-lg">
                {feat.desc}
              </p>
            </div>
          );
        })}
      </div>

      {/* Additional Visual Section */}
      <div className="bg-slate-50 dark:bg-slate-800/50 rounded-[3rem] p-12 mb-16 border border-slate-200 dark:border-slate-700">
         <div className="flex flex-col md:flex-row items-center gap-12">
            <div className="flex-1 space-y-8">
               <h3 className="text-3xl font-black text-slate-900 dark:text-white leading-tight">
                  {t.heroTitle} <span className="text-indigo-600 dark:text-indigo-400">{t.heroHighlight}</span>
               </h3>
               <div className="space-y-4">
                 <div className="flex items-start gap-4">
                    <CheckCircle2 className="w-6 h-6 text-green-500 flex-shrink-0 mt-1" />
                    <div>
                        <h4 className="font-bold text-slate-900 dark:text-white text-lg">{t.modeDubbing}</h4>
                        <p className="text-slate-600 dark:text-slate-400">{t.modeDubbingDesc}</p>
                    </div>
                 </div>
                 <div className="flex items-start gap-4">
                    <CheckCircle2 className="w-6 h-6 text-green-500 flex-shrink-0 mt-1" />
                    <div>
                        <h4 className="font-bold text-slate-900 dark:text-white text-lg">{t.modeSubtitles}</h4>
                        <p className="text-slate-600 dark:text-slate-400">{t.modeSubtitlesDesc}</p>
                    </div>
                 </div>
               </div>
            </div>
            <div className="flex-1 w-full relative">
                <div className="absolute inset-0 bg-gradient-to-r from-indigo-500 to-purple-600 blur-3xl opacity-20 rounded-full"></div>
                <div className="relative bg-white dark:bg-slate-900 rounded-2xl p-6 shadow-2xl border border-slate-200 dark:border-slate-700">
                    <div className="flex items-center gap-4 mb-4 border-b border-slate-100 dark:border-slate-800 pb-4">
                        <div className="w-10 h-10 rounded-full bg-slate-200 dark:bg-slate-700"></div>
                        <div className="space-y-2">
                           <div className="w-32 h-3 bg-slate-200 dark:bg-slate-700 rounded"></div>
                           <div className="w-20 h-2 bg-slate-200 dark:bg-slate-700 rounded"></div>
                        </div>
                    </div>
                    <div className="space-y-3">
                        <div className="w-full h-24 bg-slate-100 dark:bg-slate-800 rounded-lg"></div>
                        <div className="w-3/4 h-3 bg-slate-200 dark:bg-slate-700 rounded"></div>
                        <div className="w-1/2 h-3 bg-slate-200 dark:bg-slate-700 rounded"></div>
                    </div>
                </div>
            </div>
         </div>
      </div>

      <div className="text-center">
        <Button onClick={onBack} className="h-14 px-8 text-lg">
           {t.startBtn} <ArrowRight className="w-5 h-5 rtl:mr-2 ltr:ml-2 rtl:rotate-180" />
        </Button>
      </div>
    </div>
  );
};
