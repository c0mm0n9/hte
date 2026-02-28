/** Title text: first part sea, second part sand; Caveat Brush font */
export function SIslandLogo({ className = '' }: { className?: string }) {
  return (
    <span className={`font-title ${className}`} style={{ fontFamily: 'var(--font-caveat-brush), cursive' }}>
      <span className="text-sea-600 dark:text-sea-400">s</span>
      <span className="text-sand-700 dark:text-sand-300">Island</span>
    </span>
  );
}
