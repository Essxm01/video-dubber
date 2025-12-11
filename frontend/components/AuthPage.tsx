import React, { useState } from 'react';
import { PlayCircle, Chrome, Mail, Lock, User, ArrowLeft, ArrowRight, CheckCircle2, Loader2 } from 'lucide-react';
import { Button } from './Button';
import { useAuth } from '../contexts/AuthContext';
import { useToast } from './ToastContext';

interface AuthPageProps {
  onLoginSuccess: () => void;
  onBack: () => void;
  t: any;
}

export const AuthPage: React.FC<AuthPageProps> = ({ onLoginSuccess, onBack, t }) => {
  const [isLogin, setIsLogin] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [formData, setFormData] = useState({ name: '', email: '', password: '' });

  const { signInWithGoogle, signInWithEmail, signUpWithEmail } = useAuth();
  const { showSuccess, showError } = useToast();

  /**
   * معالجة تقديم النموذج
   */
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // التحقق من البيانات
    if (!formData.email || !formData.password) {
      showError('الرجاء إدخال البريد الإلكتروني وكلمة المرور');
      return;
    }

    if (!isLogin && !formData.name) {
      showError('الرجاء إدخال الاسم');
      return;
    }

    setIsLoading(true);

    try {
      if (isLogin) {
        // تسجيل الدخول
        const result = await signInWithEmail(formData.email, formData.password);
        if (result.success) {
          showSuccess('مرحباً بعودتك! 👋');
          onLoginSuccess();
        } else {
          showError(result.error || 'فشل تسجيل الدخول. تحقق من البيانات.');
        }
      } else {
        // إنشاء حساب
        const result = await signUpWithEmail(formData.email, formData.password, formData.name);
        if (result.success) {
          showSuccess('تم إنشاء حسابك بنجاح! 🎉');
          onLoginSuccess();
        } else {
          showError(result.error || 'فشل إنشاء الحساب. قد يكون البريد مستخدم.');
        }
      }
    } catch (error: any) {
      showError(error.message || 'حدث خطأ غير متوقع');
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * تسجيل الدخول بـ Google
   */
  const handleGoogleLogin = () => {
    setIsLoading(true);
    signInWithGoogle();
    // ملاحظة: سيتم إعادة التوجيه لـ Google
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  return (
    <div className="flex flex-col items-center justify-center animate-in fade-in zoom-in duration-300 py-6 w-full px-4">

      {/* Main Container - Split Layout */}
      <div className="bg-white dark:bg-slate-800 rounded-[2rem] border border-slate-200 dark:border-slate-700 shadow-2xl w-full max-w-5xl overflow-hidden grid grid-cols-1 md:grid-cols-2 min-h-[650px]">

        {/* Left Side - Branding */}
        <div className="hidden md:flex flex-col justify-between bg-gradient-to-br from-indigo-600 to-violet-800 p-12 text-white relative overflow-hidden">
          {/* Abstract Shapes */}
          <div className="absolute top-0 left-0 w-64 h-64 bg-white/10 rounded-full blur-3xl -translate-x-1/2 -translate-y-1/2"></div>
          <div className="absolute bottom-0 right-0 w-80 h-80 bg-purple-500/20 rounded-full blur-3xl translate-x-1/3 translate-y-1/3"></div>

          <div className="relative z-10">
            <div className="w-14 h-14 rounded-2xl bg-white/20 backdrop-blur-sm flex items-center justify-center border border-white/30 mb-8">
              <PlayCircle className="text-white w-8 h-8" />
            </div>
            <h1 className="text-4xl font-black mb-6 leading-tight">
              {t.heroTitle} <br />
              <span className="text-indigo-200">{t.heroHighlight}</span>
            </h1>
            <p className="text-indigo-100 text-lg leading-relaxed max-w-sm">
              {t.heroDesc}
            </p>
          </div>

          <div className="relative z-10 space-y-4">
            {t.features.slice(0, 3).map((feat: string, idx: number) => (
              <div key={idx} className="flex items-center gap-3 text-indigo-50 font-medium bg-white/10 p-3 rounded-xl backdrop-blur-sm border border-white/10">
                <CheckCircle2 className="w-5 h-5 text-indigo-300" />
                <span>{feat}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Right Side - Form */}
        <div className="p-8 md:p-12 lg:p-16 flex flex-col justify-center bg-white dark:bg-slate-800 h-full">

          <div className="text-start mb-8">
            <h2 className="text-3xl font-black text-slate-900 dark:text-white mb-2">
              {isLogin ? t.welcomeBack : t.createAccountTitle}
            </h2>
            <p className="text-slate-500 dark:text-slate-400 text-base">
              {isLogin ? t.loginDesc : t.createAccountDesc}
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            {!isLogin && (
              <div className="space-y-1.5">
                <label className="text-xs font-bold text-slate-600 dark:text-slate-300 uppercase tracking-wide px-1">{t.nameLabel}</label>
                <div className="relative">
                  <User className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400 rtl:right-4 rtl:left-auto" />
                  <input
                    name="name"
                    type="text"
                    required={!isLogin}
                    className="w-full pl-12 rtl:pr-12 rtl:pl-4 py-3.5 bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none transition-all dark:text-white text-lg"
                    placeholder={t.nameLabel}
                    value={formData.name}
                    onChange={handleChange}
                  />
                </div>
              </div>
            )}

            <div className="space-y-1.5">
              <label className="text-xs font-bold text-slate-600 dark:text-slate-300 uppercase tracking-wide px-1">{t.emailLabel}</label>
              <div className="relative">
                <Mail className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400 rtl:right-4 rtl:left-auto" />
                <input
                  name="email"
                  type="email"
                  required
                  className="w-full pl-12 rtl:pr-12 rtl:pl-4 py-3.5 bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none transition-all dark:text-white text-lg"
                  placeholder="name@example.com"
                  value={formData.email}
                  onChange={handleChange}
                  dir="ltr"
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-bold text-slate-600 dark:text-slate-300 uppercase tracking-wide px-1">{t.passwordLabel}</label>
              <div className="relative">
                <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400 rtl:right-4 rtl:left-auto" />
                <input
                  name="password"
                  type="password"
                  required
                  minLength={6}
                  className="w-full pl-12 rtl:pr-12 rtl:pl-4 py-3.5 bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none transition-all dark:text-white text-lg"
                  placeholder="••••••••"
                  value={formData.password}
                  onChange={handleChange}
                  dir="ltr"
                />
              </div>
            </div>

            <Button
              type="submit"
              className="w-full mt-4 text-lg py-4 shadow-xl shadow-indigo-500/20"
              isLoading={isLoading}
              disabled={isLoading}
            >
              {isLoading ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                isLogin ? t.submitLogin : t.submitSignUp
              )}
            </Button>
          </form>

          <div className="relative my-8">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-slate-200 dark:border-slate-700"></div>
            </div>
            <div className="relative flex justify-center text-sm uppercase">
              <span className="bg-white dark:bg-slate-800 px-3 text-slate-500 font-medium">{t.orDivider}</span>
            </div>
          </div>

          {/* Google OAuth Button */}
          <button
            onClick={handleGoogleLogin}
            disabled={isLoading}
            className="flex items-center justify-center gap-3 w-full px-6 py-4 rounded-xl border-2 border-slate-200 dark:border-slate-600 hover:bg-slate-50 dark:hover:bg-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-white font-bold transition-all duration-200 hover:shadow-lg hover:border-indigo-300 disabled:opacity-50"
          >
            <Chrome className="w-6 h-6 text-red-500" />
            <span>المتابعة مع Google</span>
          </button>

          <div className="mt-8 text-center">
            <p className="text-base text-slate-500 dark:text-slate-400">
              {isLogin ? t.noAccount : t.haveAccount}{' '}
              <button
                onClick={() => setIsLogin(!isLogin)}
                className="text-indigo-600 dark:text-indigo-400 font-bold hover:underline mx-1"
              >
                {isLogin ? t.signUpLink : t.loginLink}
              </button>
            </p>
          </div>
        </div>

      </div>

      <button onClick={onBack} className="mt-8 flex items-center gap-2 text-slate-500 hover:text-slate-800 dark:hover:text-white transition-colors text-base font-medium">
        <span className="rtl:hidden"><ArrowLeft className="w-5 h-5" /></span>
        <span className="ltr:hidden"><ArrowRight className="w-5 h-5" /></span>
        {t.returnHome}
      </button>

    </div>
  );
};

export default AuthPage;