/**
 * Supabase Client Configuration
 * Used for authentication, database, and storage
 */

// Supabase Configuration
const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL || 'https://phqtzwxslkqdgzukgmab.supabase.co';
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY || '';

/**
 * User interface
 */
export interface SupabaseUser {
    id: string;
    email: string;
    name?: string;
    avatar_url?: string;
    created_at?: string;
}

/**
 * Video history item
 */
export interface VideoHistory {
    id: string;
    user_id: string;
    url: string;
    title: string;
    thumbnail?: string;
    mode: 'DUBBING' | 'SUBTITLES' | 'BOTH';
    status: 'pending' | 'processing' | 'completed' | 'failed';
    result_url?: string;
    srt_url?: string;
    created_at: string;
    completed_at?: string;
}

/**
 * Simple fetch-based Supabase REST API client
 * (No external dependencies required)
 */
class SupabaseClient {
    private url: string;
    private key: string;
    private accessToken: string | null = null;

    constructor(url: string, key: string) {
        this.url = url;
        this.key = key;
        // Try to restore session from localStorage
        this.accessToken = localStorage.getItem('supabase_access_token');
    }

    private async fetch(endpoint: string, options: RequestInit = {}) {
        const headers: Record<string, string> = {
            'apikey': this.key,
            'Content-Type': 'application/json',
            ...(options.headers as Record<string, string> || {}),
        };

        if (this.accessToken) {
            headers['Authorization'] = `Bearer ${this.accessToken}`;
        }

        const response = await fetch(`${this.url}${endpoint}`, {
            ...options,
            headers,
        });

        if (!response.ok) {
            const error = await response.json().catch(() => ({ message: 'Unknown error' }));
            throw new Error(error.message || error.error_description || 'Request failed');
        }

        return response.json();
    }

    // ============= Auth Methods =============

    /**
     * Sign up with email and password
     */
    async signUp(email: string, password: string, name?: string): Promise<SupabaseUser | null> {
        try {
            const data = await this.fetch('/auth/v1/signup', {
                method: 'POST',
                body: JSON.stringify({
                    email,
                    password,
                    data: { name },
                }),
            });

            if (data.access_token) {
                this.accessToken = data.access_token;
                localStorage.setItem('supabase_access_token', data.access_token);
            }

            return data.user ? {
                id: data.user.id,
                email: data.user.email,
                name: data.user.user_metadata?.name,
            } : null;
        } catch (error) {
            console.error('Sign up error:', error);
            return null;
        }
    }

    /**
     * Sign in with email and password
     */
    async signIn(email: string, password: string): Promise<SupabaseUser | null> {
        try {
            const data = await this.fetch('/auth/v1/token?grant_type=password', {
                method: 'POST',
                body: JSON.stringify({ email, password }),
            });

            if (data.access_token) {
                this.accessToken = data.access_token;
                localStorage.setItem('supabase_access_token', data.access_token);
            }

            return data.user ? {
                id: data.user.id,
                email: data.user.email,
                name: data.user.user_metadata?.name,
            } : null;
        } catch (error) {
            console.error('Sign in error:', error);
            return null;
        }
    }

    /**
     * Sign out
     */
    async signOut(): Promise<void> {
        try {
            await this.fetch('/auth/v1/logout', { method: 'POST' });
        } catch (error) {
            console.error('Sign out error:', error);
        } finally {
            this.accessToken = null;
            localStorage.removeItem('supabase_access_token');
        }
    }

    /**
     * Get current user
     */
    async getUser(): Promise<SupabaseUser | null> {
        if (!this.accessToken) return null;

        try {
            const data = await this.fetch('/auth/v1/user');
            return {
                id: data.id,
                email: data.email,
                name: data.user_metadata?.name,
                avatar_url: data.user_metadata?.avatar_url,
            };
        } catch (error) {
            console.error('Get user error:', error);
            return null;
        }
    }

    /**
     * Sign in with OAuth provider (Google, Apple, etc.)
     */
    getOAuthUrl(provider: 'google' | 'apple' | 'github'): string {
        const redirectUrl = typeof window !== 'undefined'
            ? `${window.location.origin}/auth/callback`
            : 'https://arab-dubbing.vercel.app/auth/callback';

        return `${this.url}/auth/v1/authorize?provider=${provider}&redirect_to=${encodeURIComponent(redirectUrl)}`;
    }

    // ============= Database Methods =============

    /**
     * Save video to history
     */
    async saveVideoHistory(video: Omit<VideoHistory, 'id' | 'created_at'>): Promise<VideoHistory | null> {
        if (!this.accessToken) return null;

        try {
            const data = await this.fetch('/rest/v1/video_history', {
                method: 'POST',
                body: JSON.stringify(video),
                headers: {
                    'Prefer': 'return=representation',
                },
            });
            return data[0] || null;
        } catch (error) {
            console.error('Save video error:', error);
            return null;
        }
    }

    /**
     * Get user's video history
     */
    async getVideoHistory(userId: string): Promise<VideoHistory[]> {
        try {
            const data = await this.fetch(`/rest/v1/video_history?user_id=eq.${userId}&order=created_at.desc`);
            return data || [];
        } catch (error) {
            console.error('Get history error:', error);
            return [];
        }
    }

    /**
     * Update video status
     */
    async updateVideoStatus(
        videoId: string,
        status: VideoHistory['status'],
        resultUrl?: string,
        srtUrl?: string
    ): Promise<boolean> {
        try {
            await this.fetch(`/rest/v1/video_history?id=eq.${videoId}`, {
                method: 'PATCH',
                body: JSON.stringify({
                    status,
                    result_url: resultUrl,
                    srt_url: srtUrl,
                    completed_at: status === 'completed' ? new Date().toISOString() : null,
                }),
            });
            return true;
        } catch (error) {
            console.error('Update video error:', error);
            return false;
        }
    }

    // ============= Storage Methods =============

    /**
     * Get public URL for a file in storage
     */
    getPublicUrl(bucket: string, path: string): string {
        return `${this.url}/storage/v1/object/public/${bucket}/${path}`;
    }

    /**
     * Check if user is authenticated
     */
    isAuthenticated(): boolean {
        return !!this.accessToken;
    }
}

// Create singleton instance
export const supabase = new SupabaseClient(SUPABASE_URL, SUPABASE_ANON_KEY);

export { SUPABASE_URL, SUPABASE_ANON_KEY };
