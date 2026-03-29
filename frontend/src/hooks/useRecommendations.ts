'use client';

import { useCallback, useEffect, useState } from 'react';
import type { Recommendation } from '@/lib/types';

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

export function useRecommendations(propertyId: string | null) {
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [partial, setPartial] = useState(false);
  const [missingAnalyses, setMissingAnalyses] = useState<string[]>([]);
  const [fetchKey, setFetchKey] = useState(0);

  const refetch = useCallback(() => setFetchKey((k) => k + 1), []);

  useEffect(() => {
    if (!propertyId) {
      setRecommendations([]);
      setPartial(false);
      setMissingAnalyses([]);
      return;
    }

    let cancelled = false;

    async function fetchRecommendations() {
      setLoading(true);
      setError(null);
      setPartial(false);
      setMissingAnalyses([]);

      try {
        const res = await fetch(
          `${API_URL}/api/recommendations/${propertyId}`,
        );

        if (cancelled) return;

        if (res.status === 202) {
          const body = await res.json();
          setPartial(true);
          setMissingAnalyses(body.missing_analyses ?? []);
          setRecommendations([]);
        } else if (!res.ok) {
          const body = await res.json().catch(() => null);
          setError(body?.detail ?? `Request failed (${res.status})`);
        } else {
          const body = await res.json();
          setRecommendations(body.recommendations ?? []);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Network error');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetchRecommendations();
    return () => { cancelled = true; };
  }, [propertyId, fetchKey]);

  return { recommendations, loading, error, partial, missingAnalyses, refetch };
}
