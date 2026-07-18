-- Create table for multiple resumes
CREATE TABLE IF NOT EXISTS user_resumes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    name TEXT NOT NULL,          -- e.g., 'Backend Resume', 'Frontend Resume'
    resume_url TEXT NOT NULL,    -- path/url to the file in Supabase Storage or external link
    ats_score INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Create table for multiple cover letter templates
CREATE TABLE IF NOT EXISTS user_cover_letters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    name TEXT NOT NULL,          -- e.g., 'Backend Engineer Cover Letter'
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Create table for job applications tracking
CREATE TABLE IF NOT EXISTS job_applications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    company TEXT NOT NULL,
    role TEXT NOT NULL,
    job_url TEXT NOT NULL,
    resume_version TEXT,         -- name/version of the resume used
    cover_letter_version TEXT,   -- name/version of the cover letter used (or 'None')
    match_score INTEGER,
    status TEXT NOT NULL DEFAULT 'Applied' CHECK (status IN ('Applied', 'In Review', 'Interview', 'Assessment', 'Offer', 'Rejected')),
    notes TEXT DEFAULT '',
    date_applied TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Enable RLS
ALTER TABLE user_resumes ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_cover_letters ENABLE ROW LEVEL SECURITY;
ALTER TABLE job_applications ENABLE ROW LEVEL SECURITY;

-- Permissive policies for full CRUD
DROP POLICY IF EXISTS "Public full access user_resumes" ON user_resumes;
CREATE POLICY "Public full access user_resumes" ON user_resumes FOR ALL USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "Public full access user_cover_letters" ON user_cover_letters;
CREATE POLICY "Public full access user_cover_letters" ON user_cover_letters FOR ALL USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "Public full access job_applications" ON job_applications;
CREATE POLICY "Public full access job_applications" ON job_applications FOR ALL USING (true) WITH CHECK (true);
