'use client';

import { useState, useCallback } from 'react';
import { Map, AdvancedMarker, InfoWindow, useMap } from '@vis.gl/react-google-maps';
import type { Property } from '@/lib/types';
import { MAP_DEFAULT_CENTER, MAP_DEFAULT_ZOOM } from '@/constants';
import PropertyPin from './PropertyPin';
import PropertyInfoWindow from './PropertyInfoWindow';

interface PropertyMapProps {
  properties: Property[];
  onSelectProperty: (property: Property) => void;
}

function MapMarkers({
  properties,
  onSelectProperty,
}: PropertyMapProps) {
  const map = useMap();
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);

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

  // Don't render markers until the map is ready
  if (!map) return null;

  return (
    <>
      {properties.map((property) => {
        const isHovered = hoveredId === property.id || activeId === property.id;
        return (
          <AdvancedMarker
            key={property.id}
            position={{ lat: property.latitude, lng: property.longitude }}
            onClick={() => handleMarkerClick(property)}
            onMouseEnter={() => setHoveredId(property.id)}
            onMouseLeave={() => setHoveredId(null)}
            zIndex={isHovered ? 10 : 1}
          >
            <PropertyPin score={property.top_rec_score} isHovered={isHovered} />
          </AdvancedMarker>
        );
      })}

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
