'use client';

import { useRecommendations } from '@/hooks/useRecommendations';
import type { Recommendation } from '@/lib/types';
import {
  computeRevenueTiers,
  formatCaptureRateDisplay,
  formatSurvivalProbabilityDisplay,
  parseRecommendationNumber,
  recommendationStableKey,
  type RevenueTier,
} from '@/lib/recommendationDisplay';
import Skeleton from '@/components/ui/Skeleton';
import { useEffect } from 'react';

interface RecommendationsSectionProps {
  propertyId: string;
}

function CircularScore({ score }: { score: number }) {
  const radius = 45;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;
  
  const getColor = (s: number) => {
    if (s >= 80) return '#22C55E';
    if (s >= 60) return '#FBBF24';
    return '#FB923C';
  };

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative w-28 h-28">
        <svg className="w-full h-full" viewBox="0 0 100 100">
          {/* Background circle */}
          <circle
            cx="50"
            cy="50"
            r={radius}
            fill="none"
            stroke="#E8E4E0"
            strokeWidth="4"
          />
          {/* Progress circle */}
          <circle
            cx="50"
            cy="50"
            r={radius}
            fill="none"
            stroke={getColor(score)}
            strokeWidth="4"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            strokeLinecap="round"
            style={{ transform: 'rotate(-90deg)', transformOrigin: '50px 50px' }}
            className="transition-all duration-300"
          />
          {/* Center text */}
          <text
            x="50"
            y="55"
            textAnchor="middle"
            className="fill-neutral-900 font-bold text-base"
            style={{ fontSize: '24px' }}
          >
            {score}
          </text>
        </svg>
      </div>
      <span className="text-xs font-medium text-neutral-500">/100</span>
    </div>
  );
}

function RecommendationCard({
  rec,
  revenueTier,
}: {
  rec: Recommendation;
  revenueTier: RevenueTier | null;
}) {
  const signals = rec.demand_signals ?? {};
  const signalKeys = Object.keys(signals);
  const conversionDisplay =
    formatCaptureRateDisplay(parseRecommendationNumber(rec.capture_rate)) ?? '—';
  const survivalDisplay =
    formatSurvivalProbabilityDisplay(
      parseRecommendationNumber(rec.survival_probability),
    ) ?? '—';
  const revenueDisplay = revenueTier ?? '—';

  return (
    <div className="rounded-xl border border-neutral-200 bg-white p-5 shadow-sm hover:shadow-md transition-shadow">
      <div className="flex gap-4">
        {/* Circular Score */}
        <div className="flex-shrink-0">
          <CircularScore score={rec.score} />
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2 mb-3">
            <div>
              <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-accent-100 text-xs font-bold text-accent-700 mr-2">
                {rec.rank}
              </span>
              <h4 className="inline text-base font-semibold text-neutral-900 capitalize">
                {rec.business_type}
              </h4>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-x-4 gap-y-2.5 text-sm sm:grid-cols-3 mb-3">
            <div>
              <div className="text-neutral-500 text-xs font-medium leading-snug">
                Walk-by conversion
              </div>
              <div className="mt-1 font-semibold tabular-nums text-neutral-900">
                {conversionDisplay}
              </div>
            </div>
            <div>
              <div className="text-neutral-500 text-xs font-medium leading-snug">
                5-year survival
              </div>
              <div className="mt-1 font-semibold tabular-nums text-neutral-900">
                {survivalDisplay}
              </div>
            </div>
            <div>
              <div className="text-neutral-500 text-xs font-medium leading-snug">
                Revenue potential
              </div>
              <div className="mt-1 font-semibold tracking-wider text-neutral-900">
                {revenueDisplay}
              </div>
            </div>
          </div>

          {(rec.summary ?? rec.reasoning) && (
            <p className="text-xs leading-relaxed text-neutral-600 mb-3">
              {rec.summary ?? rec.reasoning}
            </p>
          )}

          {signalKeys.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {signalKeys.map((key) => (
                <span
                  key={key}
                  className="inline-flex items-center rounded-full bg-accent-50 px-2.5 py-1 text-[10px] font-medium text-accent-700 border border-accent-200"
                  title={String(signals[key])}
                >
                  {key.replace(/_/g, ' ')}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div className="space-y-3">
      {[1, 2, 3].map((i) => (
        <div key={i} className="rounded-xl border border-neutral-200 p-5">
          <div className="flex gap-4">
            <Skeleton className="h-28 w-28 rounded-full flex-shrink-0" />
            <div className="flex-1">
              <Skeleton className="h-4 w-32 mb-3" />
              <Skeleton className="h-3 w-full mb-2" />
              <Skeleton className="h-3 w-3/4" />
            </div>
          </div>
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
  type = 'loading',
}: {
  title: string;
  description: string;
  type?: 'loading' | 'warning' | 'error';
}) {
  const bgClass =
    type === 'warning'
      ? 'bg-amber-50 border-amber-200'
      : type === 'error'
      ? 'bg-red-50 border-red-200'
      : 'bg-accent-50 border-accent-200';
  
  const textClass =
    type === 'warning'
      ? 'text-amber-900'
      : type === 'error'
      ? 'text-red-900'
      : 'text-accent-900';

  const descClass =
    type === 'warning'
      ? 'text-amber-800'
      : type === 'error'
      ? 'text-red-800'
      : 'text-accent-800';

  return (
    <div className={`mb-3 rounded-lg border ${bgClass} px-4 py-3`}>
      <div className={`flex items-center gap-2 text-sm font-medium ${textClass}`}>
        {type === 'loading' && <Spinner className="h-3.5 w-3.5" />}
        {type === 'warning' && (
          <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
          </svg>
        )}
        {type === 'error' && (
          <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
          </svg>
        )}
        <span>{title}</span>
      </div>
      <p className={`mt-1 text-xs leading-relaxed ${descClass}`}>
        {description}
      </p>
    </div>
  );
}

function Placeholder() {
  return (
    <div className="rounded-xl border border-dashed border-neutral-300 bg-neutral-50/50 p-8 text-center">
      <div className="text-4xl mb-3">🤖</div>
      <p className="text-base font-semibold text-neutral-700">
        No recommendations yet
      </p>
      <p className="mt-2 text-sm leading-relaxed text-neutral-500">
        Click &quot;Generate Recommendations&quot; to get AI-powered business
        suggestions based on neighborhood demand, competition gaps, and foot
        traffic analysis.
      </p>
    </div>
  );
}

function PartialData({
  missingAnalyses,
}: {
  missingAnalyses: string[];
}) {
  const labels: Record<string, string> = {
    restaurant_analysis: 'Restaurant analysis',
    retail_analysis: 'Retail analysis',
    foot_traffic_analysis: 'Foot traffic analysis',
    ml_predictions: 'ML predictions',
  };

  return (
    <div className="rounded-xl border border-dashed border-amber-200 bg-amber-50/50 p-8 text-center">
      <div className="text-4xl mb-3">📊</div>
      <p className="text-base font-semibold text-amber-900">
        Analysis in progress
      </p>
      <div className="mt-3 text-sm space-y-1">
        {missingAnalyses.map((key) => (
          <p key={key} className="text-amber-800">
            {labels[key] ?? key} — pending
          </p>
        ))}
      </div>
      <p className="mt-3 text-xs text-amber-700">
        Recommendations will be available once all analyses complete.
      </p>
    </div>
  );
}

function ActionsRow({
  canGenerate,
  refreshing,
  generating,
  onRefresh,
  onGenerate,
}: {
  canGenerate: boolean;
  refreshing: boolean;
  generating: boolean;
  onRefresh: () => void;
  onGenerate: () => void;
}) {
  const disableActions = refreshing || generating;

  return (
    <div className="mb-4 flex flex-wrap items-center gap-2">
      <button
        onClick={onRefresh}
        disabled={disableActions}
        className="inline-flex items-center justify-center gap-2 rounded-lg border border-neutral-300 bg-white px-3 py-2 text-xs font-semibold text-neutral-700 transition-colors hover:bg-neutral-50 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {refreshing ? (
          <>
            <Spinner className="h-3 w-3" />
            Refreshing...
          </>
        ) : (
          <>
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            Refresh Status
          </>
        )}
      </button>
      {canGenerate && (
        <button
          onClick={onGenerate}
          disabled={disableActions}
          className="inline-flex items-center justify-center gap-2 rounded-lg bg-accent-500 px-4 py-2 text-xs font-semibold text-white transition-colors hover:bg-accent-600 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {generating ? (
            <>
              <Spinner className="h-3 w-3" />
              Generating...
            </>
          ) : (
            <>
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
              Generate Recommendations
            </>
          )}
        </button>
      )}
    </div>
  );
}

export default function RecommendationsSection({ propertyId }: RecommendationsSectionProps) {
  const {
    recommendations,
    isInitialLoading,
    isRefreshing,
    isGenerating,
    error,
    partial,
    missingAnalyses,
    alreadyGenerated,
    loadRecommendations,
    generateRecommendations,
  } =
    useRecommendations(propertyId);

  const canGenerate =
    !partial &&
    recommendations.length === 0 &&
    !isInitialLoading &&
    !isRefreshing &&
    !isGenerating;

  useEffect(() => {
    // #region agent log
    fetch('http://127.0.0.1:7913/ingest/e737f7e8-dfd6-44cc-b7c5-6eba0ae2ca4a', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Debug-Session-Id': '65b61a',
      },
      body: JSON.stringify({
        sessionId: '65b61a',
        runId: 'rec-button-visibility',
        hypothesisId: 'H5',
        location: 'RecommendationsSection.tsx:derivedState',
        message: 'render derived button visibility state',
        data: {
          propertyId,
          partial,
          recommendationCount: recommendations.length,
          isInitialLoading,
          isRefreshing,
          isGenerating,
          canGenerate,
        },
        timestamp: Date.now(),
      }),
    }).catch(() => {});
    // #endregion
  }, [propertyId, partial, recommendations.length, isInitialLoading, isRefreshing, isGenerating, canGenerate]);

  const revenueTiersByKey =
    recommendations.length > 0 ? computeRevenueTiers(recommendations) : null;

  return (
    <div className="border-t border-neutral-200 px-5 py-4">
      <h3 className="text-xs font-bold uppercase tracking-wider text-neutral-400 mb-4">
        AI Recommendations
      </h3>

      <ActionsRow
        canGenerate={canGenerate}
        refreshing={isRefreshing}
        generating={isGenerating}
        onRefresh={loadRecommendations}
        onGenerate={generateRecommendations}
      />

      {isInitialLoading && recommendations.length === 0 && (
        <>
          <StatusCard
            title="Loading recommendations..."
            description="Checking for previously generated recommendations for this property."
          />
          <LoadingSkeleton />
        </>
      )}

      {isGenerating && (
        <StatusCard
          title="Generating recommendations..."
          description="Our AI is analyzing neighborhood demand signals and market data to find the best business opportunities."
        />
      )}

      {error && (
        <StatusCard
          title="Unable to load recommendations"
          description="Try refreshing the page or generating new recommendations."
          type="error"
        />
      )}

      {!isInitialLoading && !error && alreadyGenerated && recommendations.length > 0 && (
        <StatusCard
          title="Recommendations already generated"
          description="For demo safety, public regeneration is disabled once recommendations exist for this property."
          type="warning"
        />
      )}

      {!isInitialLoading && !error && partial && <PartialData missingAnalyses={missingAnalyses} />}

      {!isInitialLoading && !error && !partial && recommendations.length === 0 && <Placeholder />}

      {!isInitialLoading && !error && recommendations.length > 0 && (
        <div className="space-y-3">
          <p className="text-xs leading-relaxed text-neutral-400">
            Revenue symbols are relative rankings for this property, not actual dollar amounts.
          </p>
          {revenueTiersByKey &&
            recommendations.map((rec) => {
              const key = recommendationStableKey(rec);
              return (
                <RecommendationCard
                  key={key}
                  rec={rec}
                  revenueTier={revenueTiersByKey.get(key) ?? null}
                />
              );
            })}
        </div>
      )}
    </div>
  );
}
