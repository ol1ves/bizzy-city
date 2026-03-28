'use client';

import { useEffect, useRef } from 'react';

interface SlidePanelProps {
  open: boolean;
  onClose: () => void;
  children: React.ReactNode;
}

export default function SlidePanel({ open, onClose, children }: SlidePanelProps) {
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
    }
    if (open) {
      document.addEventListener('keydown', handleKeyDown);
    }
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [open, onClose]);

  useEffect(() => {
    if (open && panelRef.current) {
      panelRef.current.focus();
    }
  }, [open]);

  if (!open) return null;

  return (
    <>
      {/* Backdrop — click to close (only visible on mobile) */}
      <div
        className="fixed inset-0 z-40 bg-black/20 md:bg-transparent md:pointer-events-none"
        onClick={onClose}
        aria-hidden
      />

      {/* Desktop / Tablet: slide from right */}
      <div
        ref={panelRef}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        className={`
          fixed z-50 bg-white shadow-2xl outline-none overflow-y-auto
          transition-transform duration-300 ease-in-out

          /* Mobile: bottom sheet */
          inset-x-0 bottom-0 h-[70vh] rounded-t-2xl
          
          /* Tablet+ : right panel */
          md:inset-y-0 md:right-0 md:left-auto md:h-full md:rounded-none
          md:w-[400px] lg:w-[480px]

          ${open ? 'translate-y-0 md:translate-x-0' : 'translate-y-full md:translate-y-0 md:translate-x-full'}
        `}
      >
        <button
          onClick={onClose}
          className="absolute top-3 right-3 z-10 flex h-8 w-8 items-center justify-center rounded-full bg-white/80 text-gray-600 shadow backdrop-blur hover:bg-white hover:text-gray-900 transition-colors"
          aria-label="Close panel"
        >
          ✕
        </button>
        {children}
      </div>
    </>
  );
}
