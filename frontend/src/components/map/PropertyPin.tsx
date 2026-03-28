'use client';

const PIN_COLOR = '#3B82F6';

export default function PropertyPin() {
  return (
    <div className="relative flex flex-col items-center group cursor-pointer">
      <div
        className="flex h-10 w-10 items-center justify-center rounded-full border-2 border-white shadow-lg text-base transition-transform group-hover:scale-110"
        style={{ backgroundColor: PIN_COLOR }}
      >
        <span role="img" aria-label="property">
          🏢
        </span>
      </div>
      <div
        className="h-0 w-0 -mt-0.5"
        style={{
          borderLeft: '6px solid transparent',
          borderRight: '6px solid transparent',
          borderTop: `8px solid ${PIN_COLOR}`,
        }}
      />
    </div>
  );
}
