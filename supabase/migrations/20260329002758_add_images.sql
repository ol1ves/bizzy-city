-- migration: add property_images table
-- created_at: 2026-03-28

create table public.property_images (
  id            uuid    not null default gen_random_uuid(),
  property_id   uuid    not null references public.properties(id) on delete cascade,
  storage_path  text    not null,
  is_primary    boolean not null default false,
  display_order integer not null default 0,
  uploaded_at   timestamp with time zone not null default now(),

  constraint property_images_pkey primary key (id)
) tablespace pg_default;

-- fast lookup of all images for a property, in order
create index idx_property_images_property_id
  on public.property_images using btree (property_id, display_order)
  tablespace pg_default;

-- enforce exactly one primary image per property
create unique index idx_property_images_one_primary
  on public.property_images (property_id)
  where (is_primary = true);