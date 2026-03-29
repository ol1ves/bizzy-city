'use client';

export default function Header() {
  return (
    <div className="absolute top-4 left-4 z-30">
      <div className="flex items-center gap-3 rounded-2xl bg-white/90 backdrop-blur-lg px-4 py-3 shadow-lg border border-neutral-100">
        {/* Logo Icon */}
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-accent-400 to-accent-500 shadow-sm">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M3 21V8L12 3L21 8V21H15V14H9V21H3Z" fill="white" fillOpacity="0.95"/>
            <rect x="10" y="9" width="4" height="3" rx="0.5" fill="currentColor" className="text-accent-500"/>
          </svg>
        </div>
        
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
