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

function Spinner({ className = 'h-4 w-4' }: { className?: string }) {
  return (
    <span
      className={`${className} inline-block animate-spin rounded-full border-2 border-current border-r-transparent`}
      aria-hidden="true"
    />
  );
}

function StatusCard({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="mb-3 rounded-lg border border-brand-100 bg-brand-50 px-3 py-2 text-brand-800">
      <div className="flex items-center gap-2 text-sm font-medium">
        <Spinner />
        <span>{title}</span>
      </div>
      <p className="mt-1 text-xs text-brand-700">{description}</p>
    </div>
  );
}

function Placeholder({ onGenerate, generating }: { onGenerate: () => void; generating: boolean }) {
  return (
    <div className="rounded-xl border border-dashed border-gray-200 bg-gray-50/50 p-6 text-center">
      <div className="text-3xl mb-3">🤖</div>
      <p className="text-sm font-medium text-gray-700">
        Recommendations for this property haven&apos;t been generated yet.
      </p>
      <button
        onClick={onGenerate}
        disabled={generating}
        className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-lg bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {generating ? (
          <>
            <Spinner className="h-3.5 w-3.5" />
            Running recommendation engine...
          </>
        ) : (
          'Run Recommendations'
        )}
      </button>
      <p className="mt-3 text-xs text-gray-400 leading-relaxed">
        Our AI analyzes neighborhood demand, competition gaps, and foot traffic
        to suggest the best business types for this location.
      </p>
    </div>
  );
}

function PartialData({
  missingAnalyses,
  onRefresh,
  refreshing,
}: {
  missingAnalyses: string[];
  onRefresh: () => void;
  refreshing: boolean;
}) {
  const labels: Record<string, string> = {
    restaurant_analysis: 'Restaurant analysis',
    retail_analysis: 'Retail analysis',
    foot_traffic_analysis: 'Foot traffic analysis',
    ml_predictions: 'ML predictions',
  };

  return (
    <div className="rounded-xl border border-dashed border-amber-200 bg-amber-50/50 p-6 text-center">
      <div className="text-3xl mb-3">📊</div>
      <p className="text-sm font-medium text-gray-700">
        Analysis data is still being collected for this property.
      </p>
      <div className="mt-3 space-y-1">
        {missingAnalyses.map((key) => (
          <p key={key} className="text-xs text-amber-700">
            &#x2022; {labels[key] ?? key} — pending
          </p>
        ))}
      </div>
      <p className="mt-3 text-xs text-gray-400 leading-relaxed">
        Recommendations will be available once all analyses are complete.
      </p>
      <button
        onClick={onRefresh}
        disabled={refreshing}
        className="mt-4 inline-flex items-center justify-center gap-2 rounded-lg border border-amber-300 bg-white px-3 py-2 text-xs font-semibold text-amber-800 transition-colors hover:bg-amber-100 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {refreshing ? (
          <>
            <Spinner className="h-3 w-3" />
            Checking...
          </>
        ) : (
          'Refresh Status'
        )}
      </button>
    </div>
  );
}

export default function RecommendationsSection({ propertyId }: RecommendationsSectionProps) {
  const {
    recommendations,
    loadingInitial,
    isGenerating,
    error,
    partial,
    missingAnalyses,
    loadRecommendations,
    generateRecommendations,
  } =
    useRecommendations(propertyId);

  return (
    <div className="px-5 py-4 border-t border-gray-100">
      <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-3">
        AI Recommendations
      </h3>

      {loadingInitial && recommendations.length === 0 && (
        <>
          <StatusCard
            title="Checking saved recommendations..."
            description="Loading previously generated recommendations for this property."
          />
          <LoadingSkeleton />
        </>
      )}

      {isGenerating && (
        <StatusCard
          title="Running recommendation engine..."
          description="This can take a few moments while we evaluate demand and foot traffic signals."
        />
      )}

      {error && (
        <p className="text-sm text-red-500">
          Failed to load recommendations.{' '}
          <button
            className="underline hover:text-red-700"
            onClick={loadRecommendations}
          >
            Retry
          </button>
        </p>
      )}

      {!loadingInitial && !error && partial && (
        <PartialData
          missingAnalyses={missingAnalyses}
          onRefresh={loadRecommendations}
          refreshing={loadingInitial}
        />
      )}

      {!loadingInitial && !error && !partial && recommendations.length === 0 && (
        <Placeholder onGenerate={generateRecommendations} generating={isGenerating} />
      )}

      {!loadingInitial && !error && recommendations.length > 0 && (
        <div className="space-y-3">
          {recommendations.map((rec) => (
            <RecommendationCard key={rec.id ?? `${rec.rank}-${rec.business_type}`} rec={rec} />
          ))}
        </div>
      )}
    </div>
  );
}
