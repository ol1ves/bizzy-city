'use client';

import type { Property } from '@/lib/types';
import SlidePanel from '@/components/ui/SlidePanel';
import PropertyGallery from './PropertyGallery';
import PropertyInfo from './PropertyInfo';
import RecommendationsSection from './RecommendationsSection';

interface PropertyDetailPanelProps {
  property: Property | null;
  onClose: () => void;
}

export default function PropertyDetailPanel({
  property,
  onClose,
}: PropertyDetailPanelProps) {
  return (
    <SlidePanel open={property !== null} onClose={onClose}>
      {property && (
        <div className="pb-8">
          {/* Gallery */}
          <PropertyGallery propertyId={property.id} lat={property.latitude} lng={property.longitude} />

          {/* Header */}
          <div className="px-5 pt-4 pb-3 border-b border-gray-100">
            <h2 className="text-xl font-bold text-gray-900 leading-tight">
              {property.address}
            </h2>
            <div className="mt-1 flex flex-wrap items-center gap-1.5 text-sm text-gray-500">
              <span>{property.city}, {property.state_code}</span>
              {property.zip_code && <span>·</span>}
              {property.zip_code && <span>{property.zip_code}</span>}
            </div>
            {property.crexi_url && (
              <a
                href={property.crexi_url}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-2 inline-flex items-center text-xs font-medium text-brand-600 hover:text-brand-700 transition-colors"
              >
                View on Crexi ↗
              </a>
            )}
          </div>

          {/* Property Details */}
          <PropertyInfo property={property} />

          {/* AI Recommendations */}
          <RecommendationsSection propertyId={property.id} />
        </div>
      )}
    </SlidePanel>
  );
}
