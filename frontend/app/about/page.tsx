import Link from 'next/link';
import { SIslandLogo } from '@/app/components/SIslandLogo';

export default function AboutPage() {
  return (
    <div className="min-h-screen bg-emerald-50 dark:bg-emerald-950/30">
      <header className="border-b border-emerald-200/60 bg-white/80 dark:border-emerald-800/50 dark:bg-emerald-950/70 backdrop-blur-sm">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-4 py-4 sm:px-6">
          <Link href="/" className="text-xl font-bold text-emerald-700 dark:text-emerald-400 transition hover:opacity-90">
            <SIslandLogo />
          </Link>
          <nav className="flex gap-4">
            <Link
              href="/about"
              className="text-sm font-medium text-emerald-700 transition hover:text-emerald-800 dark:text-emerald-400 dark:hover:text-emerald-300"
            >
              About team
            </Link>
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-4 py-16 sm:py-24">
        <h1 className="animate-fade-in-up font-title text-3xl font-bold text-emerald-900 dark:text-emerald-100 sm:text-4xl">
          About the team
        </h1>
        <p className="animate-fade-in-up animate-delay-100 mt-6 text-lg leading-relaxed text-emerald-800/90 dark:text-emerald-200/90">
          We built <SIslandLogo className="inline" /> to help families keep kids safe online. Our team combines expertise in safety, AI, and product design to deliver harmful content detection, private information alerts, and predator awareness — so you can focus on what matters.
        </p>
        <section className="animate-fade-in-up animate-delay-200 mt-14">
          <h2 className="font-title text-2xl font-bold text-emerald-900 dark:text-emerald-100">
            Meet the team
          </h2>
          <div className="mt-8 grid gap-8 sm:grid-cols-3">
            <div className="rounded-2xl border border-emerald-200/80 bg-white p-6 shadow-sm dark:border-emerald-800/50 dark:bg-emerald-950/40">
              <p className="font-title text-lg font-semibold text-emerald-900 dark:text-emerald-100">
                Danial Iskakov
              </p>
              <p className="mt-1 text-sm font-medium text-emerald-700 dark:text-emerald-300">
                City University of Hong Kong · Browser extension developer
              </p>
              <p className="mt-3 text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">
                Danial brings the extension to life with clean, secure code and a sharp eye for performance. He keeps the client lightweight and reliable so it runs smoothly on every device.
              </p>
            </div>
            <div className="rounded-2xl border border-emerald-200/80 bg-white p-6 shadow-sm dark:border-emerald-800/50 dark:bg-emerald-950/40">
              <p className="font-title text-lg font-semibold text-emerald-900 dark:text-emerald-100">
                Mykhailo Kurganov
              </p>
              <p className="mt-1 text-sm font-medium text-emerald-700 dark:text-emerald-300">
                University of Hong Kong · AI & detection · not the last coder
              </p>
              <p className="mt-3 text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">
                Mykhailo designs and trains the models that spot harmful content and risks in real time. His work makes the AI accurate, privacy-aware, and adaptable to different ages.
              </p>
            </div>
            <div className="rounded-2xl border border-emerald-200/80 bg-white p-6 shadow-sm dark:border-emerald-800/50 dark:bg-emerald-950/40">
              <p className="font-title text-lg font-semibold text-emerald-900 dark:text-emerald-100">
                Arsen Argandykov
              </p>
              <p className="mt-1 text-sm font-medium text-emerald-700 dark:text-emerald-300">
                University of Hong Kong · Full-stack developer
              </p>
              <p className="mt-3 text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">
                Arsen builds and maintains the backend and admin portal so admins get clear reports and control. He keeps the stack robust and the experience simple for families.
              </p>
            </div>
          </div>
        </section>
        <div className="animate-fade-in-up animate-delay-300 mt-12">
          <Link
            href="/"
            className="inline-flex rounded-xl bg-emerald-600 px-6 py-3 text-base font-semibold text-white shadow-sm transition duration-200 hover:scale-[1.02] hover:bg-emerald-700 hover:shadow-md dark:bg-emerald-500 dark:hover:bg-emerald-600"
          >
            ← Back to home
          </Link>
        </div>
      </main>
    </div>
  );
}
