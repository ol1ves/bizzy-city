-- Migration: loopnet_to_crexy
-- Switches the properties table from LoopNet as the data source to Crexy,
-- adds the neighborhood column, and hardens the property_photos upsert constraint.

ALTER TABLE properties
  RENAME COLUMN loopnet_id TO crexy_id;

ALTER TABLE properties
  RENAME COLUMN loopnet_url TO crexy_url;

ALTER TABLE properties
  ADD COLUMN IF NOT EXISTS neighborhood text;

ALTER TABLE properties
  DROP CONSTRAINT IF EXISTS properties_loopnet_id_key;

ALTER TABLE properties
  ADD CONSTRAINT properties_crexy_id_key UNIQUE (crexy_id);

ALTER TABLE property_photos
  ADD CONSTRAINT property_photos_property_sort_key
  UNIQUE (property_id, sort_order);