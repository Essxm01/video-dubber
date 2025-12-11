import React, { useState, useEffect } from 'react';
import { ArrowLeft, ArrowRight, Camera, Save, History, User, Loader2, CheckCircle } from 'lucide-react';
import { Button } from './Button';
import { useAuth } from '../contexts/AuthContext';
import { useToast } from './ToastContext';
import { supabase, UserProfile, Project } from '../services/supabaseService';

interface SettingsPageProps {
    t: any;
    onBack: () => void;
}

export const SettingsPage: React.FC<SettingsPageProps> = ({ t, onBack }) => {
    const { user, refreshUser } = useAuth();
    const { showSuccess, showError } = useToast();

    // Profile state
    const [profile, setProfile] = useState<UserProfile | null>(null);
    const [username, setUsername] = useState('');
    const [fullName, setFullName] = useState('');
    const [avatarUrl, setAvatarUrl] = useState('');

    // Projects state
    const [projects, setProjects] = useState<Project[]>([]);

    // UI state
    const [isLoading, setIsLoading] = useState(true);
    const [isSaving, setIsSaving] = useState(false);
    const [isUploading, setIsUploading] = useState(false);
    const [usernameAvailable, setUsernameAvailable] = useState<boolean | null>(null);

    /**
     * تحميل بيانات المستخدم والمشاريع
     */
    useEffect(() => {
        if (user) {
            loadData();
        }
    }, [user]);

    const loadData = async () => {
        if (!user) return;

        setIsLoading(true);
        try {
            // تحميل الملف الشخصي
            const profileData = await supabase.getProfile(user.id);
            if (profileData) {
                setProfile(profileData);
                setUsername(profileData.username || '');
                setFullName(profileData.full_name || user.name || '');
                setAvatarUrl(profileData.avatar_url || user.avatar_url || '');
            } else {
                // استخدام بيانات المستخدم الأساسية
                setFullName(user.name || '');
                setAvatarUrl(user.avatar_url || '');
            }

            // تحميل المشاريع
            const projectsData = await supabase.getProjects(user.id);
            setProjects(projectsData);
        } catch (error) {
            console.error('Error loading data:', error);
        } finally {
            setIsLoading(false);
        }
    };

    /**
     * التحقق من توفر اسم المستخدم
     */
    const checkUsername = async (value: string) => {
        if (!value || value.length < 3) {
            setUsernameAvailable(null);
            return;
        }

        // إذا كان نفس الاسم الحالي
        if (profile?.username === value) {
            setUsernameAvailable(true);
            return;
        }

        const available = await supabase.isUsernameAvailable(value);
        setUsernameAvailable(available);
    };

    /**
     * معالجة تغيير اسم المستخدم
     */
    const handleUsernameChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const value = e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, '');
        setUsername(value);
        setUsernameAvailable(null);

        // تأخير الفحص
        const timeout = setTimeout(() => checkUsername(value), 500);
        return () => clearTimeout(timeout);
    };

    /**
     * رفع الصورة الشخصية
     */
    const handleAvatarUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file || !user) return;

        // التحقق من الحجم (max 2MB)
        if (file.size > 2 * 1024 * 1024) {
            showError('حجم الصورة كبير جداً. الحد الأقصى 2 ميجابايت');
            return;
        }

        setIsUploading(true);
        try {
            const url = await supabase.uploadAvatar(user.id, file);
            if (url) {
                setAvatarUrl(url);
                // تحديث الملف الشخصي
                await supabase.updateProfile(user.id, { avatar_url: url });
                showSuccess('تم تحديث الصورة بنجاح');
            } else {
                showError('فشل رفع الصورة');
            }
        } catch (error) {
            showError('حدث خطأ أثناء رفع الصورة');
        } finally {
            setIsUploading(false);
        }
    };

    /**
     * حفظ التغييرات
     */
    const handleSaveProfile = async () => {
        if (!user) return;

        // التحقق من اسم المستخدم
        if (username && usernameAvailable === false) {
            showError('اسم المستخدم غير متاح');
            return;
        }

        setIsSaving(true);
        try {
            const success = await supabase.updateProfile(user.id, {
                username: username || undefined,
                full_name: fullName,
                avatar_url: avatarUrl,
            });

            if (success) {
                showSuccess('تم حفظ التغييرات بنجاح');
                await refreshUser();
            } else {
                showError('فشل حفظ التغييرات');
            }
        } catch (error) {
            showError('حدث خطأ أثناء الحفظ');
        } finally {
            setIsSaving(false);
        }
    };

    /**
     * تنسيق التاريخ
     */
    const formatDate = (dateString: string) => {
        return new Date(dateString).toLocaleDateString('ar-EG', {
            year: 'numeric',
            month: 'long',
            day: 'numeric'
        });
    };

    /**
     * حالة المشروع بالعربية
     */
    const getStatusText = (status: string) => {
        switch (status) {
            case 'completed': return 'مكتمل';
            case 'processing': return 'قيد المعالجة';
            case 'pending': return 'في الانتظار';
            case 'failed': return 'فشل';
            default: return status;
        }
    };

    const getStatusColor = (status: string) => {
        switch (status) {
            case 'completed': return 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400';
            case 'processing': return 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400';
            case 'pending': return 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400';
            case 'failed': return 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400';
            default: return 'bg-slate-100 text-slate-700';
        }
    };

    // إذا لم يكن مسجل دخول
    if (!user) {
        return (
            <div className="max-w-4xl mx-auto py-12 px-4 text-center animate-in fade-in">
                <h1 className="text-2xl font-bold mb-4">يجب تسجيل الدخول أولاً</h1>
                <button
                    onClick={onBack}
                    className="text-indigo-600 hover:underline font-medium"
                >
                    العودة للرئيسية
                </button>
            </div>
        );
    }

    return (
        <div className="max-w-4xl mx-auto py-12 px-4 animate-in fade-in">
            {/* زر العودة */}
            <button
                onClick={onBack}
                className="flex items-center gap-2 text-slate-500 hover:text-slate-800 dark:hover:text-white mb-8 transition-colors"
            >
                <span className="rtl:hidden"><ArrowLeft className="w-5 h-5" /></span>
                <span className="ltr:hidden"><ArrowRight className="w-5 h-5" /></span>
                <span>{t.returnHome || 'العودة'}</span>
            </button>

            <h1 className="text-3xl font-bold text-slate-900 dark:text-white mb-8">
                {t.settings || 'الإعدادات'}
            </h1>

            {isLoading ? (
                <div className="flex items-center justify-center py-20">
                    <Loader2 className="w-8 h-8 animate-spin text-indigo-600" />
                </div>
            ) : (
                <div className="space-y-8">
                    {/* قسم الملف الشخصي */}
                    <div className="bg-white dark:bg-slate-800 rounded-2xl p-8 border border-slate-200 dark:border-slate-700 shadow-sm">
                        <h2 className="text-xl font-bold mb-6 flex items-center gap-2 text-slate-900 dark:text-white">
                            <User className="w-5 h-5 text-indigo-600" />
                            الملف الشخصي
                        </h2>

                        <div className="flex flex-col md:flex-row items-start gap-8">
                            {/* الصورة الشخصية */}
                            <div className="flex-shrink-0">
                                <div className="relative">
                                    <div className="w-28 h-28 rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden ring-4 ring-white dark:ring-slate-800 shadow-lg">
                                        {avatarUrl ? (
                                            <img src={avatarUrl} alt="Avatar" className="w-full h-full object-cover" />
                                        ) : (
                                            <div className="w-full h-full flex items-center justify-center text-4xl font-bold text-slate-400">
                                                {fullName?.charAt(0) || user.email?.charAt(0) || '?'}
                                            </div>
                                        )}
                                    </div>
                                    <label className={`
                    absolute bottom-0 right-0 w-10 h-10 
                    bg-indigo-600 hover:bg-indigo-700 
                    rounded-full flex items-center justify-center 
                    cursor-pointer transition-colors shadow-lg
                    ${isUploading ? 'opacity-50 cursor-wait' : ''}
                  `}>
                                        {isUploading ? (
                                            <Loader2 className="w-5 h-5 text-white animate-spin" />
                                        ) : (
                                            <Camera className="w-5 h-5 text-white" />
                                        )}
                                        <input
                                            type="file"
                                            accept="image/*"
                                            className="hidden"
                                            onChange={handleAvatarUpload}
                                            disabled={isUploading}
                                        />
                                    </label>
                                </div>
                                <p className="text-xs text-slate-500 text-center mt-2">الحد: 2 ميجا</p>
                            </div>

                            {/* حقول البيانات */}
                            <div className="flex-1 space-y-5 w-full">
                                {/* اسم المستخدم */}
                                <div>
                                    <label className="block text-sm font-medium text-slate-600 dark:text-slate-400 mb-2">
                                        اسم المستخدم
                                    </label>
                                    <div className="relative">
                                        <input
                                            type="text"
                                            value={username}
                                            onChange={handleUsernameChange}
                                            className={`
                        w-full px-4 py-3 rounded-xl 
                        border bg-slate-50 dark:bg-slate-900 
                        text-slate-900 dark:text-white
                        transition-colors
                        ${usernameAvailable === true ? 'border-green-500' : ''}
                        ${usernameAvailable === false ? 'border-red-500' : 'border-slate-200 dark:border-slate-600'}
                      `}
                                            placeholder="اختر اسم مستخدم فريد (حروف إنجليزية وأرقام فقط)"
                                            dir="ltr"
                                        />
                                        {usernameAvailable !== null && (
                                            <div className="absolute left-3 top-1/2 -translate-y-1/2 rtl:left-auto rtl:right-3">
                                                {usernameAvailable ? (
                                                    <CheckCircle className="w-5 h-5 text-green-500" />
                                                ) : (
                                                    <span className="text-red-500 text-xs">غير متاح</span>
                                                )}
                                            </div>
                                        )}
                                    </div>
                                </div>

                                {/* الاسم الكامل */}
                                <div>
                                    <label className="block text-sm font-medium text-slate-600 dark:text-slate-400 mb-2">
                                        الاسم الكامل
                                    </label>
                                    <input
                                        type="text"
                                        value={fullName}
                                        onChange={(e) => setFullName(e.target.value)}
                                        className="w-full px-4 py-3 rounded-xl border border-slate-200 dark:border-slate-600 bg-slate-50 dark:bg-slate-900 text-slate-900 dark:text-white"
                                        placeholder="الاسم الكامل"
                                    />
                                </div>

                                {/* البريد الإلكتروني (للقراءة فقط) */}
                                <div>
                                    <label className="block text-sm font-medium text-slate-600 dark:text-slate-400 mb-2">
                                        البريد الإلكتروني
                                    </label>
                                    <input
                                        type="email"
                                        value={user.email}
                                        disabled
                                        className="w-full px-4 py-3 rounded-xl border border-slate-200 dark:border-slate-600 bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 cursor-not-allowed"
                                        dir="ltr"
                                    />
                                </div>

                                {/* الرصيد */}
                                {profile?.credits !== undefined && (
                                    <div className="flex items-center gap-2 p-4 bg-indigo-50 dark:bg-indigo-900/20 rounded-xl">
                                        <span className="text-indigo-600 dark:text-indigo-400 font-medium">رصيد المعالجة:</span>
                                        <span className="text-2xl font-bold text-indigo-600 dark:text-indigo-400">{profile.credits}</span>
                                        <span className="text-slate-500 text-sm">فيديو</span>
                                    </div>
                                )}
                            </div>
                        </div>

                        {/* زر الحفظ */}
                        <div className="mt-8 flex justify-end">
                            <Button
                                onClick={handleSaveProfile}
                                isLoading={isSaving}
                                disabled={isSaving || (usernameAvailable === false)}
                            >
                                <Save className="w-4 h-4 ltr:mr-2 rtl:ml-2" />
                                حفظ التغييرات
                            </Button>
                        </div>
                    </div>

                    {/* قسم سجل الدبلجة */}
                    <div className="bg-white dark:bg-slate-800 rounded-2xl p-8 border border-slate-200 dark:border-slate-700 shadow-sm">
                        <h2 className="text-xl font-bold mb-6 flex items-center gap-2 text-slate-900 dark:text-white">
                            <History className="w-5 h-5 text-indigo-600" />
                            سجل الدبلجة
                        </h2>

                        {projects.length === 0 ? (
                            <div className="text-center py-12">
                                <div className="w-16 h-16 bg-slate-100 dark:bg-slate-700 rounded-full flex items-center justify-center mx-auto mb-4">
                                    <History className="w-8 h-8 text-slate-400" />
                                </div>
                                <p className="text-slate-500 dark:text-slate-400">لا يوجد مشاريع سابقة</p>
                                <p className="text-slate-400 dark:text-slate-500 text-sm mt-1">ابدأ بدبلجة فيديو من الصفحة الرئيسية</p>
                            </div>
                        ) : (
                            <div className="space-y-4">
                                {projects.map((project) => (
                                    <div
                                        key={project.id}
                                        className="flex items-center gap-4 p-4 rounded-xl bg-slate-50 dark:bg-slate-700/50 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
                                    >
                                        {/* الصورة المصغرة */}
                                        {project.thumbnail ? (
                                            <img
                                                src={project.thumbnail}
                                                alt=""
                                                className="w-24 h-14 rounded-lg object-cover flex-shrink-0"
                                            />
                                        ) : (
                                            <div className="w-24 h-14 rounded-lg bg-slate-200 dark:bg-slate-600 flex-shrink-0" />
                                        )}

                                        {/* التفاصيل */}
                                        <div className="flex-1 min-w-0">
                                            <h3 className="font-medium text-slate-900 dark:text-white truncate">
                                                {project.title || 'بدون عنوان'}
                                            </h3>
                                            <p className="text-sm text-slate-500 dark:text-slate-400">
                                                {formatDate(project.created_at)}
                                            </p>
                                        </div>

                                        {/* الوضع */}
                                        <span className="px-2 py-1 rounded text-xs font-bold bg-slate-100 dark:bg-slate-600 text-slate-600 dark:text-slate-300 flex-shrink-0">
                                            {project.mode}
                                        </span>

                                        {/* الحالة */}
                                        <span className={`px-3 py-1 rounded-full text-xs font-bold flex-shrink-0 ${getStatusColor(project.status)}`}>
                                            {getStatusText(project.status)}
                                        </span>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
};

export default SettingsPage;
