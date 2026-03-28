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
      let { data, error: queryError } = await supabase
        .from('properties_with_top_rec')
        .select('*');

      if (queryError) {
        ({ data, error: queryError } = await supabase
          .from('properties')
          .select('*'));
      }

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
