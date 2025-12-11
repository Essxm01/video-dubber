
import React from 'react';
import { Play, Calendar, FileText, Mic, Layers, ArrowRight } from 'lucide-react';
import { HistoryItem, ServiceMode } from '../types';
import { Button } from './Button';

interface MyVideosPageProps {
  history: HistoryItem[];
  t: any;
  onPlay: (item: HistoryItem) => void;
  onBack: () => void;
}

export const MyVideosPage: React.FC<MyVideosPageProps> = ({ history, t, onPlay, onBack }) => {
  const getModeIcon = (mode?: ServiceMode) => {
    switch (mode) {
      case 'DUBBING': return <Mic className="w-4 h-4" />;
      case 'SUBTITLES': return <FileText className="w-4 h-4" />;
      case 'BOTH': return <Layers className="w-4 h-4" />;
      default: return <Mic className="w-4 h-4" />;
    }
  };

  const getModeLabel = (mode?: ServiceMode) => {
    switch (mode) {
      case 'DUBBING': return t.modeDubbing;
      case 'SUBTITLES': return t.modeSubtitles;
      case 'BOTH': return t.modeBoth;
      default: return t.modeDubbing;
    }
  };

  return (
    <div className="w-full max-w-6xl mx-auto py-12 px-4 animate-in fade-in slide-in-from-bottom-8 duration-500">
      <div className="flex items-center justify-between mb-8">
        <h2 className="text-3xl font-black text-slate-900 dark:text-white">{t.myVideosTitle}</h2>
        <Button onClick={onBack} variant="secondary" className="hidden md:flex">
          {t.returnHome}
        </Button>
      </div>

      {history.length === 0 ? (
        <div className="text-center py-20 bg-slate-50 dark:bg-slate-800/50 rounded-3xl border border-dashed border-slate-300 dark:border-slate-700">
          <div className="w-20 h-20 bg-slate-100 dark:bg-slate-700 rounded-full flex items-center justify-center mx-auto mb-4">
             <Play className="w-8 h-8 text-slate-400" />
          </div>
          <h3 className="text-xl font-bold text-slate-700 dark:text-slate-300 mb-2">{t.noVideos}</h3>
          <p className="text-slate-500 dark:text-slate-500 mb-6">{t.noVideosDesc}</p>
          <Button onClick={onBack}>{t.startBtn}</Button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {history.map((item) => (
            <div key={item.id} className="group bg-white dark:bg-slate-800 rounded-2xl overflow-hidden border border-slate-200 dark:border-slate-700 hover:shadow-xl transition-all duration-300 hover:-translate-y-1">
              <div className="relative aspect-video bg-slate-900 overflow-hidden">
                <img src={item.thumbnail} alt={item.title} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-700" />
                <div className="absolute inset-0 bg-black/20 group-hover:bg-black/10 transition-colors"></div>
                
                <button 
                  onClick={() => onPlay(item)}
                  className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity duration-300"
                >
                  <div className="w-14 h-14 bg-white/30 backdrop-blur-md rounded-full flex items-center justify-center border border-white/50 shadow-lg">
                    <Play className="w-6 h-6 text-white fill-white ml-1" />
                  </div>
                </button>

                <div className="absolute top-3 right-3 bg-black/60 backdrop-blur-sm text-white text-xs font-bold px-2 py-1 rounded flex items-center gap-1">
                   {getModeIcon(item.mode)}
                   <span>{getModeLabel(item.mode)}</span>
                </div>
              </div>

              <div className="p-5">
                <h3 className="text-lg font-bold text-slate-900 dark:text-white line-clamp-2 mb-2 leading-tight">
                  {item.title}
                </h3>
                <div className="flex items-center text-sm text-slate-500 dark:text-slate-400 mb-4">
                  <Calendar className="w-4 h-4 rtl:ml-1 ltr:mr-1" />
                  <span>{item.date}</span>
                </div>
                
                <Button onClick={() => onPlay(item)} variant="outline" className="w-full text-sm py-2">
                  {t.watchBtn}
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}
      
      <div className="md:hidden mt-8 text-center">
         <Button onClick={onBack} variant="secondary">
          {t.returnHome}
        </Button>
      </div>
    </div>
  );
};
