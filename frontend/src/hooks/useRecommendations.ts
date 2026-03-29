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

function debugRec(payload: {
  runId: string;
  hypothesisId: string;
  location: string;
  message: string;
  data: Record<string, unknown>;
}) {
  // #region agent log
  fetch('http://127.0.0.1:7913/ingest/e737f7e8-dfd6-44cc-b7c5-6eba0ae2ca4a', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Debug-Session-Id': '65b61a',
    },
    body: JSON.stringify({
      sessionId: '65b61a',
      runId: payload.runId,
      hypothesisId: payload.hypothesisId,
      location: payload.location,
      message: payload.message,
      data: payload.data,
      timestamp: Date.now(),
    }),
  }).catch(() => {});
  // #endregion
}

export function useRecommendations(propertyId: string | null) {
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [isInitialLoading, setIsInitialLoading] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [partial, setPartial] = useState(false);
  const [missingAnalyses, setMissingAnalyses] = useState<string[]>([]);

  const fetchRecommendations = useCallback(
    async (mode: 'initial' | 'refresh' | 'generate') => {
      if (!propertyId) return;

      const isGenerate = mode === 'generate';
      const isInitial = mode === 'initial';

      if (isGenerate) {
        setIsGenerating(true);
      } else if (isInitial) {
        setIsInitialLoading(true);
      } else {
        setIsRefreshing(true);
      }

      setError(null);
      debugRec({
        runId: 'rec-button-visibility',
        hypothesisId: 'H1',
        location: 'useRecommendations.ts:fetchRecommendations:start',
        message: 'request started and pre-request state reset',
        data: { mode, propertyId },
      });

      try {
        const res = await fetch(
          `${API_URL}/api/recommendations/${propertyId}?generate=${isGenerate ? 'true' : 'false'}`,
        );

        if (res.status === 202) {
          const body = await res.json();
          setPartial(true);
          setMissingAnalyses(body.missing_analyses ?? []);
          setRecommendations([]);
          debugRec({
            runId: 'rec-button-visibility',
            hypothesisId: 'H2',
            location: 'useRecommendations.ts:fetchRecommendations:202',
            message: 'backend returned missing analyses',
            data: {
              mode,
              missingAnalysesCount: Array.isArray(body.missing_analyses)
                ? body.missing_analyses.length
                : 0,
            },
          });
        } else if (!res.ok) {
          const body = await res.json().catch(() => null);
          setError(body?.detail ?? `Request failed (${res.status})`);
          debugRec({
            runId: 'rec-button-visibility',
            hypothesisId: 'H4',
            location: 'useRecommendations.ts:fetchRecommendations:error',
            message: 'backend returned non-ok response',
            data: { mode, status: res.status },
          });
        } else {
          const body = await res.json();
          setPartial(false);
          setMissingAnalyses([]);
          setRecommendations(body.recommendations ?? []);
          debugRec({
            runId: 'rec-button-visibility',
            hypothesisId: 'H3',
            location: 'useRecommendations.ts:fetchRecommendations:ok',
            message: 'backend returned recommendations payload',
            data: {
              mode,
              recommendationCount: Array.isArray(body.recommendations)
                ? body.recommendations.length
                : 0,
            },
          });
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Network error');
      } finally {
        if (isGenerate) {
          setIsGenerating(false);
        } else if (isInitial) {
          setIsInitialLoading(false);
        } else {
          setIsRefreshing(false);
        }
      }
    },
    [propertyId],
  );

  const loadRecommendations = useCallback(async () => {
    await fetchRecommendations('refresh');
  }, [fetchRecommendations]);

  const generateRecommendations = useCallback(async () => {
    await fetchRecommendations('generate');
  }, [fetchRecommendations]);

  useEffect(() => {
    if (!propertyId) {
      setRecommendations([]);
      setIsInitialLoading(false);
      setIsRefreshing(false);
      setIsGenerating(false);
      setError(null);
      setPartial(false);
      setMissingAnalyses([]);
      return;
    }

    void fetchRecommendations('initial');
  }, [propertyId, fetchRecommendations]);

  return {
    recommendations,
    isInitialLoading,
    isRefreshing,
    isGenerating,
    error,
    partial,
    missingAnalyses,
    loadRecommendations,
    generateRecommendations,
  };
}
