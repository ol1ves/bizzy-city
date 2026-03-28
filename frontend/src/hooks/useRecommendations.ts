'use client';

import { useEffect, useState } from 'react';
import { getSupabase } from '@/lib/supabase';
import type { Recommendation } from '@/lib/types';

export function useRecommendations(propertyId: string | null) {
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!propertyId) {
      setRecommendations([]);
      return;
    }

    async function fetchRecommendations() {
      setLoading(true);
      setError(null);

      const supabase = getSupabase();
      const { data, error: queryError } = await supabase
        .from('recommendations')
        .select('*')
        .eq('property_id', propertyId)
        .order('rank');

      if (queryError) {
        setError(queryError.message);
      } else {
        setRecommendations(data ?? []);
      }
      setLoading(false);
    }

    fetchRecommendations();
  }, [propertyId]);

  return { recommendations, loading, error };
}
