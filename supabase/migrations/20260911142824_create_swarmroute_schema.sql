-- SWARMRoute Supabase Schema
-- Stores Delivery Partners, Orders, Task Allocations, and Real-time Fleet Telemetry

-- 1. Delivery Partners Table
CREATE TABLE IF NOT EXISTS public.delivery_partners (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    phone TEXT,
    vehicle_model TEXT,
    registration TEXT,
    hub TEXT,
    city TEXT,
    rating NUMERIC(3,2),
    completed_deliveries INT DEFAULT 0,
    avatar TEXT,
    status TEXT DEFAULT 'IDLE',
    current_load NUMERIC(6,1) DEFAULT 0.0,
    max_weight NUMERIC(6,1),
    fuel_level NUMERIC(5,1) DEFAULT 100.0,
    speed_kmh NUMERIC(5,1) DEFAULT 0.0,
    location_x NUMERIC(6,2),
    location_y NUMERIC(6,2),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Orders Table
CREATE TABLE IF NOT EXISTS public.orders (
    id TEXT PRIMARY KEY,
    customer_id INT,
    address TEXT,
    area TEXT,
    city TEXT,
    demand_weight NUMERIC(6,1) NOT NULL,
    priority TEXT DEFAULT 'NORMAL',
    deadline NUMERIC(6,1),
    ready_time NUMERIC(6,1) DEFAULT 0.0,
    status TEXT DEFAULT 'PENDING',
    assigned_vehicle_id TEXT REFERENCES public.delivery_partners(id) ON DELETE SET NULL,
    payout_inr INT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Task Allocations History
CREATE TABLE IF NOT EXISTS public.task_allocations (
    id BIGSERIAL PRIMARY KEY,
    order_id TEXT NOT NULL,
    vehicle_id TEXT NOT NULL,
    allocated_by TEXT,
    status TEXT DEFAULT 'ASSIGNED',
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Real-time Telemetry Logs
CREATE TABLE IF NOT EXISTS public.telemetry_logs (
    id BIGSERIAL PRIMARY KEY,
    vehicle_id TEXT NOT NULL,
    status TEXT,
    speed_kmh NUMERIC(5,1),
    current_load NUMERIC(6,1),
    fuel_level NUMERIC(5,1),
    co2_kg NUMERIC(6,2),
    location_x NUMERIC(6,2),
    location_y NUMERIC(6,2),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable Row Level Security (RLS)
ALTER TABLE public.delivery_partners ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.task_allocations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.telemetry_logs ENABLE ROW LEVEL SECURITY;

-- Allow public read access to all tables
DO $$
BEGIN
    DROP POLICY IF EXISTS "Public read delivery_partners" ON public.delivery_partners;
    CREATE POLICY "Public read delivery_partners" ON public.delivery_partners FOR SELECT USING (true);
    
    DROP POLICY IF EXISTS "Public insert/update delivery_partners" ON public.delivery_partners;
    CREATE POLICY "Public insert/update delivery_partners" ON public.delivery_partners FOR ALL USING (true);

    DROP POLICY IF EXISTS "Public read orders" ON public.orders;
    CREATE POLICY "Public read orders" ON public.orders FOR SELECT USING (true);

    DROP POLICY IF EXISTS "Public insert/update orders" ON public.orders;
    CREATE POLICY "Public insert/update orders" ON public.orders FOR ALL USING (true);

    DROP POLICY IF EXISTS "Public read task_allocations" ON public.task_allocations;
    CREATE POLICY "Public read task_allocations" ON public.task_allocations FOR SELECT USING (true);

    DROP POLICY IF EXISTS "Public insert task_allocations" ON public.task_allocations;
    CREATE POLICY "Public insert task_allocations" ON public.task_allocations FOR INSERT WITH CHECK (true);

    DROP POLICY IF EXISTS "Public read telemetry_logs" ON public.telemetry_logs;
    CREATE POLICY "Public read telemetry_logs" ON public.telemetry_logs FOR SELECT USING (true);

    DROP POLICY IF EXISTS "Public insert telemetry_logs" ON public.telemetry_logs;
    CREATE POLICY "Public insert telemetry_logs" ON public.telemetry_logs FOR INSERT WITH CHECK (true);
END $$;
