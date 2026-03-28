'use client';

import { useState } from 'react';
import { getStreetViewGallery } from '@/lib/streetview';

interface StreetViewGalleryProps {
  lat: number;
  lng: number;
}

export default function StreetViewGallery({ lat, lng }: StreetViewGalleryProps) {
  const urls = getStreetViewGallery(lat, lng);
  const [heroIndex, setHeroIndex] = useState(0);

  const labels = ['Front', 'Right', 'Left'];

  return (
    <div>
      {/* Hero image */}
      <div className="relative w-full h-[280px] bg-gray-100 overflow-hidden">
        <img
          src={urls[heroIndex]}
          alt={`Street view — ${labels[heroIndex]}`}
          className="h-full w-full object-cover"
        />
      </div>

      {/* Thumbnails */}
      <div className="flex gap-1 p-1 bg-gray-50">
        {urls.map((url, i) => (
          <button
            key={i}
            onClick={() => setHeroIndex(i)}
            className={`relative flex-1 h-16 overflow-hidden rounded transition-all ${
              heroIndex === i
                ? 'ring-2 ring-brand-500 ring-offset-1'
                : 'opacity-70 hover:opacity-100'
            }`}
          >
            <img
              src={url}
              alt={`Street view — ${labels[i]}`}
              className="h-full w-full object-cover"
              loading="lazy"
            />
          </button>
        ))}
      </div>
    </div>
  );
}
