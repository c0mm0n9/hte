import Link from 'next/link';
import { SIslandLogo } from '@/app/components/sIslandLogo';

export default function Home() {
  return (
    <div className="min-h-screen bg-sand-50 dark:bg-sand-950/40">
      <header className="border-b border-sand-200/60 bg-white/80 dark:border-sand-800/60 dark:bg-sand-950/60 backdrop-blur-sm">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-4 py-4 sm:px-6">
          <SIslandLogo className="text-xl font-bold" />
          <nav className="flex gap-4">
            <Link
              href="/about"
              className="text-sm font-medium text-sea-700 hover:text-sea-800 dark:text-sea-400 dark:hover:text-sea-300"
            >
              About team
            </Link>
          </nav>
        </div>
      </header>

      <main className="mx-auto flex max-w-4xl flex-col items-center justify-center px-4 py-24 text-center sm:py-32">
        <h1 className="text-4xl font-bold tracking-tight sm:text-5xl md:text-6xl">
          <SIslandLogo />
        </h1>
        <p className="mt-8 max-w-2xl text-2xl font-medium leading-relaxed text-sand-800/90 dark:text-sand-100/90 sm:text-3xl">
          digital ecosystem to safely surf in the sea of information
        </p>
        <div className="mt-14 flex flex-wrap items-center justify-center gap-4">
          <a
            href="#"
            className="inline-flex rounded-xl bg-sea-600 px-8 py-4 text-base font-semibold text-white shadow-md transition hover:bg-sea-700 focus:outline-none focus:ring-2 focus:ring-sea-500 focus:ring-offset-2 dark:bg-sea-500 dark:hover:bg-sea-600"
          >
            Download extension
          </a>
          <Link
            href="/portal"
            className="inline-flex rounded-xl border-2 border-sea-600 bg-transparent px-8 py-4 text-base font-semibold text-sea-700 transition hover:bg-sea-600 hover:text-white focus:outline-none focus:ring-2 focus:ring-sea-500 focus:ring-offset-2 dark:border-sea-500 dark:text-sea-400 dark:hover:bg-sea-500 dark:hover:text-white"
          >
            Parents portal
          </Link>
        </div>
      </main>
    </div>
  );
}
