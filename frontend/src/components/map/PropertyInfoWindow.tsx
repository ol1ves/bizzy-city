'use client';

import type { Property } from '@/lib/types';
import { getStreetViewUrl } from '@/lib/streetview';

interface PropertyInfoWindowProps {
  property: Property;
  onViewDetails: () => void;
}

export default function PropertyInfoWindow({
  property,
  onViewDetails,
}: PropertyInfoWindowProps) {
  const thumbnailUrl = getStreetViewUrl(property.latitude, property.longitude, {
    size: '200x120',
    heading: 0,
    pitch: 5,
    fov: 100,
  });

  return (
    <div className="w-[240px] overflow-hidden rounded-lg bg-white font-sans shadow-sm">
      {/* Image Preview */}
      <div className="relative h-[100px] w-full overflow-hidden bg-neutral-100">
        <img
          src={thumbnailUrl}
          alt={`Street view of ${property.address}`}
          className="h-full w-full object-cover"
          loading="eager"
        />
      </div>

      {/* Content */}
      <div className="p-3">
        <h3 className="text-sm font-semibold text-neutral-900 leading-tight line-clamp-2">
          {property.address}
        </h3>

        <p className="mt-1 text-xs text-neutral-500">
          {property.city}, {property.state_code}
        </p>

        {property.square_footage && (
          <p className="mt-1 text-xs text-neutral-400">
            {property.square_footage.toLocaleString()} sqft
          </p>
        )}

        <button
          onClick={onViewDetails}
          className="mt-2.5 w-full rounded-md bg-neutral-900 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-neutral-800"
        >
          View Details
        </button>
      </div>
    </div>
  );
}
