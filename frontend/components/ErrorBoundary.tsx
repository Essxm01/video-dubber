import React, { Component, ErrorInfo, ReactNode } from 'react';
import { AlertTriangle, RefreshCw, Home } from 'lucide-react';

interface Props {
    children: ReactNode;
    fallback?: ReactNode;
}

interface State {
    hasError: boolean;
    error: Error | null;
    errorInfo: ErrorInfo | null;
}

/**
 * ErrorBoundary Component
 * يلتقط أي خطأ في React ويعرض واجهة ودية بدلاً من الشاشة البيضاء
 */
export class ErrorBoundary extends Component<Props, State> {
    constructor(props: Props) {
        super(props);
        this.state = { hasError: false, error: null, errorInfo: null };
    }

    static getDerivedStateFromError(error: Error): Partial<State> {
        return { hasError: true, error };
    }

    componentDidCatch(error: Error, errorInfo: ErrorInfo) {
        console.error('🔴 ErrorBoundary caught an error:', error, errorInfo);
        this.setState({ errorInfo });

        // يمكن إرسال الخطأ لخدمة تتبع الأخطاء هنا
        // logErrorToService(error, errorInfo);
    }

    handleReload = () => {
        window.location.reload();
    };

    handleGoHome = () => {
        window.location.href = '/';
    };

    render() {
        if (this.state.hasError) {
            // إذا كان هناك fallback مخصص، استخدمه
            if (this.props.fallback) {
                return this.props.fallback;
            }

            // واجهة الخطأ الافتراضية
            return (
                <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800 flex items-center justify-center p-4" dir="rtl">
                    <div className="max-w-md w-full text-center">
                        {/* أيقونة الخطأ */}
                        <div className="relative mb-8">
                            <div className="absolute inset-0 bg-red-500/20 rounded-full blur-3xl animate-pulse"></div>
                            <div className="relative w-24 h-24 bg-gradient-to-br from-red-100 to-red-50 dark:from-red-900/30 dark:to-red-800/20 rounded-full flex items-center justify-center mx-auto border border-red-200 dark:border-red-800">
                                <AlertTriangle className="w-12 h-12 text-red-600 dark:text-red-400" />
                            </div>
                        </div>

                        {/* العنوان والوصف */}
                        <h1 className="text-3xl font-bold text-slate-900 dark:text-white mb-4">
                            حدث خطأ غير متوقع 😔
                        </h1>
                        <p className="text-slate-600 dark:text-slate-400 mb-8 leading-relaxed">
                            نعتذر عن هذا الخطأ. فريقنا يعمل على حله.
                            <br />
                            يرجى إعادة تحميل الصفحة أو العودة للرئيسية.
                        </p>

                        {/* أزرار الإجراءات */}
                        <div className="flex flex-col sm:flex-row gap-4 justify-center">
                            <button
                                onClick={this.handleReload}
                                className="inline-flex items-center justify-center gap-2 px-6 py-3 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl font-bold transition-all duration-200 shadow-lg shadow-indigo-500/25"
                            >
                                <RefreshCw className="w-5 h-5" />
                                إعادة التحميل
                            </button>

                            <button
                                onClick={this.handleGoHome}
                                className="inline-flex items-center justify-center gap-2 px-6 py-3 bg-slate-200 hover:bg-slate-300 dark:bg-slate-700 dark:hover:bg-slate-600 text-slate-700 dark:text-white rounded-xl font-bold transition-all duration-200"
                            >
                                <Home className="w-5 h-5" />
                                الصفحة الرئيسية
                            </button>
                        </div>

                        {/* تفاصيل الخطأ للمطورين (في وضع التطوير فقط) */}
                        {process.env.NODE_ENV === 'development' && this.state.error && (
                            <details className="mt-8 text-start bg-slate-100 dark:bg-slate-800 rounded-xl p-4 border border-slate-200 dark:border-slate-700">
                                <summary className="cursor-pointer text-sm font-medium text-slate-500 dark:text-slate-400">
                                    تفاصيل الخطأ (للمطورين فقط)
                                </summary>
                                <pre className="mt-4 text-xs text-red-600 dark:text-red-400 overflow-auto max-h-40" dir="ltr">
                                    {this.state.error.toString()}
                                    {this.state.errorInfo?.componentStack}
                                </pre>
                            </details>
                        )}
                    </div>
                </div>
            );
        }

        return this.props.children;
    }
}

export default ErrorBoundary;
