import React from 'react';
import { Check, Star, Zap, Shield } from 'lucide-react';
import { Button } from './Button';

interface PricingPageProps {
  t: any;
  onBack: () => void;
}

export const PricingPage: React.FC<PricingPageProps> = ({ t, onBack }) => {
  const plans = [
    {
      name: t.planFree,
      price: "0",
      icon: <Star className="w-6 h-6 text-slate-400" />,
      features: t.features_free,
      recommended: false
    },
    {
      name: t.planPro,
      price: "29",
      icon: <Zap className="w-6 h-6 text-indigo-500" />,
      features: t.features_pro,
      recommended: true
    },
    {
      name: t.planBusiness,
      price: "99",
      icon: <Shield className="w-6 h-6 text-purple-500" />,
      features: t.features_biz,
      recommended: false
    }
  ];

  return (
    <div className="w-full max-w-6xl mx-auto py-12 px-4 animate-in fade-in slide-in-from-bottom-8 duration-500">
      <div className="text-center mb-16 space-y-4">
        <h2 className="text-4xl font-black text-slate-900 dark:text-white">{t.pricingTitle}</h2>
        <p className="text-xl text-slate-600 dark:text-slate-400 max-w-2xl mx-auto">{t.pricingDesc}</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
        {plans.map((plan, idx) => (
          <div 
            key={idx} 
            className={`
              relative bg-white dark:bg-slate-800 rounded-2xl p-8 border transition-all duration-300 hover:shadow-2xl hover:-translate-y-2
              ${plan.recommended 
                ? 'border-indigo-500 shadow-xl shadow-indigo-500/10 dark:shadow-indigo-900/20 ring-1 ring-indigo-500' 
                : 'border-slate-200 dark:border-slate-700 shadow-lg'}
            `}
          >
            {plan.recommended && (
              <div className="absolute -top-4 left-1/2 -translate-x-1/2 bg-indigo-600 text-white text-xs font-bold px-3 py-1 rounded-full uppercase tracking-wider">
                Recommended
              </div>
            )}

            <div className="flex items-center justify-between mb-8">
              <div className="p-3 bg-slate-50 dark:bg-slate-700/50 rounded-xl">
                {plan.icon}
              </div>
              <div>
                <span className="text-3xl font-black text-slate-900 dark:text-white">${plan.price}</span>
                <span className="text-slate-500 dark:text-slate-400">/{t.month}</span>
              </div>
            </div>

            <h3 className="text-xl font-bold text-slate-900 dark:text-white mb-6">{plan.name}</h3>

            <ul className="space-y-4 mb-8">
              {plan.features.map((feat: string, i: number) => (
                <li key={i} className="flex items-center text-slate-600 dark:text-slate-300">
                  <Check className="w-5 h-5 text-green-500 ltr:mr-3 rtl:ml-3 flex-shrink-0" />
                  <span className="text-sm font-medium">{feat}</span>
                </li>
              ))}
            </ul>

            <Button 
              variant={plan.recommended ? 'primary' : 'secondary'} 
              className="w-full"
              onClick={onBack}
            >
              {t.selectPlan}
            </Button>
          </div>
        ))}
      </div>
      
      <div className="text-center mt-12">
        <button onClick={onBack} className="text-slate-500 hover:text-indigo-600 dark:hover:text-indigo-400 font-medium transition-colors">
          {t.returnHome}
        </button>
      </div>
    </div>
  );
};