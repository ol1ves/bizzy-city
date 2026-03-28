'use client';

import type { Property } from '@/lib/types';

interface PropertyInfoProps {
  property: Property;
}

function formatRent(rent: number | null): string {
  if (rent == null) return 'Contact for pricing';
  return `$${Number(rent).toLocaleString()}/mo`;
}

function formatRentPerSqft(rent: number | null): string {
  if (rent == null) return '—';
  return `$${Number(rent).toLocaleString()}/sqft/yr`;
}

export default function PropertyInfo({ property }: PropertyInfoProps) {
  const fields = [
    {
      label: 'Square Footage',
      value: property.square_footage
        ? `${property.square_footage.toLocaleString()} sqft`
        : 'N/A',
    },
    { label: 'Asking Rent', value: formatRent(property.asking_rent) },
    { label: 'Rent / sqft', value: formatRentPerSqft(property.asking_rent_per_sqft) },
    { label: 'Year Built', value: property.year_built ?? '—' },
  ];

  return (
    <div className="px-5 py-4">
      <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-3">
        Property Details
      </h3>

      <div className="grid grid-cols-2 gap-3">
        {fields.map((f) => (
          <div key={f.label}>
            <p className="text-xs text-gray-400">{f.label}</p>
            <p className="text-sm font-medium text-gray-900">{f.value}</p>
          </div>
        ))}
      </div>

      {/* Listing status */}
      <div className="mt-3 flex items-center gap-2">
        <span className="inline-flex items-center rounded-full bg-green-50 px-2 py-0.5 text-xs font-medium text-green-700 ring-1 ring-green-600/20 ring-inset">
          {property.listing_status ?? 'active'}
        </span>
      </div>

      {/* Broker info */}
      {(property.broker_name || property.broker_company) && (
        <div className="mt-4 border-t border-gray-100 pt-3">
          <p className="text-xs text-gray-400">Listed by</p>
          <p className="text-sm font-medium text-gray-900">
            {property.broker_name ?? 'Unknown'}
            {property.broker_company && (
              <span className="font-normal text-gray-500">
                {' '}at {property.broker_company}
              </span>
            )}
          </p>
        </div>
      )}
    </div>
  );
}
