'use client';

import { useEffect, useState } from 'react';
import { getSupabase, getImageUrl } from '@/lib/supabase';
import type { PropertyImage } from '@/lib/types';

export interface PropertyImageWithUrl extends PropertyImage {
  url: string;
}

export function usePropertyImages(propertyId: string | null) {
  const [images, setImages] = useState<PropertyImageWithUrl[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!propertyId) {
      setImages([]);
      return;
    }

    async function fetchImages() {
      setLoading(true);
      setError(null);

      const supabase = getSupabase();
      const { data, error: queryError } = await supabase
        .from('property_images')
        .select('*')
        .eq('property_id', propertyId)
        .order('display_order');

      if (queryError) {
        setError(queryError.message);
      } else {
        const withUrls = (data ?? []).map((img: PropertyImage) => ({
          ...img,
          url: getImageUrl(img.storage_path),
        }));
        setImages(withUrls);
      }
      setLoading(false);
    }

    fetchImages();
  }, [propertyId]);

  return { images, loading, error };
}
