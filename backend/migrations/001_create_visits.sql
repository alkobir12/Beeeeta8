-- ============================================================================
-- Migration 001 — create the `visits` table for the Workshop ERP
-- Run this once in your Supabase project (Dashboard → SQL Editor → New query).
-- After running it, Katrina's "افتح زيارة / سجل عملية" commands persist to the
-- database instead of in-memory staging (which is lost on restart).
-- ============================================================================

create table if not exists public.visits (
    id            uuid primary key default gen_random_uuid(),
    plate         text,
    vehicle_type  text,
    year          integer,
    customer_name text,
    customer_phone text,
    service       text,
    price         numeric(12,2),
    reason        text,
    status        text not null default 'open',   -- open | in_progress | closed | delivered
    created_at    timestamptz not null default now(),
    updated_at    timestamptz not null default now()
);

create index if not exists idx_visits_status on public.visits (status);
create index if not exists idx_visits_plate  on public.visits (plate);
create index if not exists idx_visits_phone  on public.visits (customer_phone);

-- Keep updated_at fresh on every UPDATE
create or replace function public.set_visits_updated_at()
returns trigger as $$
begin
    new.updated_at = now();
    return new;
end;
$$ language plpgsql;

drop trigger if exists trg_visits_updated_at on public.visits;
create trigger trg_visits_updated_at
    before update on public.visits
    for each row execute function public.set_visits_updated_at();

-- NOTE on RLS: the backend uses the SERVICE ROLE key which bypasses RLS, so no
-- policies are strictly required. If you enable RLS, add policies that allow the
-- service role full access (or appropriate per-user policies for the anon key).
