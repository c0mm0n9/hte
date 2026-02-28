'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import type { DashboardResponse, VisitedSite, UserInfo } from '@/lib/api';
import { fetchDashboard, fetchMe, logout, createDevice, deleteDevice } from '@/lib/api';

function DetectionBadge({ value }: { value: boolean }) {
  if (value) {
    return (
      <span className="inline-flex items-center rounded-full bg-red-100 px-2.5 py-0.5 text-xs font-medium text-red-800 dark:bg-red-900/30 dark:text-red-400">
        Yes
      </span>
    );
  }
  return (
    <span className="inline-flex items-center rounded-full bg-zinc-100 px-2.5 py-0.5 text-xs font-medium text-zinc-600 dark:bg-zinc-700 dark:text-zinc-400">
      No
    </span>
  );
}

function VisitedSitesTable({ sites }: { sites: VisitedSite[] }) {
  if (sites.length === 0) {
    return (
      <p className="text-sm text-zinc-500 dark:text-zinc-400">No visits recorded yet.</p>
    );
  }
  return (
    <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-700">
      <table className="min-w-full divide-y divide-zinc-200 dark:divide-zinc-700">
        <thead className="bg-zinc-50 dark:bg-zinc-800/50">
          <tr>
            <th scope="col" className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-zinc-600 dark:text-zinc-400">
              Website
            </th>
            <th scope="col" className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-zinc-600 dark:text-zinc-400">
              Visited
            </th>
            <th scope="col" className="px-4 py-3 text-center text-xs font-medium uppercase tracking-wider text-zinc-600 dark:text-zinc-400">
              AI detected
            </th>
            <th scope="col" className="px-4 py-3 text-center text-xs font-medium uppercase tracking-wider text-zinc-600 dark:text-zinc-400">
              Fake news
            </th>
            <th scope="col" className="px-4 py-3 text-center text-xs font-medium uppercase tracking-wider text-zinc-600 dark:text-zinc-400">
              Harmful content
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-200 bg-white dark:divide-zinc-700 dark:bg-zinc-900/30">
          {sites.map((site) => (
            <tr key={site.id} className="hover:bg-zinc-50 dark:hover:bg-zinc-800/30">
              <td className="px-4 py-3">
                <a
                  href={site.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="max-w-[280px] truncate font-medium text-blue-600 hover:underline dark:text-blue-400"
                  title={site.url}
                >
                  {site.title || site.url}
                </a>
                {site.title && (
                  <div className="max-w-[280px] truncate text-xs text-zinc-500 dark:text-zinc-400" title={site.url}>
                    {site.url}
                  </div>
                )}
              </td>
              <td className="whitespace-nowrap px-4 py-3 text-sm text-zinc-600 dark:text-zinc-400">
                {new Date(site.visited_at).toLocaleString()}
              </td>
              <td className="px-4 py-3 text-center">
                <DetectionBadge value={site.ai_detected} />
              </td>
              <td className="px-4 py-3 text-center">
                <DetectionBadge value={site.fake_news_detected} />
              </td>
              <td className="px-4 py-3 text-center">
                <DetectionBadge value={site.harmful_content_detected} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function PortalPage() {
  const router = useRouter();
  const [user, setUser] = useState<UserInfo | null>(null);
  const [data, setData] = useState<DashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedDeviceId, setSelectedDeviceId] = useState<number | null>(null);
  const [loggingOut, setLoggingOut] = useState(false);
  const [addLabel, setAddLabel] = useState('');
  const [addDeviceType, setAddDeviceType] = useState<'control' | 'agentic'>('control');
  const [addAgenticPrompt, setAddAgenticPrompt] = useState('');
  const [addDeviceLoading, setAddDeviceLoading] = useState(false);
  const [addDeviceError, setAddDeviceError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [copyStatus, setCopyStatus] = useState<string | null>(null);

  const refreshDashboard = () => {
    return fetchDashboard().then((d) => {
      setData(d);
      if (d.devices.length > 0 && !d.devices.some((dev) => dev.id === selectedDeviceId)) {
        setSelectedDeviceId(d.devices[0].id);
      }
    });
  };

  useEffect(() => {
    fetchMe()
      .then((r) => {
        setUser(r.user);
        return fetchDashboard();
      })
      .then(setData)
      .catch((e) => {
        if (e instanceof Error && e.message === 'Not authenticated') {
          router.push('/login');
          return;
        }
        setError(e instanceof Error ? e.message : 'Failed to load');
      })
      .finally(() => setLoading(false));
  }, [router]);

  async function handleAddDevice(e: React.FormEvent) {
    e.preventDefault();
    const label = addLabel.trim();
    if (!label) return;
    if (addDeviceType === 'agentic' && !addAgenticPrompt.trim()) return;
    setAddDeviceError(null);
    setAddDeviceLoading(true);
    try {
      await createDevice({
        label,
        device_type: addDeviceType,
        agentic_prompt: addDeviceType === 'agentic' ? addAgenticPrompt.trim() : undefined,
      });
      setAddLabel('');
      setAddAgenticPrompt('');
      await refreshDashboard();
    } catch (err) {
      setAddDeviceError(err instanceof Error ? err.message : 'Failed to add device');
    } finally {
      setAddDeviceLoading(false);
    }
  }

  async function handleRemoveDevice(deviceId: number, deviceLabel: string) {
    if (!confirm(`Remove device "${deviceLabel}"? Its visit history will be deleted.`)) return;
    setDeletingId(deviceId);
    try {
      await deleteDevice(deviceId);
      await refreshDashboard();
      if (selectedDeviceId === deviceId) setSelectedDeviceId(null);
    } finally {
      setDeletingId(null);
    }
  }

  async function handleLogout() {
    setLoggingOut(true);
    try {
      await logout();
      router.push('/login');
      router.refresh();
    } finally {
      setLoggingOut(false);
    }
  }

  useEffect(() => {
    if (data?.devices?.length && selectedDeviceId === null) {
      setSelectedDeviceId(data.devices[0].id);
    }
  }, [data, selectedDeviceId]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-50 dark:bg-zinc-950">
        <p className="text-zinc-600 dark:text-zinc-400">Loading dashboard…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-50 dark:bg-zinc-950">
        <div className="rounded-lg border border-red-200 bg-red-50 p-6 dark:border-red-900 dark:bg-red-950/30">
          <p className="font-medium text-red-800 dark:text-red-400">Error loading dashboard</p>
          <p className="mt-1 text-sm text-red-700 dark:text-red-500">{error}</p>
          <p className="mt-2 text-xs text-zinc-600 dark:text-zinc-400">
            Make sure the backend is running at {process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}
          </p>
          <Link href="/login" className="mt-3 inline-block text-sm text-blue-600 hover:underline dark:text-blue-400">
            Go to login
          </Link>
        </div>
      </div>
    );
  }

  const selectedDevice = data?.devices.find((d) => d.id === selectedDeviceId);
  const sites = selectedDevice?.visited_sites ?? [];
  const apiKey = selectedDevice ? `${selectedDevice.uuid}-${selectedDevice.device_type}` : '';

  async function handleCopyApiKey() {
    if (!apiKey) return;
    setCopyStatus(null);
    try {
      await navigator.clipboard.writeText(apiKey);
      setCopyStatus('Copied');
    } catch {
      try {
        const ta = document.createElement('textarea');
        ta.value = apiKey;
        ta.style.position = 'fixed';
        ta.style.left = '-9999px';
        document.body.appendChild(ta);
        ta.focus();
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
        setCopyStatus('Copied');
      } catch {
        setCopyStatus('Copy failed');
      }
    } finally {
      setTimeout(() => setCopyStatus(null), 1500);
    }
  }

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950">
      <header className="border-b border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
        <div className="mx-auto max-w-6xl px-4 py-4 sm:px-6 flex items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <Link href="/" className="text-lg font-semibold text-emerald-600 dark:text-emerald-400 hover:underline">
              hSafety
            </Link>
            <div>
              <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100">
                Parents Portal
              </h1>
              <p className="mt-0.5 text-sm text-zinc-600 dark:text-zinc-400">
                View device activity and detection alerts
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {user && (
              <>
                <span className="text-sm text-zinc-600 dark:text-zinc-400">{user.username}</span>
                <button
                  type="button"
                  onClick={handleLogout}
                  disabled={loggingOut}
                  className="rounded-md bg-zinc-200 px-4 py-2 text-sm font-medium text-zinc-800 hover:bg-zinc-300 disabled:opacity-50 dark:bg-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-600"
                >
                  {loggingOut ? '…' : 'Logout'}
                </button>
              </>
            )}
            <Link
              href="/register"
              className="rounded-md bg-zinc-200 px-4 py-2 text-sm font-medium text-zinc-800 hover:bg-zinc-300 dark:bg-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-600"
            >
              Register
            </Link>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-6 sm:px-6">
        {data?.devices && data.devices.length > 0 ? (
          <>
            <div className="mb-4 flex flex-wrap items-center gap-2">
              {data.devices.map((device) => (
                <div key={device.id} className="flex items-center gap-1">
                  <button
                    type="button"
                    onClick={() => setSelectedDeviceId(device.id)}
                    className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
                      selectedDeviceId === device.id
                        ? 'bg-emerald-600 text-white dark:bg-emerald-500'
                        : 'bg-zinc-200 text-zinc-700 hover:bg-zinc-300 dark:bg-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-600'
                    }`}
                  >
                    {device.label}
                  </button>
                  <button
                    type="button"
                    onClick={() => handleRemoveDevice(device.id, device.label)}
                    disabled={deletingId === device.id}
                    className="rounded-lg p-2 text-zinc-500 hover:bg-red-100 hover:text-red-700 disabled:opacity-50 dark:hover:bg-red-900/30 dark:hover:text-red-400"
                    title="Remove device"
                  >
                    {deletingId === device.id ? '…' : '✕'}
                  </button>
                </div>
              ))}
            </div>
            {selectedDevice && (
              <div className="mb-4 rounded-lg border border-zinc-200 bg-zinc-50 px-4 py-2 dark:border-zinc-700 dark:bg-zinc-800/50">
                <p className="text-xs font-medium text-zinc-500 dark:text-zinc-400">Device UUID (for extension)</p>
                <p className="font-mono text-sm text-zinc-800 dark:text-zinc-200" title={selectedDevice.uuid}>
                  {selectedDevice.uuid}
                </p>
                <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="text-xs font-medium text-zinc-500 dark:text-zinc-400">API key</p>
                    <p className="font-mono text-sm text-zinc-800 dark:text-zinc-200" title={apiKey}>
                      {apiKey}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    {copyStatus && (
                      <span className="text-xs text-zinc-500 dark:text-zinc-400">{copyStatus}</span>
                    )}
                    <button
                      type="button"
                      onClick={handleCopyApiKey}
                      className="rounded-md bg-zinc-200 px-3 py-2 text-sm font-medium text-zinc-800 hover:bg-zinc-300 dark:bg-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-600"
                    >
                      Copy API key
                    </button>
                  </div>
                </div>
                <p className="mt-0.5 text-xs text-zinc-500 dark:text-zinc-400">
                  Type: {selectedDevice.device_type === 'agentic' ? 'Agentic' : 'Control'}
                  {selectedDevice.device_type === 'agentic' && selectedDevice.agentic_prompt && (
                    <> · Prompt: {selectedDevice.agentic_prompt.slice(0, 60)}{selectedDevice.agentic_prompt.length > 60 ? '…' : ''}</>
                  )}
                </p>
              </div>
            )}
            <section className="mb-6 rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-700 dark:bg-zinc-900">
              <h3 className="mb-3 text-sm font-medium text-zinc-700 dark:text-zinc-300">Add a device</h3>
              <form onSubmit={handleAddDevice} className="flex flex-wrap items-end gap-3">
                {addDeviceError && (
                  <p className="w-full text-sm text-red-600 dark:text-red-400">{addDeviceError}</p>
                )}
                <div>
                  <label htmlFor="new-device-label" className="block text-xs text-zinc-500 dark:text-zinc-400">
                    Label
                  </label>
                  <input
                    id="new-device-label"
                    type="text"
                    value={addLabel}
                    onChange={(e) => setAddLabel(e.target.value)}
                    placeholder="e.g. Laptop, Tablet"
                    className="mt-0.5 rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-600 dark:bg-zinc-800 dark:text-zinc-100"
                  />
                </div>
                <div>
                  <label htmlFor="new-device-type" className="block text-xs text-zinc-500 dark:text-zinc-400">
                    Type
                  </label>
                  <select
                    id="new-device-type"
                    value={addDeviceType}
                    onChange={(e) => setAddDeviceType(e.target.value as 'control' | 'agentic')}
                    className="mt-0.5 rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-600 dark:bg-zinc-800 dark:text-zinc-100"
                  >
                    <option value="control">Control (predetermined settings)</option>
                    <option value="agentic">Agentic (parent-defined AI prompt)</option>
                  </select>
                </div>
                {addDeviceType === 'agentic' && (
                  <div className="min-w-[240px]">
                    <label htmlFor="new-device-prompt" className="block text-xs text-zinc-500 dark:text-zinc-400">
                      Agentic prompt
                    </label>
                    <input
                      id="new-device-prompt"
                      type="text"
                      value={addAgenticPrompt}
                      onChange={(e) => setAddAgenticPrompt(e.target.value)}
                      placeholder="Prompt for agentic AI"
                      className="mt-0.5 w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-600 dark:bg-zinc-800 dark:text-zinc-100"
                    />
                  </div>
                )}
                <button
                  type="submit"
                  disabled={addDeviceLoading || !addLabel.trim() || (addDeviceType === 'agentic' && !addAgenticPrompt.trim())}
                  className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50 dark:bg-emerald-500 dark:hover:bg-emerald-600"
                >
                  {addDeviceLoading ? 'Adding…' : 'Add device'}
                </button>
              </form>
            </section>
            <section>
              <h2 className="mb-3 text-lg font-medium text-zinc-900 dark:text-zinc-100">
                Visited websites {selectedDevice && `— ${selectedDevice.label}`}
              </h2>
              <VisitedSitesTable sites={sites} />
            </section>
          </>
        ) : (
          <div className="rounded-lg border border-zinc-200 bg-white p-8 dark:border-zinc-700 dark:bg-zinc-900">
            <p className="mb-4 text-zinc-600 dark:text-zinc-400">
              Add a device to start tracking browsing. Each device gets a unique UUID for the extension. Choose Control (predetermined settings) or Agentic (you set a prompt for the AI).
            </p>
            <form onSubmit={handleAddDevice} className="max-w-md space-y-3">
              {addDeviceError && (
                <p className="text-sm text-red-600 dark:text-red-400">{addDeviceError}</p>
              )}
              <div>
                <label htmlFor="first-device-label" className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
                  Label
                </label>
                <input
                  id="first-device-label"
                  type="text"
                  required
                  value={addLabel}
                  onChange={(e) => setAddLabel(e.target.value)}
                  placeholder="e.g. Kids laptop"
                  className="mt-1 w-full rounded-md border border-zinc-300 px-3 py-2 dark:border-zinc-600 dark:bg-zinc-800 dark:text-zinc-100"
                />
              </div>
              <div>
                <label htmlFor="first-device-type" className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
                  Type
                </label>
                <select
                  id="first-device-type"
                  value={addDeviceType}
                  onChange={(e) => setAddDeviceType(e.target.value as 'control' | 'agentic')}
                  className="mt-1 w-full rounded-md border border-zinc-300 px-3 py-2 dark:border-zinc-600 dark:bg-zinc-800 dark:text-zinc-100"
                >
                  <option value="control">Control (predetermined settings, TBD)</option>
                  <option value="agentic">Agentic (parent enters a prompt for agentic AI)</option>
                </select>
              </div>
              {addDeviceType === 'agentic' && (
                <div>
                  <label htmlFor="first-device-prompt" className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
                    Agentic prompt
                  </label>
                  <textarea
                    id="first-device-prompt"
                    required={addDeviceType === 'agentic'}
                    value={addAgenticPrompt}
                    onChange={(e) => setAddAgenticPrompt(e.target.value)}
                    placeholder="Enter the prompt for the agentic AI on this device"
                    rows={3}
                    className="mt-1 w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-600 dark:bg-zinc-800 dark:text-zinc-100"
                  />
                </div>
              )}
              <button
                type="submit"
                disabled={addDeviceLoading || !addLabel.trim() || (addDeviceType === 'agentic' && !addAgenticPrompt.trim())}
                className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50 dark:bg-emerald-500 dark:hover:bg-emerald-600"
              >
                {addDeviceLoading ? 'Adding…' : 'Add device'}
              </button>
            </form>
          </div>
        )}
      </main>
    </div>
  );
}
