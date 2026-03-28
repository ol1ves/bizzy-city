-- Migration: crexy_to_crexi
-- Switches the properties table from Crexy as the data source to Crexi,
-- adds the neighborhood column, and hardens the property_photos upsert constraint.

ALTER TABLE properties
  RENAME COLUMN crexy_id TO crexi_id;

ALTER TABLE properties
  RENAME COLUMN crexy_url TO crexi_url;

ALTER TABLE properties
  ADD COLUMN IF NOT EXISTS neighborhood text;

ALTER TABLE properties
  DROP CONSTRAINT IF EXISTS properties_crexy_id_key;
