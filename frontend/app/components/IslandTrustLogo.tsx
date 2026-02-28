/** Brand: island.trust — sandy "island", ocean "trust" */
export function IslandTrustLogo({ className = '' }: { className?: string }) {
  return (
    <span className={`font-semibold tracking-tight ${className}`}>
      <span className="text-sand-700 dark:text-sand-300">island</span>
      <span className="text-sea-600 dark:text-sea-400">.trust</span>
    </span>
  );
}
