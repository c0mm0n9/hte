'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { login } from '@/lib/api';
import { SIslandLogo } from '@/app/components/SIslandLogo';

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(username, password);
      router.push('/portal');
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-emerald-50 dark:bg-emerald-950/80">
      <header className="border-b border-emerald-200/60 bg-white/80 dark:border-emerald-800/50 dark:bg-emerald-950/90 backdrop-blur-sm">
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

      <main className="mx-auto flex max-w-md flex-col items-center justify-center px-4 py-16">
        <div className="animate-scale-in w-full rounded-2xl border border-emerald-200/80 bg-white p-8 shadow-lg shadow-emerald-900/5 dark:border-emerald-800/60 dark:bg-emerald-950/40 dark:shadow-none">
          <h1 className="animate-fade-in-up font-title text-xl font-semibold text-emerald-800 dark:text-emerald-100">Admin login</h1>
          <p className="animate-fade-in-up animate-delay-100 mt-1 text-sm text-emerald-700/80 dark:text-emerald-200/80">
            Sign in to view device activity and detection alerts.
          </p>
          <form onSubmit={handleSubmit} className="mt-6 space-y-4">
            {error && (
              <div className="animate-fade-in rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800 dark:bg-red-950/50 dark:text-red-400">
                {error}
              </div>
            )}
            <div className="animate-fade-in-up animate-delay-200">
              <label htmlFor="username" className="block text-sm font-medium text-emerald-800 dark:text-emerald-200">
                Username
              </label>
              <input
                id="username"
                type="text"
                required
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="mt-1 block w-full rounded-xl border border-emerald-300 bg-white px-3 py-2.5 text-emerald-900 placeholder-emerald-500/60 transition focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/30 dark:border-emerald-600 dark:bg-emerald-950/60 dark:text-emerald-100 dark:placeholder-emerald-400/50"
              />
            </div>
            <div className="animate-fade-in-up animate-delay-300">
              <label htmlFor="password" className="block text-sm font-medium text-emerald-800 dark:text-emerald-200">
                Password
              </label>
              <input
                id="password"
                type="password"
                required
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="mt-1 block w-full rounded-xl border border-emerald-300 bg-white px-3 py-2.5 text-emerald-900 placeholder-emerald-500/60 transition focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/30 dark:border-emerald-600 dark:bg-emerald-950/60 dark:text-emerald-100 dark:placeholder-emerald-400/50"
              />
            </div>
            <div className="flex flex-wrap items-center gap-3 pt-2 animate-fade-in-up animate-delay-400">
              <button
                type="submit"
                disabled={loading}
                className="rounded-xl bg-emerald-600 px-6 py-2.5 text-sm font-semibold text-white shadow-sm transition duration-200 hover:bg-emerald-700 hover:shadow-md disabled:opacity-50 dark:bg-emerald-500 dark:hover:bg-emerald-600"
              >
                {loading ? 'Signing in…' : 'Sign in'}
              </button>
              <Link href="/register" className="text-sm font-medium text-emerald-700 transition hover:underline dark:text-emerald-400">
                Register
              </Link>
            </div>
          </form>
        </div>
      </main>
    </div>
  );
}
