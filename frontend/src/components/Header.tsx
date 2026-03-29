'use client';

export default function Header() {
  return (
    <div className="absolute top-4 left-4 z-30">
      <div className="rounded-xl bg-white/80 backdrop-blur-md px-4 py-2.5 shadow-lg border border-neutral-200/50">
        <h1 className="text-lg font-bold text-neutral-900 tracking-tight">
          BusiCity
        </h1>
        <p className="text-[11px] text-neutral-500 -mt-0.5">
          Find the right business for any space.
        </p>
      </div>
    </div>
  );
}
