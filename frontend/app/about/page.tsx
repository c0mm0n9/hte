import Link from 'next/link';
import { SIslandLogo } from '@/app/components/sIslandLogo';

export default function AboutPage() {
  return (
    <div className="min-h-screen bg-sand-50 dark:bg-sand-950/40">
      <header className="border-b border-sand-200/60 bg-white/80 dark:border-sand-800/60 dark:bg-sand-950/60 backdrop-blur-sm">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-4 py-4 sm:px-6">
          <Link href="/" className="text-xl font-bold hover:underline">
            <SIslandLogo />
          </Link>
          <nav className="flex gap-4">
            <Link
              href="/portal"
              className="text-sm font-medium text-sea-700 hover:text-sea-800 dark:text-sea-400 dark:hover:text-sea-300"
            >
              Parents portal
            </Link>
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-4 py-16 sm:py-24">
        <h1 className="text-3xl font-bold text-sand-800 dark:text-sand-100 sm:text-4xl">
          About the team
        </h1>
        <p className="mt-6 text-lg leading-relaxed text-sand-800/90 dark:text-sand-100/90">
          We built <SIslandLogo className="inline" /> to help families safely navigate the sea of information. Our team combines expertise in safety, AI, and product design to deliver a digital ecosystem that detects fake news, AI-generated content, and harmful material — so you can focus on what matters.
        </p>
        <p className="mt-4 text-lg leading-relaxed text-sand-800/90 dark:text-sand-100/90">
          More about our team and mission will be added here.
        </p>
        <div className="mt-10">
          <Link
            href="/"
            className="inline-flex rounded-xl bg-sea-600 px-6 py-3 text-base font-semibold text-white transition hover:bg-sea-700 dark:bg-sea-500 dark:hover:bg-sea-600"
          >
            ← Back to home
          </Link>
        </div>
      </main>
    </div>
  );
}
