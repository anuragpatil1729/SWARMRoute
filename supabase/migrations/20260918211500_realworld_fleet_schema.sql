-- Migration: Real-World Fleet Platform Schema Extensions
-- Authoritative Schema for Vehicles, Real-World Orders, Route Sessions, and BLE Mesh Relays

-- 1. Create Dedicated Vehicles Table
CREATE TABLE IF NOT EXISTS public.vehicles (
    id TEXT PRIMARY KEY,
    partner_id TEXT REFERENCES public.delivery_partners(id) ON DELETE SET NULL,
    manufacturer TEXT NOT NULL,
    model TEXT NOT NULL,
    model_year INT,
    fuel_type TEXT NOT NULL, -- DIESEL, ELECTRIC, PETROL, HYBRID
    engine_type TEXT NOT NULL,
    fuel_capacity NUMERIC(6,2) NOT NULL DEFAULT 60.0,
    current_fuel NUMERIC(6,2) NOT NULL DEFAULT 60.0,
    odometer_km NUMERIC(10,2) DEFAULT 0.0,
    vehicle_condition NUMERIC(3,2) DEFAULT 1.0, -- 0.0 to 1.0
    maintenance_score NUMERIC(3,2) DEFAULT 1.0,
    tyre_condition NUMERIC(3,2) DEFAULT 1.0,
    engine_health NUMERIC(3,2) DEFAULT 1.0,
    average_fuel_efficiency NUMERIC(5,2) DEFAULT 12.0, -- km/L or km/kWh
    max_payload_kg NUMERIC(6,1) DEFAULT 500.0,
    current_payload_kg NUMERIC(6,1) DEFAULT 0.0,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Enhance Orders Table with Real Geographic Coordinates and Status Lifecycle
ALTER TABLE public.orders 
    ADD COLUMN IF NOT EXISTS customer_name TEXT,
    ADD COLUMN IF NOT EXISTS pickup_address TEXT,
    ADD COLUMN IF NOT EXISTS pickup_lat NUMERIC(9,6),
    ADD COLUMN IF NOT EXISTS pickup_lon NUMERIC(9,6),
    ADD COLUMN IF NOT EXISTS delivery_lat NUMERIC(9,6),
    ADD COLUMN IF NOT EXISTS delivery_lon NUMERIC(9,6),
    ADD COLUMN IF NOT EXISTS estimated_distance_km NUMERIC(6,2),
    ADD COLUMN IF NOT EXISTS estimated_eta_mins NUMERIC(6,1),
    ADD COLUMN IF NOT EXISTS assigned_partner_id TEXT,
    ADD COLUMN IF NOT EXISTS assigned_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS picked_up_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS delivered_at TIMESTAMPTZ;

-- 3. Dedicated Order Assignments Table
CREATE TABLE IF NOT EXISTS public.order_assignments (
    id BIGSERIAL PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES public.orders(id) ON DELETE CASCADE,
    partner_id TEXT NOT NULL,
    vehicle_id TEXT,
    allocated_by TEXT DEFAULT 'DISPATCH_MANAGER',
    dispatch_mode TEXT DEFAULT 'MANUAL', -- MANUAL, AI_RECOMMENDED
    status TEXT DEFAULT 'ASSIGNED',
    allocated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Route Sessions and Events Table
CREATE TABLE IF NOT EXISTS public.route_sessions (
    id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES public.orders(id) ON DELETE CASCADE,
    partner_id TEXT NOT NULL,
    vehicle_id TEXT NOT NULL,
    origin_lat NUMERIC(9,6) NOT NULL,
    origin_lon NUMERIC(9,6) NOT NULL,
    dest_lat NUMERIC(9,6) NOT NULL,
    dest_lon NUMERIC(9,6) NOT NULL,
    distance_km NUMERIC(6,2),
    duration_mins NUMERIC(6,1),
    route_geometry JSONB DEFAULT '[]'::jsonb,
    status TEXT DEFAULT 'ACTIVE', -- ACTIVE, COMPLETED, REROUTED, ABORTED
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS public.route_events (
    id BIGSERIAL PRIMARY KEY,
    session_id TEXT REFERENCES public.route_sessions(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL, -- GPS_UPDATE, REROUTE_RECOMMENDED, REROUTE_APPROVED, ASSISTANCE_REQUESTED
    description TEXT,
    severity TEXT DEFAULT 'INFO',
    payload JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. Physical BLE Mesh Messages & Bridged Relays Table
CREATE TABLE IF NOT EXISTS public.mesh_messages (
    id BIGSERIAL PRIMARY KEY,
    message_id TEXT NOT NULL UNIQUE,
    source_device_id TEXT NOT NULL,
    destination_device_id TEXT DEFAULT 'BACKEND',
    message_type TEXT NOT NULL, -- ASSISTANCE_REQUEST, SOS_ALERT, ROUTE_ADVISORY, ACK
    timestamp NUMERIC(15,3) NOT NULL,
    ttl INT NOT NULL DEFAULT 5,
    hop_count INT NOT NULL DEFAULT 0,
    payload JSONB DEFAULT '{}'::jsonb,
    signature TEXT,
    bridge_device_id TEXT,
    received_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable RLS
ALTER TABLE public.vehicles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.order_assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.route_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.route_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mesh_messages ENABLE ROW LEVEL SECURITY;

-- Public read/write policies for platform operation
DO $$
BEGIN
    DROP POLICY IF EXISTS "Public read vehicles" ON public.vehicles;
    CREATE POLICY "Public read vehicles" ON public.vehicles FOR SELECT USING (true);
    
    DROP POLICY IF EXISTS "Public write vehicles" ON public.vehicles;
    CREATE POLICY "Public write vehicles" ON public.vehicles FOR ALL USING (true);

    DROP POLICY IF EXISTS "Public read order_assignments" ON public.order_assignments;
    CREATE POLICY "Public read order_assignments" ON public.order_assignments FOR SELECT USING (true);

    DROP POLICY IF EXISTS "Public write order_assignments" ON public.order_assignments;
    CREATE POLICY "Public write order_assignments" ON public.order_assignments FOR ALL USING (true);

    DROP POLICY IF EXISTS "Public read route_sessions" ON public.route_sessions;
    CREATE POLICY "Public read route_sessions" ON public.route_sessions FOR SELECT USING (true);

    DROP POLICY IF EXISTS "Public write route_sessions" ON public.route_sessions;
    CREATE POLICY "Public write route_sessions" ON public.route_sessions FOR ALL USING (true);

    DROP POLICY IF EXISTS "Public read route_events" ON public.route_events;
    CREATE POLICY "Public read route_events" ON public.route_events FOR SELECT USING (true);

    DROP POLICY IF EXISTS "Public write route_events" ON public.route_events;
    CREATE POLICY "Public write route_events" ON public.route_events FOR ALL USING (true);

    DROP POLICY IF EXISTS "Public read mesh_messages" ON public.mesh_messages;
    CREATE POLICY "Public read mesh_messages" ON public.mesh_messages FOR SELECT USING (true);

    DROP POLICY IF EXISTS "Public write mesh_messages" ON public.mesh_messages;
    CREATE POLICY "Public write mesh_messages" ON public.mesh_messages FOR ALL USING (true);
END $$;
