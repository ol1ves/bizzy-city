'use client';

import { useEffect, useState } from 'react';
import { getSupabase } from '@/lib/supabase';
import type { Property } from '@/lib/types';

export function useProperties() {
  const [properties, setProperties] = useState<Property[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchProperties() {
      const supabase = getSupabase();
      const { data, error: queryError } = await supabase
        .from('public_properties_demo')
        .select(
          'id,crexi_url,address,city,state_code,zip_code,latitude,longitude,square_footage,asking_rent_per_sqft,description,top_rec_business,top_rec_score,top_rec_summary',
        );

      if (queryError) {
        setError(queryError.message);
      } else {
        const valid = (data ?? []).filter(
          (p: Property) => p.latitude != null && p.longitude != null
        );
        setProperties(valid);
      }
      setLoading(false);
    }

    fetchProperties();
  }, []);

  return { properties, loading, error };
}
