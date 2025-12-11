
import React, { useState } from 'react';
import { ChevronDown, HelpCircle, ArrowRight } from 'lucide-react';
import { Button } from './Button';

interface FAQPageProps {
  t: any;
  onBack: () => void;
}

export const FAQPage: React.FC<FAQPageProps> = ({ t, onBack }) => {
  const [openIndex, setOpenIndex] = useState<number | null>(0);

  const toggleAccordion = (index: number) => {
    setOpenIndex(openIndex === index ? null : index);
  };

  return (
    <div className="w-full max-w-4xl mx-auto py-12 px-4 animate-in fade-in zoom-in duration-500">
      <div className="text-center mb-16">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 mb-6">
            <HelpCircle className="w-8 h-8" />
        </div>
        <h2 className="text-4xl font-black text-slate-900 dark:text-white mb-4">{t.faqTitle}</h2>
        <p className="text-xl text-slate-600 dark:text-slate-400">{t.faqDesc}</p>
      </div>

      <div className="space-y-4">
        {t.faqItems.map((item: any, idx: number) => (
          <div 
            key={idx} 
            className={`
                bg-white dark:bg-slate-800 rounded-2xl border transition-all duration-300 overflow-hidden
                ${openIndex === idx ? 'border-indigo-500 ring-1 ring-indigo-500 shadow-lg' : 'border-slate-200 dark:border-slate-700 hover:border-indigo-300'}
            `}
          >
            <button
              onClick={() => toggleAccordion(idx)}
              className="w-full flex items-center justify-between p-6 text-start focus:outline-none"
            >
              <span className={`text-lg font-bold transition-colors ${openIndex === idx ? 'text-indigo-600 dark:text-indigo-400' : 'text-slate-900 dark:text-white'}`}>
                {item.q}
              </span>
              <ChevronDown 
                className={`w-5 h-5 text-slate-400 transition-transform duration-300 ${openIndex === idx ? 'rotate-180 text-indigo-500' : ''}`} 
              />
            </button>
            <div 
                className={`transition-all duration-300 ease-in-out overflow-hidden ${openIndex === idx ? 'max-h-48 opacity-100' : 'max-h-0 opacity-0'}`}
            >
              <div className="p-6 pt-0 text-slate-600 dark:text-slate-300 leading-relaxed border-t border-slate-100 dark:border-slate-700/50 mt-2 pt-4">
                {item.a}
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="text-center mt-12 bg-slate-50 dark:bg-slate-800/50 p-8 rounded-3xl border border-dashed border-slate-300 dark:border-slate-700">
        <h3 className="text-xl font-bold text-slate-900 dark:text-white mb-2">{t.ctaTitle}</h3>
        <p className="text-slate-600 dark:text-slate-400 mb-6">{t.ctaDesc}</p>
        <Button onClick={onBack}>
          {t.startBtn} <ArrowRight className="w-4 h-4 rtl:rotate-180 ltr:ml-2 rtl:mr-2" />
        </Button>
      </div>
    </div>
  );
};
