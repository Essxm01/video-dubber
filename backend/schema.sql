-- Enable UUID extension if not enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
-- Jobs Table: Tracks the overall dubbing request
CREATE TABLE IF NOT EXISTS video_jobs (
    id UUID PRIMARY KEY,
    original_filename TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    -- pending, processing, completed, failed
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    mode TEXT DEFAULT 'DUBBING',
    target_lang TEXT DEFAULT 'ar'
);
-- Segments Table: Tracks individual 5-minute chunks
CREATE TABLE IF NOT EXISTS video_segments (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    job_id UUID REFERENCES video_jobs(id) ON DELETE CASCADE,
    segment_index INTEGER NOT NULL,
    status TEXT DEFAULT 'pending',
    -- pending, processing, ready, failed
    media_url TEXT,
    -- Signed URL or Public URL from GCS
    gcs_path TEXT,
    -- Internal path in GCS bucket
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(job_id, segment_index)
);