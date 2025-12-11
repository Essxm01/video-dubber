
import React, { useState } from 'react';
import { Mail, Phone, MapPin, Send, CheckCircle2 } from 'lucide-react';
import { Button } from './Button';

interface ContactPageProps {
  t: any;
  onBack: () => void;
}

export const ContactPage: React.FC<ContactPageProps> = ({ t, onBack }) => {
  const [submitted, setSubmitted] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    await new Promise(resolve => setTimeout(resolve, 1500));
    setIsLoading(false);
    setSubmitted(true);
  };

  return (
    <div className="w-full max-w-6xl mx-auto py-12 px-4 animate-in fade-in zoom-in duration-500">
       <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 bg-white dark:bg-slate-800 rounded-[3rem] overflow-hidden shadow-2xl border border-slate-200 dark:border-slate-700">
          
          {/* Info Side */}
          <div className="bg-gradient-to-br from-indigo-600 to-purple-700 p-12 text-white flex flex-col justify-between relative overflow-hidden">
             <div className="absolute top-0 right-0 w-64 h-64 bg-white/10 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2"></div>
             
             <div className="relative z-10">
                <h2 className="text-4xl font-black mb-6">{t.contactTitle}</h2>
                <p className="text-indigo-100 text-lg leading-relaxed mb-12">
                   {t.contactDesc}
                </p>

                <div className="space-y-8">
                   <div className="flex items-start gap-4">
                      <div className="w-12 h-12 rounded-xl bg-white/20 backdrop-blur-sm flex items-center justify-center border border-white/20 flex-shrink-0">
                         <Mail className="w-6 h-6" />
                      </div>
                      <div>
                         <h3 className="font-bold text-lg mb-1">{t.contactEmail}</h3>
                         <p className="text-indigo-100">support@arabdubbing.ai</p>
                      </div>
                   </div>
                   
                   <div className="flex items-start gap-4">
                      <div className="w-12 h-12 rounded-xl bg-white/20 backdrop-blur-sm flex items-center justify-center border border-white/20 flex-shrink-0">
                         <Phone className="w-6 h-6" />
                      </div>
                      <div>
                         <h3 className="font-bold text-lg mb-1">الهاتف</h3>
                         <p className="text-indigo-100">+971 4 123 4567</p>
                      </div>
                   </div>

                   <div className="flex items-start gap-4">
                      <div className="w-12 h-12 rounded-xl bg-white/20 backdrop-blur-sm flex items-center justify-center border border-white/20 flex-shrink-0">
                         <MapPin className="w-6 h-6" />
                      </div>
                      <div>
                         <h3 className="font-bold text-lg mb-1">العنوان</h3>
                         <p className="text-indigo-100">Dubai Internet City, Dubai, UAE</p>
                      </div>
                   </div>
                </div>
             </div>
             
             <div className="relative z-10 mt-12">
                <div className="flex gap-4">
                   <div className="w-10 h-10 rounded-full bg-white/20 hover:bg-white/30 cursor-pointer transition-colors flex items-center justify-center">
                     <span className="font-bold text-sm">FB</span>
                   </div>
                   <div className="w-10 h-10 rounded-full bg-white/20 hover:bg-white/30 cursor-pointer transition-colors flex items-center justify-center">
                     <span className="font-bold text-sm">TW</span>
                   </div>
                   <div className="w-10 h-10 rounded-full bg-white/20 hover:bg-white/30 cursor-pointer transition-colors flex items-center justify-center">
                     <span className="font-bold text-sm">IG</span>
                   </div>
                </div>
             </div>
          </div>

          {/* Form Side */}
          <div className="p-12 flex flex-col justify-center">
             {submitted ? (
                <div className="text-center py-12">
                   <div className="w-20 h-20 bg-green-100 dark:bg-green-500/20 text-green-600 dark:text-green-400 rounded-full flex items-center justify-center mx-auto mb-6">
                      <CheckCircle2 className="w-10 h-10" />
                   </div>
                   <h3 className="text-2xl font-bold text-slate-900 dark:text-white mb-2">{t.contactSuccess}</h3>
                   <p className="text-slate-500 mb-8">Thank you for reaching out. We will get back to you shortly.</p>
                   <Button onClick={onBack} variant="outline">{t.returnHome}</Button>
                </div>
             ) : (
                <form onSubmit={handleSubmit} className="space-y-6">
                   <div className="space-y-2">
                      <label className="text-sm font-bold text-slate-900 dark:text-white uppercase">{t.contactName}</label>
                      <input 
                        type="text" 
                        required
                        className="w-full px-4 py-3 rounded-xl bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 focus:ring-2 focus:ring-indigo-500 outline-none transition-all dark:text-white"
                        placeholder={t.contactName}
                      />
                   </div>
                   <div className="space-y-2">
                      <label className="text-sm font-bold text-slate-900 dark:text-white uppercase">{t.contactEmail}</label>
                      <input 
                        type="email" 
                        required
                        className="w-full px-4 py-3 rounded-xl bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 focus:ring-2 focus:ring-indigo-500 outline-none transition-all dark:text-white"
                        placeholder="email@example.com"
                      />
                   </div>
                   <div className="space-y-2">
                      <label className="text-sm font-bold text-slate-900 dark:text-white uppercase">{t.contactMsg}</label>
                      <textarea 
                        required
                        rows={4}
                        className="w-full px-4 py-3 rounded-xl bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 focus:ring-2 focus:ring-indigo-500 outline-none transition-all dark:text-white resize-none"
                        placeholder="..."
                      />
                   </div>
                   
                   <Button type="submit" className="w-full h-14 text-lg" isLoading={isLoading} icon={<Send className="w-5 h-5" />}>
                      {t.contactSubmit}
                   </Button>
                </form>
             )}
          </div>

       </div>
    </div>
  );
};
