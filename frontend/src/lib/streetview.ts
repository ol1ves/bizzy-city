const STREET_VIEW_BASE = 'https://maps.googleapis.com/maps/api/streetview';

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

export function getStreetViewGallery(lat: number, lng: number): string[] {
  return [
    getStreetViewUrl(lat, lng, { heading: 0 }),
    getStreetViewUrl(lat, lng, { heading: 120 }),
    getStreetViewUrl(lat, lng, { heading: 240 }),
  ];
}
