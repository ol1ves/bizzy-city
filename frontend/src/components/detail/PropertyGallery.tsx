'use client';

import { useEffect, useMemo, useState } from 'react';
import { usePropertyImages } from '@/hooks/usePropertyImages';
import {
  getStreetViewPaddingUrls,
  STREET_VIEW_CARDINAL_LABELS,
} from '@/lib/streetview';
import Skeleton from '@/components/ui/Skeleton';

const GALLERY_SIZE = 4;

type GallerySlot =
  | { url: string; source: 'storage'; photoIndex: number }
  | { url: string; source: 'streetview'; svLabelIndex: number };

interface PropertyGalleryProps {
  propertyId: string;
  lat: number;
  lng: number;
}

function buildGallerySlots(
  storageUrls: string[],
  lat: number,
  lng: number
): GallerySlot[] {
  const trimmed = storageUrls.slice(0, GALLERY_SIZE);
  const padCount = GALLERY_SIZE - trimmed.length;
  const padUrls = padCount > 0 ? getStreetViewPaddingUrls(lat, lng, padCount) : [];

  const slots: GallerySlot[] = trimmed.map((url, i) => ({
    url,
    source: 'storage',
    photoIndex: i + 1,
  }));
  for (let i = 0; i < padCount; i++) {
    slots.push({
      url: padUrls[i],
      source: 'streetview',
      svLabelIndex: i,
    });
  }
  return slots;
}

export default function PropertyGallery({ propertyId, lat, lng }: PropertyGalleryProps) {
  const { images, loading } = usePropertyImages(propertyId);
  const [heroIndex, setHeroIndex] = useState(0);

  useEffect(() => {
    setHeroIndex(0);
  }, [propertyId]);

  const slots = useMemo(() => {
    const storageUrls = images.map((img) => img.url);
    return buildGallerySlots(storageUrls, lat, lng);
  }, [images, lat, lng]);

  if (loading) {
    return (
      <div>
        <Skeleton className="w-full h-[280px]" />
        <div className="flex gap-1 p-1 bg-gray-50">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="flex-1 h-16 rounded" />
          ))}
        </div>
      </div>
    );
  }

  const safeIndex = Math.min(heroIndex, slots.length - 1);
  const active = slots[safeIndex];

  const heroAlt =
    active.source === 'storage'
      ? `Property photo ${active.photoIndex}`
      : `Street view — ${STREET_VIEW_CARDINAL_LABELS[active.svLabelIndex]}`;

  return (
    <div>
      <div className="relative w-full h-[280px] bg-gray-100 overflow-hidden">
        <img
          src={active.url}
          alt={heroAlt}
          className="h-full w-full object-cover"
        />
        {active.source === 'streetview' && (
          <span className="absolute bottom-2 left-2 rounded bg-black/50 px-2 py-0.5 text-[10px] text-white">
            Street View
          </span>
        )}
      </div>

      <div className="flex gap-1 p-1 bg-gray-50">
        {slots.map((slot, i) => {
          const alt =
            slot.source === 'storage'
              ? `Property photo ${slot.photoIndex}`
              : `Street view — ${STREET_VIEW_CARDINAL_LABELS[slot.svLabelIndex]}`;
          return (
            <button
              key={i}
              type="button"
              onClick={() => setHeroIndex(i)}
              className={`relative flex-1 h-16 overflow-hidden rounded transition-all ${
                safeIndex === i
                  ? 'ring-2 ring-brand-500 ring-offset-1'
                  : 'opacity-70 hover:opacity-100'
              }`}
            >
              <img
                src={slot.url}
                alt={alt}
                className="h-full w-full object-cover"
                loading="lazy"
              />
              {slot.source === 'streetview' && (
                <span className="pointer-events-none absolute bottom-0.5 left-0.5 rounded bg-black/50 px-1 py-px text-[8px] leading-none text-white">
                  SV
                </span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
