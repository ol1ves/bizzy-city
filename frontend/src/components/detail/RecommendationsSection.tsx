'use client';

import { useRecommendations } from '@/hooks/useRecommendations';
import type { Recommendation } from '@/lib/types';
import Skeleton from '@/components/ui/Skeleton';

interface RecommendationsSectionProps {
  propertyId: string;
}

function ScoreBar({ score }: { score: number }) {
  const color =
    score >= 80 ? 'bg-green-500' : score >= 60 ? 'bg-yellow-500' : 'bg-orange-500';
  return (
    <div className="flex items-center gap-2">
      <div className="h-2 flex-1 rounded-full bg-gray-100 overflow-hidden">
        <div
          className={`h-full rounded-full ${color}`}
          style={{ width: `${score}%` }}
        />
      </div>
      <span className="text-xs font-bold text-gray-700 tabular-nums w-10 text-right">
        {score}/100
      </span>
    </div>
  );
}

function RecommendationCard({ rec }: { rec: Recommendation }) {
  const signals = rec.demand_signals ?? {};
  const signalKeys = Object.keys(signals);

  return (
    <div className="rounded-xl border border-gray-100 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex items-center gap-2">
          <span className="flex h-6 w-6 items-center justify-center rounded-full bg-brand-50 text-xs font-bold text-brand-700">
            {rec.rank}
          </span>
          <h4 className="text-sm font-semibold text-gray-900 capitalize">
            {rec.business_type}
          </h4>
        </div>
      </div>

      <ScoreBar score={rec.score} />

      {rec.reasoning && (
        <p className="mt-2 text-xs leading-relaxed text-gray-600">
          {rec.reasoning}
        </p>
      )}

      {signalKeys.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {signalKeys.map((key) => (
            <span
              key={key}
              className="inline-flex items-center rounded-full bg-brand-50 px-2 py-0.5 text-[10px] font-medium text-brand-700"
              title={String(signals[key])}
            >
              {key.replace(/_/g, ' ')}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div className="space-y-3">
      {[1, 2, 3].map((i) => (
        <div key={i} className="rounded-xl border border-gray-100 p-4">
          <div className="flex items-center gap-2 mb-3">
            <Skeleton className="h-6 w-6 rounded-full" />
            <Skeleton className="h-4 w-32" />
          </div>
          <Skeleton className="h-2 w-full rounded-full" />
          <Skeleton className="mt-3 h-3 w-full" />
          <Skeleton className="mt-1 h-3 w-3/4" />
        </div>
      ))}
    </div>
  );
}

function Placeholder() {
  return (
    <div className="rounded-xl border border-dashed border-gray-200 bg-gray-50/50 p-6 text-center">
      <div className="text-3xl mb-3">🤖</div>
      <p className="text-sm font-medium text-gray-700">
        Recommendations for this property haven&apos;t been generated yet.
      </p>
      <button
        disabled
        className="mt-4 w-full rounded-lg bg-gray-200 px-4 py-2.5 text-sm font-semibold text-gray-400 cursor-not-allowed"
        title="Coming soon — backend not yet available"
      >
        Generate Recommendations
      </button>
      <p className="mt-2 text-[11px] text-gray-400">Coming soon</p>
      <p className="mt-3 text-xs text-gray-400 leading-relaxed">
        Our AI analyzes neighborhood demand, competition gaps, and foot traffic
        to suggest the best business types for this location.
      </p>
    </div>
  );
}

export default function RecommendationsSection({ propertyId }: RecommendationsSectionProps) {
  const { recommendations, loading, error } = useRecommendations(propertyId);

  return (
    <div className="px-5 py-4 border-t border-gray-100">
      <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-3">
        AI Recommendations
      </h3>

      {loading && <LoadingSkeleton />}

      {error && (
        <p className="text-sm text-red-500">
          Failed to load recommendations.{' '}
          <button
            className="underline hover:text-red-700"
            onClick={() => window.location.reload()}
          >
            Retry
          </button>
        </p>
      )}

      {!loading && !error && recommendations.length === 0 && <Placeholder />}

      {!loading && !error && recommendations.length > 0 && (
        <div className="space-y-3">
          {recommendations.map((rec) => (
            <RecommendationCard key={rec.id} rec={rec} />
          ))}
        </div>
      )}
    </div>
  );
}
