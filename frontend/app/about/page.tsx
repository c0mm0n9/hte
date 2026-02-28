import Link from 'next/link';

export default function AboutPage() {
  return (
    <div className="min-h-screen bg-emerald-50 dark:bg-emerald-950/40">
      <header className="border-b border-emerald-200/60 bg-white/80 dark:border-emerald-800/60 dark:bg-emerald-950/60 backdrop-blur-sm">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-4 py-4 sm:px-6">
          <Link
            href="/"
            className="text-xl font-bold text-emerald-700 dark:text-emerald-400 hover:underline"
          >
            hSafety
          </Link>
          <nav className="flex gap-4">
            <Link
              href="/portal"
              className="text-sm font-medium text-emerald-700 hover:text-emerald-800 dark:text-emerald-400 dark:hover:text-emerald-300"
            >
              Parents portal
            </Link>
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-4 py-16 sm:py-24">
        <h1 className="text-3xl font-bold text-emerald-800 dark:text-emerald-100 sm:text-4xl">
          About the team
        </h1>
        <p className="mt-6 text-lg leading-relaxed text-emerald-800/90 dark:text-emerald-100/90">
          We built hSafety to help parents protect their children online. Our team combines expertise in safety, AI, and product design to deliver tools that detect fake news, AI-generated content, and harmful material — so you can focus on what matters.
        </p>
        <p className="mt-4 text-lg leading-relaxed text-emerald-800/90 dark:text-emerald-100/90">
          More about our team and mission will be added here.
        </p>
        <div className="mt-10">
          <Link
            href="/"
            className="inline-flex rounded-xl bg-emerald-600 px-6 py-3 text-base font-semibold text-white transition hover:bg-emerald-700 dark:bg-emerald-500 dark:hover:bg-emerald-600"
          >
            ← Back to home
          </Link>
        </div>
      </main>
    </div>
  );
}
