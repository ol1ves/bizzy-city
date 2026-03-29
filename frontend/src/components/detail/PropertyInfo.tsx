'use client';

import type { Property } from '@/lib/types';

interface PropertyInfoProps {
  property: Property;
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
    { label: 'Rent / sqft', value: formatRentPerSqft(property.asking_rent_per_sqft) },
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
    </div>
  );
}
