-- ============================================
-- SUPABASE MIGRATION: Arab Dubbing Platform v3.0
-- Run this in Supabase SQL Editor
-- ============================================

-- ============================================
-- 1. PROFILES TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID REFERENCES auth.users(id) ON DELETE CASCADE PRIMARY KEY,
    username TEXT UNIQUE,
    full_name TEXT,
    avatar_url TEXT,
    credits INTEGER DEFAULT 10,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable RLS
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

-- RLS Policies for profiles
DROP POLICY IF EXISTS "Users can view own profile" ON public.profiles;
CREATE POLICY "Users can view own profile" ON public.profiles
    FOR SELECT USING (auth.uid() = id);

DROP POLICY IF EXISTS "Users can update own profile" ON public.profiles;
CREATE POLICY "Users can update own profile" ON public.profiles
    FOR UPDATE USING (auth.uid() = id);

DROP POLICY IF EXISTS "Users can insert own profile" ON public.profiles;
CREATE POLICY "Users can insert own profile" ON public.profiles
    FOR INSERT WITH CHECK (auth.uid() = id);

-- Auto-create profile on signup trigger
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.profiles (id, full_name, avatar_url)
    VALUES (
        NEW.id,
        COALESCE(NEW.raw_user_meta_data->>'full_name', NEW.raw_user_meta_data->>'name'),
        NEW.raw_user_meta_data->>'avatar_url'
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- ============================================
-- 2. PROJECTS TABLE (Task Status & History)
-- UPDATED: Now used for tracking processing status
-- ============================================
DROP TABLE IF EXISTS public.projects;

CREATE TABLE public.projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    
    -- Video Info
    title TEXT,
    thumbnail TEXT,
    source TEXT DEFAULT 'upload',  -- 'upload' or 'youtube'
    youtube_url TEXT,
    
    -- Processing Mode
    mode TEXT CHECK (mode IN ('DUBBING', 'SUBTITLES', 'BOTH')) DEFAULT 'DUBBING',
    target_lang TEXT DEFAULT 'ar',
    
    -- Processing Status (for real-time tracking)
    status TEXT DEFAULT 'PENDING',
    progress INTEGER DEFAULT 0,
    message TEXT DEFAULT '',
    stage TEXT DEFAULT 'PENDING',
    
    -- Results
    result JSONB DEFAULT '{}',
    output_video_url TEXT,
    output_srt_url TEXT,
    original_text TEXT,
    translated_text TEXT,
    detected_language TEXT,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

-- Create index for faster status lookups
CREATE INDEX IF NOT EXISTS idx_projects_status ON public.projects(status);
CREATE INDEX IF NOT EXISTS idx_projects_id ON public.projects(id);

-- Enable RLS
ALTER TABLE public.projects ENABLE ROW LEVEL SECURITY;

-- RLS Policies for projects
-- IMPORTANT: Allow public read for status checking (no auth required for status)
DROP POLICY IF EXISTS "Anyone can read projects by ID" ON public.projects;
CREATE POLICY "Anyone can read projects by ID" ON public.projects
    FOR SELECT USING (true);

DROP POLICY IF EXISTS "Service can insert projects" ON public.projects;
CREATE POLICY "Service can insert projects" ON public.projects
    FOR INSERT WITH CHECK (true);

DROP POLICY IF EXISTS "Service can update projects" ON public.projects;
CREATE POLICY "Service can update projects" ON public.projects
    FOR UPDATE USING (true);

-- ============================================
-- 3. STORAGE BUCKET FOR AVATARS
-- ============================================
INSERT INTO storage.buckets (id, name, public)
VALUES ('avatars', 'avatars', true)
ON CONFLICT (id) DO NOTHING;

-- Storage policies for avatars
DROP POLICY IF EXISTS "Avatar images are publicly accessible" ON storage.objects;
CREATE POLICY "Avatar images are publicly accessible"
ON storage.objects FOR SELECT
USING (bucket_id = 'avatars');

DROP POLICY IF EXISTS "Users can upload their own avatar" ON storage.objects;
CREATE POLICY "Users can upload their own avatar"
ON storage.objects FOR INSERT
WITH CHECK (bucket_id = 'avatars' AND auth.uid()::text = (storage.foldername(name))[1]);

DROP POLICY IF EXISTS "Users can update their own avatar" ON storage.objects;
CREATE POLICY "Users can update their own avatar"
ON storage.objects FOR UPDATE
USING (bucket_id = 'avatars' AND auth.uid()::text = (storage.foldername(name))[1]);

-- ============================================
-- 4. HELPER FUNCTION: Check username availability
-- ============================================
CREATE OR REPLACE FUNCTION public.is_username_available(username_to_check TEXT)
RETURNS BOOLEAN AS $$
BEGIN
    RETURN NOT EXISTS (
        SELECT 1 FROM public.profiles WHERE username = username_to_check
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================
-- SUCCESS MESSAGE
-- ============================================
-- If you see this without errors, the migration was successful!
-- Tables: profiles, projects (with status tracking)
-- Storage bucket: avatars
--
-- The projects table now stores:
-- - Task processing status (progress, message, stage)
-- - Results as JSONB (video_url, srt_url, etc.)
-- - Public read access for status polling
