-- Phase 0: immediate hardening for public hackathon demo.
-- Goal: public read-only access, no public writes, keep service_role workflows.

-- 1) Ensure every exposed app table has RLS enabled.
alter table if exists public.properties enable row level security;
alter table if exists public.recommendations enable row level security;
alter table if exists public.property_images enable row level security;

-- 2) Remove permissive write policies.
drop policy if exists "Service insert properties" on public.properties;
drop policy if exists "Service update properties" on public.properties;
drop policy if exists "Service insert recommendations" on public.recommendations;
drop policy if exists "Service update recommendations" on public.recommendations;

-- 3) Keep explicit public SELECT-only policies for demo reads.
drop policy if exists "Public read properties" on public.properties;
create policy "Public read properties"
  on public.properties
  for select
  using (true);

drop policy if exists "Public read recommendations" on public.recommendations;
create policy "Public read recommendations"
  on public.recommendations
  for select
  using (true);

drop policy if exists "Public read property_images" on public.property_images;
create policy "Public read property_images"
  on public.property_images
  for select
  using (true);

-- 4) Remove broad table privileges for anon/authenticated and keep SELECT only.
revoke all privileges on table public.properties from anon, authenticated;
revoke all privileges on table public.recommendations from anon, authenticated;
revoke all privileges on table public.property_images from anon, authenticated;
revoke all privileges on table public.properties_with_top_rec from anon, authenticated;

grant select on table public.properties to anon, authenticated;
grant select on table public.recommendations to anon, authenticated;
grant select on table public.property_images to anon, authenticated;
grant select on table public.properties_with_top_rec to anon, authenticated;

-- 5) Storage: keep public read of property photos, remove public upload.
drop policy if exists "Service upload photos" on storage.objects;

revoke insert, update, delete on table storage.objects from anon, authenticated;
