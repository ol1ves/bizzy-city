'use client';

import { useState, useCallback } from 'react';
import { useProperties } from '@/hooks/useProperties';
import type { Property } from '@/lib/types';
import PropertyMap from '@/components/map/PropertyMap';
import PropertyDetailPanel from '@/components/detail/PropertyDetailPanel';
import Skeleton from '@/components/ui/Skeleton';

export default function Home() {
  const { properties, loading, error } = useProperties();
  const [selectedProperty, setSelectedProperty] = useState<Property | null>(null);

  const handleSelectProperty = useCallback((property: Property) => {
    setSelectedProperty(property);
  }, []);

  const handleClosePanel = useCallback(() => {
    setSelectedProperty(null);
  }, []);

  if (error) {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-gray-50">
        <div className="text-center max-w-md px-6">
          <div className="text-5xl mb-4">🏗️</div>
          <h1 className="text-xl font-bold text-gray-900 mb-2">
            Unable to load properties
          </h1>
          <p className="text-sm text-gray-500 mb-4">
            Check your connection and Supabase configuration.
          </p>
          <button
            onClick={() => window.location.reload()}
            className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="relative h-screen w-screen">
      {/* Logo */}
      <div className="absolute top-4 left-4 z-30 pointer-events-none">
        <div className="pointer-events-auto rounded-xl bg-white/80 backdrop-blur-md px-4 py-2.5 shadow-lg">
          <h1 className="text-lg font-bold text-gray-900 tracking-tight">
            BusiCity
          </h1>
          <p className="text-[11px] text-gray-500 -mt-0.5">
            Find the right business for any space.
          </p>
        </div>
      </div>

      {/* Loading overlay */}
      {loading && (
        <div className="absolute inset-0 z-20 flex items-center justify-center bg-gray-50">
          <div className="flex flex-col items-center gap-3">
            <Skeleton className="h-8 w-48" />
            <p className="text-sm text-gray-400">Loading properties...</p>
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
    </div>
  );
}
