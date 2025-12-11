import React, { createContext, useContext, useState, useCallback, ReactNode } from 'react';
import { CheckCircle2, XCircle, AlertCircle, X, Info } from 'lucide-react';

/**
 * Toast Types
 */
type ToastType = 'success' | 'error' | 'warning' | 'info';

interface Toast {
    id: string;
    message: string;
    type: ToastType;
}

interface ToastContextType {
    showToast: (message: string, type?: ToastType) => void;
    showSuccess: (message: string) => void;
    showError: (message: string) => void;
    showWarning: (message: string) => void;
    showInfo: (message: string) => void;
}

const ToastContext = createContext<ToastContextType | undefined>(undefined);

/**
 * Hook لاستخدام Toast
 */
export const useToast = (): ToastContextType => {
    const context = useContext(ToastContext);
    if (!context) {
        throw new Error('useToast must be used within ToastProvider');
    }
    return context;
};

/**
 * Toast Provider Component
 */
export const ToastProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
    const [toasts, setToasts] = useState<Toast[]>([]);

    const showToast = useCallback((message: string, type: ToastType = 'success') => {
        const id = `toast_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

        setToasts(prev => [...prev, { id, message, type }]);

        // إزالة تلقائية بعد 4 ثواني
        setTimeout(() => {
            setToasts(prev => prev.filter(t => t.id !== id));
        }, 4000);
    }, []);

    const showSuccess = useCallback((message: string) => showToast(message, 'success'), [showToast]);
    const showError = useCallback((message: string) => showToast(message, 'error'), [showToast]);
    const showWarning = useCallback((message: string) => showToast(message, 'warning'), [showToast]);
    const showInfo = useCallback((message: string) => showToast(message, 'info'), [showToast]);

    const removeToast = (id: string) => {
        setToasts(prev => prev.filter(t => t.id !== id));
    };

    // خريطة الأيقونات
    const IconMap: Record<ToastType, React.FC<{ className?: string }>> = {
        success: CheckCircle2,
        error: XCircle,
        warning: AlertCircle,
        info: Info,
    };

    // خريطة الألوان
    const colorMap: Record<ToastType, string> = {
        success: 'bg-gradient-to-r from-green-500 to-emerald-500',
        error: 'bg-gradient-to-r from-red-500 to-rose-500',
        warning: 'bg-gradient-to-r from-amber-500 to-orange-500',
        info: 'bg-gradient-to-r from-blue-500 to-indigo-500',
    };

    return (
        <ToastContext.Provider value={{ showToast, showSuccess, showError, showWarning, showInfo }}>
            {children}

            {/* Toast Container */}
            <div className="fixed bottom-6 left-6 right-6 md:left-auto md:right-6 z-[9999] flex flex-col gap-3 pointer-events-none" dir="rtl">
                {toasts.map((toast) => {
                    const Icon = IconMap[toast.type];
                    return (
                        <div
                            key={toast.id}
                            className={`
                pointer-events-auto
                flex items-center gap-3 
                px-5 py-4 
                rounded-xl 
                shadow-2xl 
                text-white 
                ${colorMap[toast.type]}
                animate-in slide-in-from-bottom-4 fade-in duration-300
                max-w-md w-full md:w-auto
              `}
                        >
                            <Icon className="w-5 h-5 flex-shrink-0" />
                            <span className="font-medium flex-grow text-sm md:text-base">{toast.message}</span>
                            <button
                                onClick={() => removeToast(toast.id)}
                                className="flex-shrink-0 p-1 hover:bg-white/20 rounded-lg transition-colors"
                                title="إغلاق"
                            >
                                <X className="w-4 h-4" />
                            </button>
                        </div>
                    );
                })}
            </div>
        </ToastContext.Provider>
    );
};

export default ToastProvider;
