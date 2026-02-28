'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { login } from '@/lib/api';
import { SIslandLogo } from '@/app/components/sIslandLogo';

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
    <div className="min-h-screen bg-sand-50 dark:bg-sand-950/40">
      <header className="border-b border-sand-200/60 bg-white/80 dark:border-sand-800/60 dark:bg-sand-950/60 backdrop-blur-sm">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-4 py-4 sm:px-6">
          <Link href="/" className="text-xl font-bold hover:underline">
            <SIslandLogo />
          </Link>
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

      <main className="mx-auto flex max-w-md flex-col items-center justify-center px-4 py-16">
        <div className="w-full rounded-xl border border-sand-200/80 bg-white p-8 shadow-sm dark:border-sand-800/60 dark:bg-sand-950/40">
          <h1 className="text-xl font-semibold text-sand-800 dark:text-sand-100">Parent login</h1>
          <p className="mt-1 text-sm text-sand-700/80 dark:text-sand-200/80">
            Sign in to view device activity and detection alerts.
          </p>
          <form onSubmit={handleSubmit} className="mt-6 space-y-4">
            {error && (
              <div className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-800 dark:bg-red-950/50 dark:text-red-400">
                {error}
              </div>
            )}
            <div>
              <label htmlFor="username" className="block text-sm font-medium text-sand-800 dark:text-sand-200">
                Username
              </label>
              <input
                id="username"
                type="text"
                required
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="mt-1 block w-full rounded-lg border border-sand-300 bg-white px-3 py-2 text-sand-900 placeholder-sand-500/60 focus:border-sea-500 focus:outline-none focus:ring-1 focus:ring-sea-500 dark:border-sand-600 dark:bg-sand-950/60 dark:text-sand-100 dark:placeholder-sand-400/50"
              />
            </div>
            <div>
              <label htmlFor="password" className="block text-sm font-medium text-sand-800 dark:text-sand-200">
                Password
              </label>
              <input
                id="password"
                type="password"
                required
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="mt-1 block w-full rounded-lg border border-sand-300 bg-white px-3 py-2 text-sand-900 placeholder-sand-500/60 focus:border-sea-500 focus:outline-none focus:ring-1 focus:ring-sea-500 dark:border-sand-600 dark:bg-sand-950/60 dark:text-sand-100 dark:placeholder-sand-400/50"
              />
            </div>
            <div className="flex flex-wrap items-center gap-3 pt-2">
              <button
                type="submit"
                disabled={loading}
                className="rounded-xl bg-sea-600 px-6 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-sea-700 disabled:opacity-50 dark:bg-sea-500 dark:hover:bg-sea-600"
              >
                {loading ? 'Signing in…' : 'Sign in'}
              </button>
              <Link href="/register" className="text-sm font-medium text-sea-700 hover:underline dark:text-sea-400">
                Register
              </Link>
              <Link href="/" className="text-sm font-medium text-sea-700 hover:underline dark:text-sea-400">
                Home
              </Link>
            </div>
          </form>
        </div>
      </main>
    </div>
  );
}
