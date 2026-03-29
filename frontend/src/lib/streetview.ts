const STREET_VIEW_BASE = 'https://maps.googleapis.com/maps/api/streetview';

/** Headings (degrees) for four views around the location. */
export const STREET_VIEW_HEADINGS = [0, 90, 180, 270] as const;

/** Labels aligned with `STREET_VIEW_HEADINGS` indices. */
export const STREET_VIEW_CARDINAL_LABELS = ['North', 'East', 'South', 'West'] as const;

export function getStreetViewUrl(
  lat: number,
  lng: number,
  options?: {
    heading?: number;
    pitch?: number;
    fov?: number;
    size?: string;
  }
): string {
  const { heading = 0, pitch = 10, fov = 90, size = '800x600' } = options ?? {};
  const params = new URLSearchParams({
    size,
    location: `${lat},${lng}`,
    heading: String(heading),
    pitch: String(pitch),
    fov: String(fov),
    key: process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY!,
  });
  return `${STREET_VIEW_BASE}?${params}`;
}

/** First `count` Street View URLs using distinct headings from `STREET_VIEW_HEADINGS`. */
export function getStreetViewPaddingUrls(lat: number, lng: number, count: number): string[] {
  return STREET_VIEW_HEADINGS.slice(0, count).map((heading) =>
    getStreetViewUrl(lat, lng, { heading })
  );
}

export function getStreetViewGallery(lat: number, lng: number): string[] {
  return getStreetViewPaddingUrls(lat, lng, STREET_VIEW_HEADINGS.length);
}
