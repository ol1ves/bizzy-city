-- ============================================================
-- Drop listing_type column from properties
-- All scraped listings are for_lease — the column is redundant
-- ============================================================

alter table properties drop column listing_type;