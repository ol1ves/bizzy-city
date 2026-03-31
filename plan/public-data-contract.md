# Public Data Contract (Hackathon Demo)

This contract defines the only fields exposed to anonymous frontend clients.

## Properties feed (`public.public_properties_demo`)

- `id`
- `crexi_url`
- `address`
- `city`
- `state_code`
- `zip_code`
- `latitude`
- `longitude`
- `square_footage`
- `asking_rent_per_sqft`
- `description`
- `top_rec_business`
- `top_rec_score`
- `top_rec_summary`

## Property images feed (`public.public_property_images_demo`)

- `id`
- `property_id`
- `storage_path`
- `display_order`
- `uploaded_at`

## Recommendation API payload (`/api/recommendations/{property_id}`)

From backend response for display:

- `id`
- `property_id`
- `rank`
- `business_type`
- `score`
- `summary`
- `reasoning` (fallback if summary missing)
- `capture_rate`
- `estimated_annual_revenue`
- `survival_probability`
- `created_at`
- `updated_at`

## Explicitly excluded from anonymous direct reads

- `restaurant_analysis`
- `retail_analysis`
- `foot_traffic_analysis`
- `ml_predictions`
- `neighborhood_scan`
- any future internal model/debug columns
