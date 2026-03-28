interface SkeletonProps {
  className?: string;
}

export default function Skeleton({ className = '' }: SkeletonProps) {
  return (
    <div
      className={`rounded bg-gray-200 ${className}`}
      style={{ animation: 'skeleton-pulse 1.5s ease-in-out infinite' }}
    />
  );
}
