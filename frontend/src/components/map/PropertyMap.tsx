'use client';

import { useState, useCallback, useEffect, useRef } from 'react';
import { Map, AdvancedMarker, InfoWindow, useMap } from '@vis.gl/react-google-maps';
import { MarkerClusterer, SuperClusterAlgorithm } from '@googlemaps/markerclusterer';
import type { Property } from '@/lib/types';
import { MAP_DEFAULT_CENTER, MAP_DEFAULT_ZOOM } from '@/constants';
import PropertyPin from './PropertyPin';
import PropertyInfoWindow from './PropertyInfoWindow';

interface PropertyMapProps {
  properties: Property[];
  onSelectProperty: (property: Property) => void;
}

// Custom cluster renderer
function createClusterIcon(count: number): HTMLElement {
  const div = document.createElement('div');
  div.className = 'cluster-marker';
  div.innerHTML = `
    <div style="
      display: flex;
      align-items: center;
      justify-content: center;
      width: 40px;
      height: 40px;
      background: #E8654A;
      border: 3px solid white;
      border-radius: 50%;
      color: white;
      font-weight: 600;
      font-size: 14px;
      font-family: 'Plus Jakarta Sans', system-ui, sans-serif;
      box-shadow: 0 2px 6px rgba(0,0,0,0.3);
      cursor: pointer;
    ">${count}</div>
  `;
  return div;
}

function MapMarkers({
  properties,
  onSelectProperty,
}: PropertyMapProps) {
  const map = useMap();
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);
  const clustererRef = useRef<MarkerClusterer | null>(null);
  const markersRef = useRef<Map<string, google.maps.marker.AdvancedMarkerElement>>(new Map());

  const activeProperty = properties.find((p) => p.id === activeId);

  const handleMarkerClick = useCallback(
    (property: Property) => {
      if (activeId === property.id) {
        onSelectProperty(property);
      } else {
        setActiveId(property.id);
      }
    },
    [activeId, onSelectProperty]
  );

  // Initialize clusterer
  useEffect(() => {
    if (!map) return;

    if (!clustererRef.current) {
      clustererRef.current = new MarkerClusterer({
        map,
        algorithm: new SuperClusterAlgorithm({ radius: 80 }),
        renderer: {
          render: ({ count, position }) => {
            return new google.maps.marker.AdvancedMarkerElement({
              position,
              content: createClusterIcon(count),
              zIndex: 100,
            });
          },
        },
      });
    }

    return () => {
      if (clustererRef.current) {
        clustererRef.current.clearMarkers();
      }
    };
  }, [map]);

  // Update markers in clusterer
  useEffect(() => {
    if (!map || !clustererRef.current) return;

    // Clear existing markers
    clustererRef.current.clearMarkers();
    markersRef.current.clear();

    // Create new markers
    const markers = properties.map((property) => {
      const pinElement = document.createElement('div');
      pinElement.innerHTML = `
        <div style="cursor: pointer; filter: drop-shadow(0 2px 4px rgba(0,0,0,0.2));">
          <svg width="32" height="40" viewBox="0 0 32 40" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M16 0C7.16 0 0 6.72 0 15C0 26.25 16 40 16 40S32 26.25 32 15C32 6.72 24.84 0 16 0Z" fill="${getPinColorFromScore(property.top_rec_score)}"/>
            <rect x="9" y="9" width="14" height="11" rx="1.5" fill="white" opacity="0.9"/>
            <path d="M9 14.5h14" stroke="${getPinColorFromScore(property.top_rec_score)}" stroke-width="1"/>
            <rect x="13" y="16" width="6" height="4" rx="0.5" fill="${getPinColorFromScore(property.top_rec_score)}" opacity="0.3"/>
          </svg>
        </div>
      `;

      const marker = new google.maps.marker.AdvancedMarkerElement({
        position: { lat: property.latitude, lng: property.longitude },
        content: pinElement,
        title: property.address,
      });

      marker.addListener('click', () => handleMarkerClick(property));
      markersRef.current.set(property.id, marker);

      return marker;
    });

    clustererRef.current.addMarkers(markers);
  }, [map, properties, handleMarkerClick]);

  // Don't render markers until the map is ready
  if (!map) return null;

  return (
    <>
      {activeProperty && (
        <InfoWindow
          position={{
            lat: activeProperty.latitude,
            lng: activeProperty.longitude,
          }}
          onCloseClick={() => setActiveId(null)}
          pixelOffset={[0, -48]}
        >
          <PropertyInfoWindow
            property={activeProperty}
            onViewDetails={() => {
              onSelectProperty(activeProperty);
              setActiveId(null);
            }}
          />
        </InfoWindow>
      )}
    </>
  );
}

// Helper function to get pin color
function getPinColorFromScore(score: number | null): string {
  if (score === null) return '#9CA3AF';
  if (score >= 70) return '#E8654A';
  if (score >= 40) return '#C4956A';
  return '#E8B4A0';
}

export default function PropertyMap({ properties, onSelectProperty }: PropertyMapProps) {
  return (
    <Map
      defaultCenter={MAP_DEFAULT_CENTER}
      defaultZoom={MAP_DEFAULT_ZOOM}
      mapId={process.env.NEXT_PUBLIC_GOOGLE_MAPS_MAP_ID || undefined}
      gestureHandling="greedy"
      disableDefaultUI={false}
      zoomControl={true}
      streetViewControl={true}
      mapTypeControl={false}
      fullscreenControl={false}
      clickableIcons={false}
      className="h-full w-full"
    >
      <MapMarkers properties={properties} onSelectProperty={onSelectProperty} />
    </Map>
  );
}
