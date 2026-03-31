-- Phase 1: restrict anonymous read surface to UI-needed fields only.

-- 1) Public-safe properties view (no raw analysis/ML internals).
create or replace view public.public_properties_demo as
select
  p.id,
  p.crexi_url,
  p.address,
  p.city,
  p.state_code,
  p.zip_code,
  p.latitude,
  p.longitude,
  p.square_footage,
  p.asking_rent_per_sqft,
  p.description,
  r.business_type as top_rec_business,
  r.score as top_rec_score,
  r.summary as top_rec_summary
from public.properties p
left join lateral (
  select
    rec.business_type,
    rec.score,
    rec.summary
  from public.recommendations rec
  where rec.property_id = p.id
  order by rec.rank asc
  limit 1
) r on true;

-- 2) Public-safe image metadata view.
create or replace view public.public_property_images_demo as
select
  id,
  property_id,
  storage_path,
  display_order,
  uploaded_at
from public.property_images;

-- 3) Shift anon/auth reads from base tables to public-safe views only.
revoke all privileges on table public.properties_with_top_rec from anon, authenticated;
revoke all privileges on table public.properties from anon, authenticated;
revoke all privileges on table public.property_images from anon, authenticated;
revoke all privileges on table public.recommendations from anon, authenticated;

grant select on table public.public_properties_demo to anon, authenticated;
grant select on table public.public_property_images_demo to anon, authenticated;
