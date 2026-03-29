'use client';

import Image from 'next/image';

export default function Header() {
  return (
    <div className="absolute top-4 left-4 z-30">
      <div className="flex items-center gap-2 rounded-xl bg-white/90 backdrop-blur-lg px-3 py-2 shadow-lg border border-neutral-100">
        {/* Logo */}
        <Image
          src="/logo.png"
          alt="BizzyCity logo"
          width={24}
          height={30}
          className="object-contain"
          style={{ height: '24px', width: 'auto' }}
          priority
        />
        
        {/* Text */}
        <div>
          <h1 className="text-base font-bold text-neutral-900 tracking-tight leading-tight">
            BizzyCity
          </h1>
          <p className="text-[10px] text-neutral-400 font-medium tracking-wide uppercase">
            AI Property Insights
          </p>
        </div>
      </div>
    </div>
  );
}
