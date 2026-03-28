export interface Property {
  id: string;
  crexi_id: string | null;
  crexi_url: string | null;
  address: string;
  city: string;
  neighborhood: string | null;
  zip_code: string | null;
  latitude: number;
  longitude: number;
  square_footage: number | null;
  asking_rent: number | null;
  asking_rent_per_sqft: number | null;
  year_built: number | null;
  listing_status: string;
  broker_name: string | null;
  broker_company: string | null;
  created_at: string;
  updated_at: string;
  top_rec_business: string | null;
  top_rec_score: number | null;
  top_rec_reasoning: string | null;
}

export interface Recommendation {
  id: string;
  property_id: string;
  rank: number;
  business_type: string;
  score: number;
  reasoning: string | null;
  demand_signals: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}
