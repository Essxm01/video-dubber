
import React, { useState } from 'react';
import { Globe, Menu, X, Sun, Moon, LogIn, User as UserIcon } from 'lucide-react';
import { Language, Theme, User, AppView } from '../types';

interface HeaderProps {
  lang: Language;
  theme: Theme;
  user: User | null;
  t: any;
  onToggleLang: () => void;
  onToggleTheme: () => void;
  onLoginClick: () => void;
  onLogoutClick: () => void;
  onNavigate: (view: AppView) => void;
}

export const Header: React.FC<HeaderProps> = ({ 
  lang, 
  theme, 
  user,
  t, 
  onToggleLang, 
  onToggleTheme,
  onLoginClick,
  onLogoutClick,
  onNavigate
}) => {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  const handleMobileNavigate = (view: AppView) => {
    onNavigate(view);
    setIsMobileMenuOpen(false);
  };

  return (
    <header className="sticky top-0 z-50 w-full border-b border-slate-200 dark:border-slate-800 bg-white/90 dark:bg-[#0f172a]/90 backdrop-blur-lg transition-all duration-300 shadow-sm h-24">
      <div className="container mx-auto px-6 h-full flex items-center justify-between">
        
        {/* Logo Section */}
        <div 
          className="flex items-center cursor-pointer hover:opacity-80 transition-opacity flex-shrink-0 gap-3" 
          onClick={() => onNavigate('HOME')}
        >
          <img 
            src="https://raw.githubusercontent.com/Essxm01/Arab-Dubbing-Logo/496d4bc9e8684020c3aa2663f50bc442b9eacc13/Vector.svg" 
            alt="Arab Dubbing Logo" 
            className="w-12 h-12 object-contain rtl:ml-2 ltr:mr-2"
          />
          <span className="text-2xl font-black bg-clip-text text-transparent bg-gradient-to-r from-slate-900 to-slate-600 dark:from-white dark:to-slate-400 tracking-tight">
            {t.appTitle}
          </span>
        </div>

        {/* Desktop Nav - Visible on Large Screens (lg+) */}
        <nav className="hidden lg:flex flex-1 items-center justify-center">
          <button 
            onClick={() => onNavigate('HOME')} 
            className="mx-1 px-4 py-2 text-base font-bold text-slate-600 dark:text-slate-300 hover:text-indigo-600 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-all"
          >
            {t.home}
          </button>
          
          <button 
            onClick={() => onNavigate('FEATURES')} 
            className="mx-1 px-4 py-2 text-base font-bold text-slate-600 dark:text-slate-300 hover:text-indigo-600 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-all"
          >
            {t.featuresNav}
          </button>

          <button 
            onClick={() => onNavigate('HOW_IT_WORKS')} 
            className="mx-1 px-4 py-2 text-base font-bold text-slate-600 dark:text-slate-300 hover:text-indigo-600 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-all"
          >
            {t.howItWorks}
          </button>

          <button 
            onClick={() => onNavigate('FAQ')} 
            className="mx-1 px-4 py-2 text-base font-bold text-slate-600 dark:text-slate-300 hover:text-indigo-600 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-all"
          >
            {t.faqNav}
          </button>

          <button 
            onClick={() => onNavigate('CONTACT')} 
            className="mx-1 px-4 py-2 text-base font-bold text-slate-600 dark:text-slate-300 hover:text-indigo-600 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-all"
          >
            {t.contactNav}
          </button>
          
          {user && (
            <button 
              onClick={() => onNavigate('MY_VIDEOS')} 
              className="mx-1 px-4 py-2 text-base font-bold text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-900/20 hover:bg-indigo-100 rounded-lg transition-all"
            >
              {t.myVideosTitle}
            </button>
          )}
        </nav>

        {/* Actions Section */}
        <div className="flex items-center flex-shrink-0 gap-4">
          
          {/* Theme Toggle */}
          <button 
            onClick={onToggleTheme}
            className="w-10 h-10 flex items-center justify-center text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800 rounded-full transition-colors hidden sm:flex"
            title={theme === 'light' ? 'Switch to Dark Mode' : 'Switch to Light Mode'}
          >
            {theme === 'light' ? <Moon className="w-5 h-5" /> : <Sun className="w-5 h-5" />}
          </button>

          {/* Lang Toggle */}
          <button 
            onClick={onToggleLang}
            className="flex items-center justify-center h-10 px-3 text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800 rounded-full transition-colors"
            title="Switch Language"
          >
            <Globe className="w-5 h-5 rtl:ml-2 ltr:mr-2" />
            <span className="text-xs font-bold uppercase pt-0.5">{lang === 'ar' ? 'EN' : 'عربي'}</span>
          </button>

          {/* User / Login */}
          <div className="hidden sm:block rtl:mr-2 ltr:ml-2 border-l rtl:border-r rtl:border-l-0 border-slate-200 dark:border-slate-700 h-8 mx-2"></div>

          {user ? (
            <div className="flex items-center rtl:mr-2 ltr:ml-2">
              <span className="hidden md:block text-sm font-medium text-slate-700 dark:text-slate-200 rtl:ml-3 ltr:mr-3">
                {user.name}
              </span>
              <button 
                onClick={onLogoutClick}
                className="hidden md:inline-flex px-4 py-1.5 text-sm font-semibold text-red-500 bg-red-50 dark:bg-red-900/20 rounded-full hover:bg-red-100 dark:hover:bg-red-900/40 transition-colors rtl:ml-2 ltr:mr-2"
              >
                {t.logout}
              </button>
              <div className="w-10 h-10 rounded-full bg-indigo-100 dark:bg-indigo-900 flex items-center justify-center text-indigo-700 dark:text-indigo-300 font-bold border border-indigo-200 dark:border-indigo-700">
                {user.name.charAt(0)}
              </div>
            </div>
          ) : (
             <button 
              onClick={onLoginClick}
              className="hidden sm:inline-flex items-center gap-2 px-6 py-2.5 text-sm font-bold text-white bg-slate-900 dark:bg-white dark:text-slate-900 rounded-full hover:bg-slate-800 dark:hover:bg-slate-200 transition-all shadow-md hover:shadow-lg transform hover:-translate-y-0.5"
             >
               <LogIn className="w-4 h-4" />
               {t.login}
             </button>
          )}

          {/* Mobile Menu Button */}
          <button 
            onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
            className="lg:hidden p-2 text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors"
          >
            {isMobileMenuOpen ? <X className="w-7 h-7" /> : <Menu className="w-7 h-7" />}
          </button>
        </div>
      </div>

      {/* Mobile Menu Dropdown */}
      {isMobileMenuOpen && (
        <div className="lg:hidden absolute top-24 left-0 right-0 bg-white dark:bg-[#0f172a] border-b border-slate-200 dark:border-slate-800 shadow-xl animate-in slide-in-from-top-4 duration-300">
          <div className="flex flex-col p-4 space-y-2">
            <button 
              onClick={() => handleMobileNavigate('HOME')} 
              className="px-4 py-3 text-start font-bold text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 rounded-xl"
            >
              {t.home}
            </button>
            <button 
              onClick={() => handleMobileNavigate('FEATURES')} 
              className="px-4 py-3 text-start font-bold text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 rounded-xl"
            >
              {t.featuresNav}
            </button>
            <button 
              onClick={() => handleMobileNavigate('HOW_IT_WORKS')} 
              className="px-4 py-3 text-start font-bold text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 rounded-xl"
            >
              {t.howItWorks}
            </button>
            <button 
              onClick={() => handleMobileNavigate('FAQ')} 
              className="px-4 py-3 text-start font-bold text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 rounded-xl"
            >
              {t.faqNav}
            </button>
            <button 
              onClick={() => handleMobileNavigate('CONTACT')} 
              className="px-4 py-3 text-start font-bold text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 rounded-xl"
            >
              {t.contactNav}
            </button>
            
            {user && (
               <button 
                onClick={() => handleMobileNavigate('MY_VIDEOS')} 
                className="px-4 py-3 text-start font-bold text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-900/20 rounded-xl"
              >
                {t.myVideosTitle}
              </button>
            )}

            <div className="border-t border-slate-100 dark:border-slate-800 my-2"></div>
            
            <div className="flex items-center justify-between px-4 py-2">
               <span className="text-sm font-medium text-slate-500">{t.appTitle}</span>
               <div className="flex gap-2">
                 <button onClick={onToggleTheme} className="p-2 bg-slate-100 dark:bg-slate-800 rounded-lg">
                    {theme === 'light' ? <Moon className="w-5 h-5" /> : <Sun className="w-5 h-5" />}
                 </button>
               </div>
            </div>

            {!user && (
              <button 
                onClick={() => { onLoginClick(); setIsMobileMenuOpen(false); }}
                className="w-full mt-2 py-3 bg-slate-900 dark:bg-white text-white dark:text-slate-900 font-bold rounded-xl"
              >
                {t.login}
              </button>
            )}
             {user && (
              <button 
                onClick={() => { onLogoutClick(); setIsMobileMenuOpen(false); }}
                className="w-full mt-2 py-3 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 font-bold rounded-xl"
              >
                {t.logout}
              </button>
            )}
          </div>
        </div>
      )}
    </header>
  );
};
