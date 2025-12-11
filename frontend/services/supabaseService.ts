/**
 * Supabase Client Service
 * Real authentication, database, and storage
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
 * Profile interface (from profiles table)
 */
export interface UserProfile {
    id: string;
    username?: string;
    full_name?: string;
    avatar_url?: string;
    credits: number;
    created_at: string;
    updated_at: string;
}

/**
 * Project interface (dubbing history)
 */
export interface Project {
    id: string;
    user_id: string;
    youtube_url: string;
    title?: string;
    thumbnail?: string;
    mode: 'DUBBING' | 'SUBTITLES' | 'BOTH';
    status: 'pending' | 'processing' | 'completed' | 'failed';
    output_video_url?: string;
    output_srt_url?: string;
    original_text?: string;
    translated_text?: string;
    detected_language?: string;
    created_at: string;
    completed_at?: string;
}

/**
 * Supabase REST API Client
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

    /**
     * Internal fetch with authentication
     */
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
            throw new Error(error.message || error.error_description || error.msg || 'Request failed');
        }

        // Handle empty responses
        const text = await response.text();
        return text ? JSON.parse(text) : null;
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
                    data: { name, full_name: name },
                }),
            });

            if (data?.access_token) {
                this.accessToken = data.access_token;
                localStorage.setItem('supabase_access_token', data.access_token);
                if (data.refresh_token) {
                    localStorage.setItem('supabase_refresh_token', data.refresh_token);
                }
            }

            return data?.user ? {
                id: data.user.id,
                email: data.user.email,
                name: data.user.user_metadata?.name || data.user.user_metadata?.full_name,
                avatar_url: data.user.user_metadata?.avatar_url,
            } : null;
        } catch (error) {
            console.error('Sign up error:', error);
            throw error;
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

            if (data?.access_token) {
                this.accessToken = data.access_token;
                localStorage.setItem('supabase_access_token', data.access_token);
                if (data.refresh_token) {
                    localStorage.setItem('supabase_refresh_token', data.refresh_token);
                }
            }

            return data?.user ? {
                id: data.user.id,
                email: data.user.email,
                name: data.user.user_metadata?.name || data.user.user_metadata?.full_name,
                avatar_url: data.user.user_metadata?.avatar_url,
            } : null;
        } catch (error) {
            console.error('Sign in error:', error);
            throw error;
        }
    }

    /**
     * Sign out
     */
    async signOut(): Promise<void> {
        try {
            if (this.accessToken) {
                await this.fetch('/auth/v1/logout', { method: 'POST' }).catch(() => { });
            }
        } finally {
            this.accessToken = null;
            localStorage.removeItem('supabase_access_token');
            localStorage.removeItem('supabase_refresh_token');
        }
    }

    /**
     * Get current user
     */
    async getUser(): Promise<SupabaseUser | null> {
        if (!this.accessToken) return null;

        try {
            const data = await this.fetch('/auth/v1/user');
            return data ? {
                id: data.id,
                email: data.email,
                name: data.user_metadata?.name || data.user_metadata?.full_name,
                avatar_url: data.user_metadata?.avatar_url || data.user_metadata?.picture,
            } : null;
        } catch (error) {
            console.error('Get user error:', error);
            // Token might be expired
            this.accessToken = null;
            localStorage.removeItem('supabase_access_token');
            return null;
        }
    }

    /**
     * Get OAuth URL for provider
     */
    getOAuthUrl(provider: 'google' | 'apple' | 'github'): string {
        const redirectUrl = typeof window !== 'undefined'
            ? `${window.location.origin}/auth/callback`
            : 'https://arab-dubbing.vercel.app/auth/callback';

        return `${this.url}/auth/v1/authorize?provider=${provider}&redirect_to=${encodeURIComponent(redirectUrl)}`;
    }

    // ============= Profile Methods =============

    /**
     * Get user profile
     */
    async getProfile(userId: string): Promise<UserProfile | null> {
        if (!this.accessToken) return null;

        try {
            const data = await this.fetch(`/rest/v1/profiles?id=eq.${userId}&select=*`);
            return data?.[0] || null;
        } catch (error) {
            console.error('Get profile error:', error);
            return null;
        }
    }

    /**
     * Update user profile
     */
    async updateProfile(userId: string, updates: Partial<UserProfile>): Promise<boolean> {
        if (!this.accessToken) return false;

        try {
            await this.fetch(`/rest/v1/profiles?id=eq.${userId}`, {
                method: 'PATCH',
                body: JSON.stringify({
                    ...updates,
                    updated_at: new Date().toISOString(),
                }),
            });
            return true;
        } catch (error) {
            console.error('Update profile error:', error);
            return false;
        }
    }

    /**
     * Check if username is available
     */
    async isUsernameAvailable(username: string): Promise<boolean> {
        try {
            const data = await this.fetch(`/rest/v1/profiles?username=eq.${username}&select=id`);
            return !data || data.length === 0;
        } catch (error) {
            console.error('Check username error:', error);
            return false;
        }
    }

    // ============= Projects Methods =============

    /**
     * Get user's projects (dubbing history)
     */
    async getProjects(userId: string): Promise<Project[]> {
        if (!this.accessToken) return [];

        try {
            const data = await this.fetch(
                `/rest/v1/projects?user_id=eq.${userId}&select=*&order=created_at.desc`
            );
            return data || [];
        } catch (error) {
            console.error('Get projects error:', error);
            return [];
        }
    }

    /**
     * Create a new project
     */
    async createProject(project: Omit<Project, 'id' | 'created_at'>): Promise<Project | null> {
        if (!this.accessToken) return null;

        try {
            const data = await this.fetch('/rest/v1/projects', {
                method: 'POST',
                body: JSON.stringify(project),
                headers: {
                    'Prefer': 'return=representation',
                },
            });
            return data?.[0] || null;
        } catch (error) {
            console.error('Create project error:', error);
            return null;
        }
    }

    /**
     * Update project status
     */
    async updateProject(
        projectId: string,
        updates: Partial<Project>
    ): Promise<boolean> {
        if (!this.accessToken) return false;

        try {
            await this.fetch(`/rest/v1/projects?id=eq.${projectId}`, {
                method: 'PATCH',
                body: JSON.stringify(updates),
            });
            return true;
        } catch (error) {
            console.error('Update project error:', error);
            return false;
        }
    }

    // ============= Storage Methods =============

    /**
     * Upload avatar image
     */
    async uploadAvatar(userId: string, file: File): Promise<string | null> {
        if (!this.accessToken) return null;

        try {
            const fileExt = file.name.split('.').pop();
            const fileName = `${userId}/${Date.now()}.${fileExt}`;

            const response = await fetch(
                `${this.url}/storage/v1/object/avatars/${fileName}`,
                {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${this.accessToken}`,
                        'Content-Type': file.type,
                    },
                    body: file,
                }
            );

            if (!response.ok) {
                throw new Error('Upload failed');
            }

            // Return public URL
            return `${this.url}/storage/v1/object/public/avatars/${fileName}`;
        } catch (error) {
            console.error('Upload avatar error:', error);
            return null;
        }
    }

    /**
     * Get public URL for storage file
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

    /**
     * Get current access token
     */
    getAccessToken(): string | null {
        return this.accessToken;
    }
}

// Create singleton instance
export const supabase = new SupabaseClient(SUPABASE_URL, SUPABASE_ANON_KEY);

export { SUPABASE_URL, SUPABASE_ANON_KEY };
