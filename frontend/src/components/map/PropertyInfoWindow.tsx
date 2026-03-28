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
      <h3 className="text-sm font-bold text-gray-900 leading-tight">
        {property.address}
      </h3>

      {property.neighborhood && (
        <div className="mt-1.5">
          <span className="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600">
            {property.neighborhood}
          </span>
        </div>
      )}

      {property.square_footage && (
        <p className="mt-1.5 text-xs text-gray-500">
          {property.square_footage.toLocaleString()} sqft
        </p>
      )}

      <button
        onClick={onViewDetails}
        className="mt-2 inline-flex items-center text-xs font-semibold text-brand-600 hover:text-brand-700 transition-colors"
      >
        View Details →
      </button>
    </div>
  );
}
