export interface Property {
  id: string;
  crexi_id: string | null;
  crexi_url: string | null;
  address: string;
  city: string;
  state_code: string;
  zip_code: string | null;
  latitude: number;
  longitude: number;
  square_footage: number | null;
  asking_rent_per_sqft: number | null;
  description: string | null;
  created_at: string;
  updated_at: string;
  restaurant_analysis: string | null;
  restaurant_analyzed_at: string | null;
  retail_analysis: string | null;
  retail_analyzed_at: string | null;
  foot_traffic_analysis: string | null;
  foot_traffic_analyzed_at: string | null;
  ml_predictions: Record<string, unknown>[] | null;
  top_rec_business: string | null;
  top_rec_score: number | null;
  top_rec_reasoning: string | null;
  top_rec_summary: string | null;
}

export interface PropertyImage {
  id: string;
  property_id: string;
  storage_path: string;
  display_order: number;
  uploaded_at: string;
}

export interface Recommendation {
  id: string;
  property_id: string;
  rank: number;
  business_type: string;
  score: number;
  reasoning: string | null;
  summary: string | null;
  demand_signals: Record<string, unknown>;
  capture_rate?: number | string | null;
  estimated_annual_revenue?: number | string | null;
  survival_probability?: number | string | null;
  created_at: string;
  updated_at: string;
}
