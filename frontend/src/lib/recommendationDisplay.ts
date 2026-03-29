import type { Recommendation } from '@/lib/types';

export function recommendationStableKey(rec: Recommendation): string {
  return rec.id ?? `${rec.rank}-${rec.business_type}`;
}

export function parseRecommendationNumber(
  value: number | string | null | undefined,
): number | null {
  if (value === null || value === undefined) return null;
  if (typeof value === 'number') {
    return Number.isFinite(value) ? value : null;
  }
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

/** ML values stored as 0–1 fractions; values > 1 are treated as already a percent. */
function formatFractionAsPercent(value: number | null): string | null {
  if (value === null) return null;
  const pct = value > 1 ? value : value * 100;
  if (!Number.isFinite(pct)) return null;
  return `${pct.toFixed(1)}%`;
}

export function formatCaptureRateDisplay(rate: number | null): string | null {
  return formatFractionAsPercent(rate);
}

export function formatSurvivalProbabilityDisplay(p: number | null): string | null {
  return formatFractionAsPercent(p);
}

export type RevenueTier = '$' | '$$' | '$$$';

export function computeRevenueTiers(
  recommendations: Recommendation[],
): Map<string, RevenueTier | null> {
  const keys = recommendations.map((r) => recommendationStableKey(r));
  const empty = new Map<string, RevenueTier | null>(
    keys.map((k) => [k, null]),
  );

  const withValues = recommendations
    .map((rec) => ({
      key: recommendationStableKey(rec),
      v: parseRecommendationNumber(rec.estimated_annual_revenue),
    }))
    .filter((e): e is { key: string; v: number } => e.v !== null);

  if (withValues.length === 0) return empty;

  const sorted = [...withValues].sort((a, b) => {
    if (a.v !== b.v) return a.v - b.v;
    return a.key.localeCompare(b.key);
  });

  const n = sorted.length;
  if (n === 1) {
    empty.set(sorted[0].key, '$$');
    return empty;
  }

  const third = Math.max(1, Math.floor(n / 3));
  for (let i = 0; i < n; i++) {
    let tier: RevenueTier;
    if (i < third) tier = '$';
    else if (i < 2 * third) tier = '$$';
    else tier = '$$$';
    empty.set(sorted[i].key, tier);
  }

  return empty;
}
