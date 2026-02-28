/** Brand: h.protect — green accent on "h", rest in neutral */
export function HProtectLogo({ className = '' }: { className?: string }) {
  return (
    <span className={`font-semibold tracking-tight ${className}`}>
      <span className="text-emerald-600 dark:text-emerald-400">h</span>
      <span className="text-zinc-700 dark:text-zinc-300">.protect</span>
    </span>
  );
}
