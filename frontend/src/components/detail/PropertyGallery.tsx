'use client';

import { useState } from 'react';
import { usePropertyImages } from '@/hooks/usePropertyImages';
import { getStreetViewGallery } from '@/lib/streetview';
import Skeleton from '@/components/ui/Skeleton';

interface PropertyGalleryProps {
  propertyId: string;
  lat: number;
  lng: number;
}

export default function PropertyGallery({ propertyId, lat, lng }: PropertyGalleryProps) {
  const { images, loading } = usePropertyImages(propertyId);
  const [heroIndex, setHeroIndex] = useState(0);

  if (loading) {
    return (
      <div>
        <Skeleton className="w-full h-[280px]" />
        <div className="flex gap-1 p-1 bg-gray-50">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="flex-1 h-16 rounded" />
          ))}
        </div>
      </div>
    );
  }

  const hasUploadedImages = images.length > 0;
  const urls = hasUploadedImages
    ? images.map((img) => img.url)
    : getStreetViewGallery(lat, lng);

  const streetViewLabels = ['Front', 'Right', 'Left'];
  const safeIndex = Math.min(heroIndex, urls.length - 1);

  return (
    <div>
      <div className="relative w-full h-[280px] bg-gray-100 overflow-hidden">
        <img
          src={urls[safeIndex]}
          alt={hasUploadedImages ? `Property photo ${safeIndex + 1}` : `Street view — ${streetViewLabels[safeIndex]}`}
          className="h-full w-full object-cover"
        />
        {!hasUploadedImages && (
          <span className="absolute bottom-2 left-2 rounded bg-black/50 px-2 py-0.5 text-[10px] text-white">
            Street View
          </span>
        )}
      </div>

      {urls.length > 1 && (
        <div className="flex gap-1 p-1 bg-gray-50">
          {urls.map((url, i) => (
            <button
              key={i}
              onClick={() => setHeroIndex(i)}
              className={`relative flex-1 h-16 overflow-hidden rounded transition-all ${
                safeIndex === i
                  ? 'ring-2 ring-brand-500 ring-offset-1'
                  : 'opacity-70 hover:opacity-100'
              }`}
            >
              <img
                src={url}
                alt={hasUploadedImages ? `Property photo ${i + 1}` : `Street view — ${streetViewLabels[i]}`}
                className="h-full w-full object-cover"
                loading="lazy"
              />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
