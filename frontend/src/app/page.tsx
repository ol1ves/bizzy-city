'use client';

import { useState, useCallback, useEffect } from 'react';
import { useProperties } from '@/hooks/useProperties';
import type { Property } from '@/lib/types';
import PropertyMap from '@/components/map/PropertyMap';
import PropertyDetailPanel from '@/components/detail/PropertyDetailPanel';
import Header from '@/components/Header';
import WelcomeModal from '@/components/WelcomeModal';
import Skeleton from '@/components/ui/Skeleton';

export default function Home() {
  const { properties, loading, error } = useProperties();
  const [selectedProperty, setSelectedProperty] = useState<Property | null>(null);
  const [showWelcome, setShowWelcome] = useState(false);

  // Initialize welcome modal on first visit
  useEffect(() => {
    const hasVisited = localStorage.getItem('bizicity-visited');
    if (!hasVisited) {
      setShowWelcome(true);
      localStorage.setItem('bizicity-visited', 'true');
    }
  }, []);

  const handleSelectProperty = useCallback((property: Property) => {
    setSelectedProperty(property);
  }, []);

  const handleClosePanel = useCallback(() => {
    setSelectedProperty(null);
  }, []);

  if (error) {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-neutral-50">
        <div className="text-center max-w-md px-6">
          <div className="text-5xl mb-4">🏗️</div>
          <h1 className="text-xl font-bold text-neutral-900 mb-2">
            Unable to load properties
          </h1>
          <p className="text-sm text-neutral-500 mb-4">
            Check your connection and Supabase configuration.
          </p>
          <button
            onClick={() => window.location.reload()}
            className="rounded-lg bg-accent-500 px-4 py-2 text-sm font-semibold text-white hover:bg-accent-600 transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="relative h-screen w-screen">
      {/* Header */}
      <Header />

      {/* Loading overlay */}
      {loading && (
        <div className="absolute inset-0 z-20 flex items-center justify-center bg-neutral-50">
          <div className="flex flex-col items-center gap-3">
            <Skeleton className="h-8 w-48" />
            <p className="text-sm text-neutral-400">Loading properties...</p>
          </div>
        </div>
      )}

      {/* Map */}
      <PropertyMap
        properties={properties}
        onSelectProperty={handleSelectProperty}
      />

      {/* Detail Panel */}
      <PropertyDetailPanel
        property={selectedProperty}
        onClose={handleClosePanel}
      />

      {/* Welcome Modal */}
      <WelcomeModal open={showWelcome} onClose={() => setShowWelcome(false)} />
    </div>
  );
}
