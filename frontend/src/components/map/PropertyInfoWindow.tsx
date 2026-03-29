'use client';

import type { Property } from '@/lib/types';

interface PropertyInfoWindowProps {
  property: Property;
  onViewDetails: () => void;
}

export default function PropertyInfoWindow({
  property,
  onViewDetails,
}: PropertyInfoWindowProps) {
  return (
    <div className="max-w-[280px] p-3 font-sans">
      <h3 className="text-sm font-bold text-neutral-900 leading-tight">
        {property.address}
      </h3>

      <p className="mt-1 text-xs text-neutral-500">
        {property.city}, {property.state_code}
      </p>

      {property.square_footage && (
        <p className="mt-1.5 text-xs text-neutral-500">
          {property.square_footage.toLocaleString()} sqft
        </p>
      )}

      <button
        onClick={onViewDetails}
        className="mt-2 inline-flex items-center text-xs font-semibold text-accent-500 hover:text-accent-600 transition-colors"
      >
        View Details →
      </button>
    </div>
  );
}
