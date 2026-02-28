import Link from 'next/link';
import { SIslandLogo } from '@/app/components/SIslandLogo';
import { ReviewsCarousel } from '@/app/components/ReviewsCarousel';

function CheckMark() {
  return (
    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-emerald-100 dark:bg-emerald-900/50" aria-hidden>
      <svg className="h-5 w-5 text-emerald-600 dark:text-emerald-400" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
      </svg>
    </span>
  );
}

export default function Home() {
  return (
    <div className="min-h-screen bg-emerald-50 dark:bg-emerald-950/30">
      <header className="sticky top-0 z-10 border-b border-emerald-200/60 bg-white/85 dark:border-emerald-800/50 dark:bg-emerald-950/70 backdrop-blur-md transition-shadow duration-300">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-4 py-4 sm:px-6">
          <Link
            href="/"
            className="text-xl font-bold text-emerald-700 transition hover:text-emerald-800 dark:text-emerald-400 dark:hover:text-emerald-300"
          >
            <SIslandLogo />
          </Link>
          <nav className="flex gap-6">
            <Link
              href="/about"
              className="text-sm font-medium text-emerald-700 transition hover:text-emerald-800 dark:text-emerald-400 dark:hover:text-emerald-300"
            >
              About team
            </Link>
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-24 sm:py-32">
        {/* Hero */}
        <section className="flex flex-col items-center justify-center text-center">
          <h1 className="animate-fade-in-down font-title text-4xl font-bold tracking-tight text-emerald-900 dark:text-emerald-100 sm:text-5xl md:text-6xl">
            <span className="inline-block">
              <SIslandLogo className="text-4xl sm:text-5xl md:text-6xl" />
            </span>
          </h1>
          <p className="animate-fade-in-up animate-delay-500 mt-8 max-w-2xl text-2xl font-medium leading-relaxed text-emerald-800/90 dark:text-emerald-100/90 sm:text-3xl md:text-4xl">
            A safe island for your child—amid a sea of harmful content.
          </p>
          <div className="animate-fade-in-up animate-delay-1000 mt-14 flex flex-wrap items-center justify-center gap-4">
            <a
              href="#"
              className="inline-flex rounded-xl bg-emerald-600 px-8 py-4 text-base font-semibold text-white shadow-lg shadow-emerald-600/25 transition duration-300 hover:scale-[1.02] hover:bg-emerald-700 hover:shadow-xl hover:shadow-emerald-600/30 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 dark:bg-emerald-500 dark:hover:bg-emerald-600"
            >
              Download extension
            </a>
            <Link
              href="/portal"
              className="inline-flex rounded-xl border-2 border-emerald-600 bg-transparent px-8 py-4 text-base font-semibold text-emerald-700 transition duration-300 hover:scale-[1.02] hover:bg-emerald-600 hover:text-white focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 dark:border-emerald-500 dark:text-emerald-400 dark:hover:bg-emerald-500 dark:hover:text-white"
            >
              Parents portal
            </Link>
          </div>
        </section>

        {/* Benefits — 3 columns, bigger cards + green check */}
        <section className="mt-28 grid gap-10 sm:grid-cols-3 sm:gap-10 lg:gap-12">
          <article className="animate-fade-in-up animate-delay-1200 flex flex-col items-center gap-5 rounded-2xl border border-emerald-200/80 bg-white p-10 text-center shadow-sm dark:border-emerald-800/50 dark:bg-emerald-950/30 sm:p-12">
            <CheckMark />
            <div>
              <h2 className="font-title text-2xl font-semibold text-emerald-800 dark:text-emerald-200">
                Protection that keeps up—without invading privacy
              </h2>
              <p className="mt-5 text-lg leading-relaxed text-zinc-700 dark:text-zinc-300">
                We spot harmful content, misleading info, and risks in real time as your child browses—so you can relax. Everything stays on your device; we never see or store their private data.
              </p>
            </div>
          </article>
          <article className="animate-fade-in-up animate-delay-1500 flex flex-col items-center gap-5 rounded-2xl border border-emerald-200/80 bg-white p-10 text-center shadow-sm dark:border-emerald-800/50 dark:bg-emerald-950/30 sm:p-12">
            <CheckMark />
            <div>
              <h2 className="font-title text-2xl font-semibold text-emerald-800 dark:text-emerald-200">
                You stay in control—without reading their chats
              </h2>
              <p className="mt-5 text-lg leading-relaxed text-zinc-700 dark:text-zinc-300">
                Get clear alerts and simple reports so you know what&apos;s going on. Set allowed sites, block others, and choose an age level. You see safety summaries—not their messages or personal stuff.
              </p>
            </div>
          </article>
          <article className="animate-fade-in-up animate-delay-1800 flex flex-col items-center gap-5 rounded-2xl border border-emerald-200/80 bg-white p-10 text-center shadow-sm dark:border-emerald-800/50 dark:bg-emerald-950/30 sm:p-12">
            <CheckMark />
            <div>
              <h2 className="font-title text-2xl font-semibold text-emerald-800 dark:text-emerald-200">
                Grows with your child—from little kids to teens
              </h2>
              <p className="mt-5 text-lg leading-relaxed text-zinc-700 dark:text-zinc-300">
                Teens get more say in how their assistant works; younger kids follow the rules you set. The AI adapts its tone and checks based on age, so protection fits your family.
              </p>
            </div>
          </article>
        </section>

        {/* Social proof / reviews — looping carousel */}
        <section className="mt-28">
          <h2 className="animate-fade-in-up animate-delay-2100 font-title text-center text-2xl font-semibold text-emerald-900 dark:text-emerald-100 sm:text-3xl">
            Families <span className="text-emerald-600 dark:text-emerald-400 font-semibold">trust</span> s-island
          </h2>
          <div className="mt-12">
            <ReviewsCarousel />
          </div>
        </section>
      </main>
    </div>
  );
}
