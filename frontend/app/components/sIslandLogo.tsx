/** Brand: s-island — green island theme */
export function SIslandLogo({ className = '' }: { className?: string }) {
  return (
    <span className={`font-title font-semibold tracking-tight ${className}`}>
      <span className="text-emerald-600 dark:text-emerald-400">s</span>
      <span className="text-zinc-700 dark:text-zinc-300">-island</span>
    </span>
  );
}
