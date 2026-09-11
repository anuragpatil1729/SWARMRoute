-- Migration: Auth and User Profiles for Managers and Delivery Partners

-- 1. Create Profiles table linked to Supabase auth.users
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    full_name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('manager', 'partner')),
    phone TEXT,
    company_name TEXT,
    vehicle_id TEXT,
    city TEXT DEFAULT 'Bengaluru',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS city TEXT DEFAULT 'Bengaluru';

-- 2. Enhance delivery_partners table with user linkage
ALTER TABLE public.delivery_partners
    ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS email TEXT;

-- 3. Enable RLS on profiles
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

-- 4. RLS Policies for profiles
DO $$
BEGIN
    DROP POLICY IF EXISTS "Public read profiles" ON public.profiles;
    CREATE POLICY "Public read profiles" ON public.profiles FOR SELECT USING (true);

    DROP POLICY IF EXISTS "Users can insert their own profile" ON public.profiles;
    CREATE POLICY "Users can insert their own profile" ON public.profiles FOR INSERT WITH CHECK (true);

    DROP POLICY IF EXISTS "Users can update their own profile" ON public.profiles;
    CREATE POLICY "Users can update their own profile" ON public.profiles FOR UPDATE USING (auth.uid() = id);
END $$;
