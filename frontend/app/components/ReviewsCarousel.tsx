'use client';

const REVIEWS = [
  { quote: "Finally, something that actually helps without feeling like I'm spying. I get peace of mind and my daughter keeps her privacy.", name: 'Maria K.', role: 'Admin' },
  { quote: "The age settings are a game-changer. What we use for our 8-year-old is different from our 15-year-old—and it actually works for both.", name: 'James T.', role: 'Dad' },
  { quote: "I love that I can see what's risky without having to read every message. It's the balance we needed.", name: 'Priya L.', role: 'Mom' },
  { quote: "Setup took five minutes. Now I get a clear summary every week and my kids don't feel watched.", name: 'David M.', role: 'Dad' },
  { quote: "The whitelist and blacklist made it so easy. We allow learning sites and block the rest. Simple and effective.", name: 'Sarah L.', role: 'Admin' },
  { quote: "Finally, safety tools that respect privacy. My teen gets space; I get alerts when it matters.", name: 'Alex C.', role: 'Guardian' },
];

function ReviewCard({ quote, name, role }: { quote: string; name: string; role: string }) {
  return (
    <blockquote className="flex shrink-0 w-[min(340px,85vw)] flex-col rounded-2xl border border-emerald-200/80 bg-white p-8 text-center shadow-sm dark:border-emerald-800/50 dark:bg-emerald-950/30">
      <p className="text-lg leading-relaxed text-zinc-700 dark:text-zinc-300">
        &ldquo;{quote}&rdquo;
      </p>
      <footer className="mt-5 flex flex-nowrap items-center justify-center gap-2 overflow-hidden">
        <span className="flex h-10 w-10 shrink-0 rounded-full bg-emerald-200 dark:bg-emerald-800" aria-hidden />
        <span className="whitespace-nowrap text-sm text-zinc-700 dark:text-zinc-300">
          <cite className="not-italic font-semibold text-emerald-800 dark:text-emerald-200">{name}</cite>
          <span className="text-zinc-500 dark:text-zinc-400"> · {role}</span>
        </span>
      </footer>
    </blockquote>
  );
}

export function ReviewsCarousel() {
  return (
    <div className="overflow-hidden">
      <div className="flex animate-marquee gap-8">
        {[...REVIEWS, ...REVIEWS].map((r, i) => (
          <ReviewCard key={i} quote={r.quote} name={r.name} role={r.role} />
        ))}
      </div>
    </div>
  );
}
