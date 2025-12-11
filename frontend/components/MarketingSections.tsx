
import React from 'react';
import { Mic2, Video, Zap, Globe2, Layers, Cpu, ArrowRight } from 'lucide-react';

interface MarketingSectionsProps {
  t: any;
  onStartClick: () => void;
}

export const MarketingSections: React.FC<MarketingSectionsProps> = ({ t, onStartClick }) => {
  
  const icons = [Zap, Mic2, Video, Globe2, Layers, Cpu];

  return (
    <div className="w-full space-y-24 py-16 animate-in fade-in slide-in-from-bottom-8 duration-700">
      
      {/* Features Grid */}
      <div className="container mx-auto px-4">
        <div className="text-center max-w-3xl mx-auto mb-16">
          <h2 className="text-3xl md:text-5xl font-black text-slate-900 dark:text-white mb-6 leading-tight">
            {t.featuresSectionTitle}
          </h2>
          <p className="text-xl text-slate-600 dark:text-slate-400">
            {t.featuresSectionDesc}
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          {t.featureCards.map((feat: any, idx: number) => {
            const Icon = icons[idx] || Zap;
            return (
              <div key={idx} className="group p-8 rounded-3xl bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 hover:border-indigo-500/50 dark:hover:border-indigo-500/50 transition-all duration-300 hover:shadow-2xl hover:-translate-y-2">
                <div className="w-14 h-14 rounded-2xl bg-indigo-50 dark:bg-indigo-500/10 flex items-center justify-center text-indigo-600 dark:text-indigo-400 mb-6 group-hover:scale-110 transition-transform">
                  <Icon className="w-7 h-7" />
                </div>
                <h3 className="text-xl font-bold text-slate-900 dark:text-white mb-3">
                  {feat.title}
                </h3>
                <p className="text-slate-600 dark:text-slate-400 leading-relaxed">
                  {feat.desc}
                </p>
              </div>
            );
          })}
        </div>
      </div>

      {/* Use Cases - Alternating Layout */}
      <div className="bg-slate-50 dark:bg-slate-800/30 py-20 rounded-[3rem]">
        <div className="container mx-auto px-6">
          <h2 className="text-3xl md:text-4xl font-black text-center text-slate-900 dark:text-white mb-16">
            {t.useCasesTitle}
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
             {t.useCases.map((useCase: any, idx: number) => (
               <div key={idx} className="relative overflow-hidden rounded-3xl bg-white dark:bg-slate-900 p-8 shadow-lg border border-slate-100 dark:border-slate-800">
                  <div className="absolute top-0 right-0 -mt-4 -mr-4 w-24 h-24 bg-gradient-to-br from-indigo-500 to-purple-600 opacity-10 rounded-full blur-xl"></div>
                  <h3 className="text-xl font-bold text-slate-900 dark:text-white mb-4 relative z-10">{useCase.title}</h3>
                  <p className="text-slate-600 dark:text-slate-400 relative z-10">{useCase.desc}</p>
               </div>
             ))}
          </div>
        </div>
      </div>

      {/* CTA Section */}
      <div className="relative rounded-[3rem] overflow-hidden bg-gradient-to-r from-indigo-600 to-violet-700 text-center py-20 px-6 mx-4 md:mx-0 shadow-2xl shadow-indigo-500/30">
        <div className="absolute top-0 left-0 w-full h-full bg-[url('https://www.transparenttextures.com/patterns/cubes.png')] opacity-10"></div>
        <div className="relative z-10 max-w-3xl mx-auto space-y-8">
          <h2 className="text-4xl md:text-5xl font-black text-white leading-tight">
            {t.ctaTitle}
          </h2>
          <p className="text-xl text-indigo-100">
            {t.ctaDesc}
          </p>
          <button 
            onClick={onStartClick}
            className="inline-flex items-center gap-3 bg-white text-indigo-700 px-10 py-5 rounded-full text-xl font-bold hover:bg-indigo-50 hover:scale-105 transition-all shadow-lg"
          >
            {t.ctaBtn}
            <ArrowRight className="w-6 h-6 rtl:rotate-180" />
          </button>
        </div>
      </div>

    </div>
  );
};
