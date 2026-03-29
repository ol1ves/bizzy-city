'use client';

import { useCallback, useEffect, useState } from 'react';
import type { Recommendation } from '@/lib/types';

const RAW_API_URL = process.env.NEXT_PUBLIC_API_URL;
const API_URL = (
  RAW_API_URL
    ? /^(https?:)?\/\//.test(RAW_API_URL)
      ? RAW_API_URL
      : `https://${RAW_API_URL}`
    : 'http://localhost:8000'
).replace(/\/+$/, '');

export function useRecommendations(propertyId: string | null) {
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [loadingInitial, setLoadingInitial] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [partial, setPartial] = useState(false);
  const [missingAnalyses, setMissingAnalyses] = useState<string[]>([]);

  const fetchRecommendations = useCallback(
    async (generate: boolean) => {
      if (!propertyId) return;

      if (generate) {
        setIsGenerating(true);
      } else {
        setLoadingInitial(true);
      }

      setError(null);
      setPartial(false);
      setMissingAnalyses([]);

      try {
        const res = await fetch(
          `${API_URL}/api/recommendations/${propertyId}?generate=${generate ? 'true' : 'false'}`,
        );

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
        setError(err instanceof Error ? err.message : 'Network error');
      } finally {
        if (generate) {
          setIsGenerating(false);
        } else {
          setLoadingInitial(false);
        }
      }
    },
    [propertyId],
  );

  const loadRecommendations = useCallback(async () => {
    await fetchRecommendations(false);
  }, [fetchRecommendations]);

  const generateRecommendations = useCallback(async () => {
    await fetchRecommendations(true);
  }, [fetchRecommendations]);

  useEffect(() => {
    if (!propertyId) {
      setRecommendations([]);
      setLoadingInitial(false);
      setIsGenerating(false);
      setError(null);
      setPartial(false);
      setMissingAnalyses([]);
      return;
    }

    void loadRecommendations();
  }, [propertyId, loadRecommendations]);

  return {
    recommendations,
    loadingInitial,
    isGenerating,
    error,
    partial,
    missingAnalyses,
    loadRecommendations,
    generateRecommendations,
  };
}
