import Link from 'next/link';

export default function Home() {
  return (
    <div className="min-h-screen bg-emerald-50 dark:bg-emerald-950/40">
      <header className="border-b border-emerald-200/60 bg-white/80 dark:border-emerald-800/60 dark:bg-emerald-950/60 backdrop-blur-sm">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-4 py-4 sm:px-6">
          <span className="text-xl font-bold text-emerald-700 dark:text-emerald-400">hSafety</span>
          <nav className="flex gap-4">
            <Link
              href="/about"
              className="text-sm font-medium text-emerald-700 hover:text-emerald-800 dark:text-emerald-400 dark:hover:text-emerald-300"
            >
              About team
            </Link>
          </nav>
        </div>
      </header>

      <main className="mx-auto flex max-w-4xl flex-col items-center justify-center px-4 py-24 text-center sm:py-32">
        <h1 className="text-4xl font-bold tracking-tight text-emerald-800 dark:text-emerald-100 sm:text-5xl md:text-6xl">
          hSafety
        </h1>
        <p className="mt-8 max-w-2xl text-2xl font-medium leading-relaxed text-emerald-800/90 dark:text-emerald-100/90 sm:text-3xl">
          Keep children safe online with fake news detection, AI-generated content alerts, and harmful content filtering — all from one place.
        </p>
        <div className="mt-14 flex flex-wrap items-center justify-center gap-4">
          <a
            href="#"
            className="inline-flex rounded-xl bg-emerald-600 px-8 py-4 text-base font-semibold text-white shadow-md transition hover:bg-emerald-700 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 dark:bg-emerald-500 dark:hover:bg-emerald-600"
          >
            Download extension
          </a>
          <Link
            href="/portal"
            className="inline-flex rounded-xl border-2 border-emerald-600 bg-transparent px-8 py-4 text-base font-semibold text-emerald-700 transition hover:bg-emerald-600 hover:text-white focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 dark:border-emerald-500 dark:text-emerald-400 dark:hover:bg-emerald-500 dark:hover:text-white"
          >
            Parents portal
          </Link>
        </div>
      </main>
    </div>
  );
}
