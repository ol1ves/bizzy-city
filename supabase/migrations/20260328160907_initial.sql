-- ============================================================
-- MVP Schema Migration
-- Run in Supabase SQL Editor or via supabase db push
-- ============================================================

-- Enable UUID generation
create extension if not exists "pgcrypto";


-- ============================================================
-- properties
-- ============================================================
create table properties (
  id                  uuid primary key default gen_random_uuid(),
  loopnet_id          text not null unique,
  loopnet_url         text not null,

  -- Location
  address             text not null,
  city                text not null,
  state               text not null,
  zip_code            text not null,
  lat                 numeric(9, 6),
  lng                 numeric(9, 6),

  -- Property details
  property_type       text not null,
  listing_type        text not null check (listing_type in ('for_sale', 'for_lease')),
  price_per_sqft_yr   numeric(10, 2),           -- nullable, annual $/sqft
  square_footage      int,
  year_built          int,

  -- Timestamps
  scraped_at          timestamptz not null,
  created_at          timestamptz not null default now()
);

create index on properties (zip_code);
create index on properties (property_type);
create index on properties (listing_type);


-- ============================================================
-- property_photos
-- ============================================================
create table property_photos (
  id              uuid primary key default gen_random_uuid(),
  property_id     uuid not null references properties (id) on delete cascade,

  storage_path    text not null,                -- Supabase Storage bucket key
  public_url      text not null,
  sort_order      int not null default 0,       -- sort_order = 0 is the primary/hero photo

  created_at      timestamptz not null default now()
);

create index on property_photos (property_id, sort_order);


-- ============================================================
-- recommendations
-- ============================================================
create table recommendations (
  id              uuid primary key default gen_random_uuid(),
  property_id     uuid not null references properties (id) on delete cascade,

  business_type   text not null,
  score           int not null check (score between 1 and 100),
  reasoning       text not null,

  created_at      timestamptz not null default now()
);

create index on recommendations (property_id, score desc);


-- ============================================================
-- Supabase RLS (Row Level Security)
-- Disabled by default for MVP — enable and add policies when
-- you introduce user auth.
-- ============================================================
alter table properties        enable row level security;
alter table property_photos   enable row level security;
alter table recommendations   enable row level security;

-- Temporary open policies for development (remove before prod)
create policy "allow all for now" on properties        for all using (true);
create policy "allow all for now" on property_photos   for all using (true);
create policy "allow all for now" on recommendations   for all using (true);