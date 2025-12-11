import React, { createContext, useContext, useState, useEffect, ReactNode, useCallback } from 'react';
import { supabase, SupabaseUser } from '../services/supabaseService';

/**
 * Auth Context Type
 */
interface AuthContextType {
    user: SupabaseUser | null;
    loading: boolean;
    isAuthenticated: boolean;
    signInWithGoogle: () => void;
    signInWithEmail: (email: string, password: string) => Promise<{ success: boolean; error?: string }>;
    signUpWithEmail: (email: string, password: string, name?: string) => Promise<{ success: boolean; error?: string }>;
    signOut: () => Promise<void>;
    refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

/**
 * Hook لاستخدام Auth Context
 */
export const useAuth = (): AuthContextType => {
    const context = useContext(AuthContext);
    if (!context) {
        throw new Error('useAuth must be used within AuthProvider');
    }
    return context;
};

/**
 * Auth Provider Component
 */
export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
    const [user, setUser] = useState<SupabaseUser | null>(null);
    const [loading, setLoading] = useState(true);

    /**
     * تحميل المستخدم الحالي
     */
    const loadUser = useCallback(async () => {
        try {
            const currentUser = await supabase.getUser();
            setUser(currentUser);
        } catch (error) {
            console.error('Error loading user:', error);
            setUser(null);
        } finally {
            setLoading(false);
        }
    }, []);

    /**
     * تحديث بيانات المستخدم
     */
    const refreshUser = useCallback(async () => {
        await loadUser();
    }, [loadUser]);

    /**
     * معالجة OAuth callback
     */
    const handleOAuthCallback = useCallback(async () => {
        const currentPath = window.location.pathname;
        const hash = window.location.hash;

        // التحقق من وجود callback
        if (currentPath === '/auth/callback' || hash.includes('access_token')) {
            console.log('🔐 Processing OAuth callback...');

            // استخراج access_token من hash
            const params = new URLSearchParams(hash.replace('#', ''));
            const accessToken = params.get('access_token');
            const refreshToken = params.get('refresh_token');

            if (accessToken) {
                // حفظ التوكن
                localStorage.setItem('supabase_access_token', accessToken);
                if (refreshToken) {
                    localStorage.setItem('supabase_refresh_token', refreshToken);
                }

                // تحميل بيانات المستخدم
                await loadUser();

                // تنظيف URL والعودة للصفحة الرئيسية
                window.history.replaceState({}, document.title, '/');
                console.log('✅ OAuth login successful');
            }
        }
    }, [loadUser]);

    useEffect(() => {
        // معالجة OAuth callback أولاً
        handleOAuthCallback().then(() => {
            // ثم تحميل المستخدم
            loadUser();
        });
    }, [handleOAuthCallback, loadUser]);

    /**
     * تسجيل الدخول بـ Google
     */
    const signInWithGoogle = useCallback(() => {
        const url = supabase.getOAuthUrl('google');
        console.log('🔗 Redirecting to Google OAuth:', url);
        window.location.href = url;
    }, []);

    /**
     * تسجيل الدخول بالإيميل
     */
    const signInWithEmail = useCallback(async (
        email: string,
        password: string
    ): Promise<{ success: boolean; error?: string }> => {
        try {
            const result = await supabase.signIn(email, password);
            if (result) {
                setUser(result);
                return { success: true };
            }
            return { success: false, error: 'فشل تسجيل الدخول. تحقق من البيانات.' };
        } catch (error: any) {
            console.error('Sign in error:', error);
            return { success: false, error: error.message || 'حدث خطأ غير متوقع' };
        }
    }, []);

    /**
     * إنشاء حساب جديد
     */
    const signUpWithEmail = useCallback(async (
        email: string,
        password: string,
        name?: string
    ): Promise<{ success: boolean; error?: string }> => {
        try {
            const result = await supabase.signUp(email, password, name);
            if (result) {
                setUser(result);
                return { success: true };
            }
            return { success: false, error: 'فشل إنشاء الحساب. قد يكون الإيميل مستخدم.' };
        } catch (error: any) {
            console.error('Sign up error:', error);
            return { success: false, error: error.message || 'حدث خطأ غير متوقع' };
        }
    }, []);

    /**
     * تسجيل الخروج
     */
    const signOut = useCallback(async () => {
        try {
            await supabase.signOut();
            setUser(null);
            console.log('👋 User signed out');
        } catch (error) {
            console.error('Sign out error:', error);
        }
    }, []);

    const value: AuthContextType = {
        user,
        loading,
        isAuthenticated: !!user,
        signInWithGoogle,
        signInWithEmail,
        signUpWithEmail,
        signOut,
        refreshUser,
    };

    return (
        <AuthContext.Provider value={value}>
            {children}
        </AuthContext.Provider>
    );
};

export default AuthProvider;
