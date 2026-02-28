'use client';

import { useEffect, useState, useCallback } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import type { DashboardResponse, VisitedSite, UserInfo, ListEntry } from '@/lib/api';
import {
  fetchDashboard,
  fetchMe,
  logout,
  createDevice,
  deleteDevice,
  addWhitelistEntry,
  deleteWhitelistEntry,
  addBlacklistEntry,
  deleteBlacklistEntry,
} from '@/lib/api';

const DRAG_TYPE = 'application/x-hsafety-domain';

function getDomain(url: string): string {
  try {
    const hostname = new URL(url).hostname;
    return hostname.replace(/^www\./i, '') || hostname;
  } catch {
    return url;
  }
}

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

function VisitDetailModal({
  site,
  onClose,
}: {
  site: VisitedSite;
  onClose: () => void;
}) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="visit-detail-title"
    >
      <div
        className="w-full max-w-lg rounded-xl border border-zinc-200 bg-white shadow-xl dark:border-zinc-700 dark:bg-zinc-900"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-zinc-200 px-4 py-3 dark:border-zinc-700">
          <h2 id="visit-detail-title" className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
            Visit details
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-zinc-500 hover:bg-zinc-100 hover:text-zinc-700 dark:hover:bg-zinc-700 dark:hover:text-zinc-300"
            aria-label="Close"
          >
            ✕
          </button>
        </div>
        <div className="space-y-4 px-4 py-4">
          <div>
            <p className="text-xs font-medium uppercase tracking-wider text-zinc-500 dark:text-zinc-400">Title</p>
            <p className="mt-0.5 font-medium text-zinc-900 dark:text-zinc-100">
              {site.title || '—'}
            </p>
          </div>
          <div>
            <p className="text-xs font-medium uppercase tracking-wider text-zinc-500 dark:text-zinc-400">URL</p>
            <a
              href={site.url}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-0.5 block max-w-full truncate font-medium text-blue-600 hover:underline dark:text-blue-400"
              title={site.url}
            >
              {site.url}
            </a>
          </div>
          <div>
            <p className="text-xs font-medium uppercase tracking-wider text-zinc-500 dark:text-zinc-400">Visited</p>
            <p className="mt-0.5 text-zinc-700 dark:text-zinc-300">
              {new Date(site.visited_at).toLocaleString()}
            </p>
          </div>
          {site.updated_at && site.updated_at !== site.visited_at && (
            <div>
              <p className="text-xs font-medium uppercase tracking-wider text-zinc-500 dark:text-zinc-400">Last updated</p>
              <p className="mt-0.5 text-zinc-700 dark:text-zinc-300">
                {new Date(site.updated_at).toLocaleString()}
              </p>
            </div>
          )}
          <div className="flex flex-wrap gap-2">
            <span className="text-xs font-medium text-zinc-500 dark:text-zinc-400">Harmful content</span>
            <DetectionBadge value={site.has_harmful_content ?? site.harmful_content_detected ?? false} />
            <span className="text-xs font-medium text-zinc-500 dark:text-zinc-400">PII</span>
            <DetectionBadge value={site.has_pii ?? false} />
            <span className="text-xs font-medium text-zinc-500 dark:text-zinc-400">Predators</span>
            <DetectionBadge value={site.has_predators ?? false} />
          </div>
          {site.notes && (
            <div>
              <p className="text-xs font-medium uppercase tracking-wider text-zinc-500 dark:text-zinc-400">Notes</p>
              <p className="mt-0.5 text-zinc-700 dark:text-zinc-300 whitespace-pre-wrap">{site.notes}</p>
            </div>
          )}
          <div className="pt-2">
            <a
              href={site.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 dark:bg-emerald-500 dark:hover:bg-emerald-600"
            >
              Open website →
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}

function VisitedSitesTable({ sites, onSelectSite }: { sites: VisitedSite[]; onSelectSite?: (site: VisitedSite) => void }) {
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
              Harmful content
            </th>
            <th scope="col" className="px-4 py-3 text-center text-xs font-medium uppercase tracking-wider text-zinc-600 dark:text-zinc-400">
              PII
            </th>
            <th scope="col" className="px-4 py-3 text-center text-xs font-medium uppercase tracking-wider text-zinc-600 dark:text-zinc-400">
              Predators
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-200 bg-white dark:divide-zinc-700 dark:bg-zinc-900/30">
          {sites.map((site) => (
            <tr
              key={site.id}
              role="button"
              tabIndex={0}
              onClick={() => onSelectSite?.(site)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  onSelectSite?.(site);
                }
              }}
              className="cursor-pointer hover:bg-zinc-50 dark:hover:bg-zinc-800/30 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-inset"
            >
              <td className="px-4 py-3">
                <span className="max-w-[280px] truncate font-medium text-zinc-900 dark:text-zinc-100 block">
                  {site.title || site.url}
                </span>
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
                <DetectionBadge value={site.has_harmful_content ?? site.harmful_content_detected ?? false} />
              </td>
              <td className="px-4 py-3 text-center">
                <DetectionBadge value={site.has_pii ?? false} />
              </td>
              <td className="px-4 py-3 text-center">
                <DetectionBadge value={site.has_predators ?? false} />
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
  const [apiKeyRevealed, setApiKeyRevealed] = useState(false);
  const [selectedVisit, setSelectedVisit] = useState<VisitedSite | null>(null);
  const [newWhitelistValue, setNewWhitelistValue] = useState('');
  const [newBlacklistValue, setNewBlacklistValue] = useState('');
  const [listActionError, setListActionError] = useState<string | null>(null);
  const [listLoading, setListLoading] = useState(false);

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
    if (addDeviceType === 'control' && !addAgenticPrompt.trim()) return;
    setAddDeviceError(null);
    setAddDeviceLoading(true);
    try {
      await createDevice({
        label,
        device_type: addDeviceType,
        agentic_prompt: addDeviceType === 'control' ? addAgenticPrompt.trim() : undefined,
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

  useEffect(() => {
    setApiKeyRevealed(false);
    setListActionError(null);
  }, [selectedDeviceId]);

  const selectedDevice = data?.devices.find((d) => d.id === selectedDeviceId);

  const handleDropOnWhitelist = useCallback(
    async (e: React.DragEvent) => {
      e.preventDefault();
      const raw = e.dataTransfer.getData(DRAG_TYPE);
      if (!raw) return;
      const device = data?.devices.find((d) => d.id === selectedDeviceId);
      if (!device) return;
      let domain: string;
      let source: string;
      let entryId: number | undefined;
      try {
        const payload = JSON.parse(raw) as { domain: string; source: string; entryId?: number };
        domain = payload.domain?.trim();
        source = payload.source;
        entryId = payload.entryId;
      } catch {
        return;
      }
      if (!domain) return;
      setListActionError(null);
      setListLoading(true);
      try {
        await addWhitelistEntry(device.id, domain);
        if (source === 'blacklist' && entryId != null) {
          await deleteBlacklistEntry(device.id, entryId);
        }
        await refreshDashboard();
      } catch (err) {
        setListActionError(err instanceof Error ? err.message : 'Failed to add');
      } finally {
        setListLoading(false);
      }
    },
    [data, selectedDeviceId, refreshDashboard]
  );

  const handleDropOnBlacklist = useCallback(
    async (e: React.DragEvent) => {
      e.preventDefault();
      const raw = e.dataTransfer.getData(DRAG_TYPE);
      if (!raw) return;
      const device = data?.devices.find((d) => d.id === selectedDeviceId);
      if (!device) return;
      let domain: string;
      let source: string;
      let entryId: number | undefined;
      try {
        const payload = JSON.parse(raw) as { domain: string; source: string; entryId?: number };
        domain = payload.domain?.trim();
        source = payload.source;
        entryId = payload.entryId;
      } catch {
        return;
      }
      if (!domain) return;
      setListActionError(null);
      setListLoading(true);
      try {
        await addBlacklistEntry(device.id, domain);
        if (source === 'whitelist' && entryId != null) {
          await deleteWhitelistEntry(device.id, entryId);
        }
        await refreshDashboard();
      } catch (err) {
        setListActionError(err instanceof Error ? err.message : 'Failed to add');
      } finally {
        setListLoading(false);
      }
    },
    [data, selectedDeviceId, refreshDashboard]
  );

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

  const sites = selectedDevice?.visited_sites ?? [];
  const whitelistValues = new Set((selectedDevice?.whitelist ?? []).map((e) => e.value));
  const blacklistValues = new Set((selectedDevice?.blacklist ?? []).map((e) => e.value));
  const visitedDomainsAll = [...new Set(sites.map((s) => getDomain(s.url)))].sort();
  const visitedDomains = visitedDomainsAll.filter((d) => !whitelistValues.has(d) && !blacklistValues.has(d));
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
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-6 sm:px-6">
        {data?.devices && data.devices.length > 0 ? (
          <>
            <div className="mb-4 flex flex-wrap items-center gap-2">
              {data.devices.map((device) => (
                <div
                  key={device.id}
                  className={`inline-flex overflow-hidden rounded-lg text-sm font-medium transition-colors ${
                    selectedDeviceId === device.id
                      ? 'bg-emerald-600 text-white dark:bg-emerald-500'
                      : 'bg-zinc-200 text-zinc-700 hover:bg-zinc-300 dark:bg-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-600'
                  }`}
                >
                  <button
                    type="button"
                    onClick={() => setSelectedDeviceId(device.id)}
                    className="px-4 py-2 text-left"
                  >
                    {device.label}
                  </button>
                  <button
                    type="button"
                    onClick={(e) => { e.stopPropagation(); handleRemoveDevice(device.id, device.label); }}
                    disabled={deletingId === device.id}
                    className={`border-l px-2.5 py-2 transition-colors ${
                      selectedDeviceId === device.id
                        ? 'border-emerald-500/50 hover:bg-red-100 hover:text-red-700 dark:border-emerald-400/30 dark:hover:bg-red-900/30 dark:hover:text-red-400'
                        : 'border-zinc-300 dark:border-zinc-600 hover:bg-red-100 hover:text-red-700 dark:hover:bg-red-900/30 dark:hover:text-red-400'
                    } disabled:opacity-50`}
                    title="Remove device"
                  >
                    {deletingId === device.id ? '…' : '✕'}
                  </button>
                </div>
              ))}
            </div>
            {selectedDevice && (
              <div className="mb-4 rounded-lg border border-zinc-200 bg-zinc-50 px-4 py-2 dark:border-zinc-700 dark:bg-zinc-800/50">
                <p className="text-xs font-medium text-zinc-500 dark:text-zinc-400">Device UUID</p>
                <p className="font-mono text-sm text-zinc-800 dark:text-zinc-200" title={selectedDevice.uuid}>
                  {selectedDevice.uuid}
                </p>
                <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="text-xs font-medium text-zinc-500 dark:text-zinc-400">API key</p>
                    <button
                      type="button"
                      onClick={() => setApiKeyRevealed((v) => !v)}
                      className="mt-0.5 block min-w-[12rem] rounded bg-zinc-300/80 px-2 py-1 font-mono text-sm tabular-nums text-zinc-800 transition-[background-color,min-width] duration-200 ease-out dark:bg-zinc-700/80 dark:text-zinc-200 hover:bg-zinc-300 dark:hover:bg-zinc-600/80"
                      title={apiKeyRevealed ? 'Click to hide' : 'Click to reveal'}
                    >
                      {apiKeyRevealed ? apiKey : '••••••••••••••••••••••••••••••••'}
                    </button>
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
                  {selectedDevice.device_type === 'control' && selectedDevice.agentic_prompt && (
                    <> · Prompt: {selectedDevice.agentic_prompt.slice(0, 60)}{selectedDevice.agentic_prompt.length > 60 ? '…' : ''}</>
                  )}
                </p>
              </div>
            )}
            <section className="mb-6 rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-700 dark:bg-zinc-900">
              <h3 className="mb-3 text-sm font-medium text-zinc-700 dark:text-zinc-300">Add a device</h3>
              <form onSubmit={handleAddDevice} className="space-y-3">
                {addDeviceError && (
                  <p className="text-sm text-red-600 dark:text-red-400">{addDeviceError}</p>
                )}
                <div className="flex flex-col gap-4 sm:flex-row sm:items-start">
                  <div className="flex min-w-0 flex-1 flex-col gap-3 sm:max-w-xs">
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
                        className="mt-0.5 w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-600 dark:bg-zinc-800 dark:text-zinc-100"
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
                        className="mt-0.5 w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-600 dark:bg-zinc-800 dark:text-zinc-100"
                      >
                        <option value="agentic">Agentic (predetermined settings)</option>
                        <option value="control">Control (parent-defined prompt)</option>
                      </select>
                    </div>
                  </div>
                  {addDeviceType === 'control' && (
                    <div className="min-w-0 flex-1">
                      <label htmlFor="new-device-prompt" className="block text-xs text-zinc-500 dark:text-zinc-400">
                        Control prompt
                      </label>
                      <textarea
                        id="new-device-prompt"
                        value={addAgenticPrompt}
                        onChange={(e) => setAddAgenticPrompt(e.target.value)}
                        placeholder="Describe rules or goals for this device (e.g. what content to allow or flag)"
                        rows={5}
                        className="mt-0.5 w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-600 dark:bg-zinc-800 dark:text-zinc-100 resize-y min-h-[100px]"
                      />
                    </div>
                  )}
                </div>
                <button
                  type="submit"
                  disabled={addDeviceLoading || !addLabel.trim() || (addDeviceType === 'control' && !addAgenticPrompt.trim())}
                  className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50 dark:bg-emerald-500 dark:hover:bg-emerald-600"
                >
                  {addDeviceLoading ? 'Adding…' : 'Add device'}
                </button>
              </form>
            </section>
            {selectedDevice && (
              <section className="mb-6 rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-700 dark:bg-zinc-900">
                <h2 className="mb-3 text-lg font-medium text-zinc-900 dark:text-zinc-100">
                  Whitelist, Blacklist & Visited list {selectedDevice.label}
                </h2>
                <p className="mb-4 text-sm text-zinc-600 dark:text-zinc-400">
                  Allowed and blocked sites (customise below). Visited list shows domain names only. Drag a domain from any list and drop on another to add or move it.
                </p>
                {listActionError && (
                  <p className="mb-2 text-sm text-red-600 dark:text-red-400">{listActionError}</p>
                )}
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                  <div>
                    <h3 className="mb-2 text-sm font-medium text-zinc-700 dark:text-zinc-300">Whitelist</h3>
                    <div className="mb-2 flex gap-2">
                      <input
                        type="text"
                        value={newWhitelistValue}
                        onChange={(e) => { setNewWhitelistValue(e.target.value); setListActionError(null); }}
                        placeholder="e.g. pbskids.org"
                        className="min-w-0 flex-1 rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-600 dark:bg-zinc-800 dark:text-zinc-100"
                      />
                      <button
                        type="button"
                        disabled={listLoading || !newWhitelistValue.trim()}
                        onClick={async () => {
                          if (!selectedDevice || !newWhitelistValue.trim()) return;
                          setListActionError(null);
                          setListLoading(true);
                          try {
                            await addWhitelistEntry(selectedDevice.id, newWhitelistValue.trim());
                            setNewWhitelistValue('');
                            await refreshDashboard();
                          } catch (e) {
                            setListActionError(e instanceof Error ? e.message : 'Failed to add');
                          } finally {
                            setListLoading(false);
                          }
                        }}
                        className="shrink-0 rounded-md bg-zinc-200 px-3 py-2 text-sm font-medium text-zinc-800 dark:bg-zinc-700 dark:text-zinc-200"
                      >
                        Add
                      </button>
                    </div>
                    <ul
                      className="rounded border border-zinc-200 dark:border-zinc-700 max-h-40 overflow-y-auto"
                      onDragOver={(e) => e.preventDefault()}
                      onDrop={handleDropOnWhitelist}
                    >
                      {(selectedDevice.whitelist ?? []).length === 0 ? (
                        <li className="px-3 py-2 text-sm text-zinc-500 dark:text-zinc-400">No entries. Drop domains here.</li>
                      ) : (
                        (selectedDevice.whitelist ?? []).map((e: ListEntry) => (
                          <li
                            key={e.id}
                            draggable
                            onDragStart={(ev) => {
                              ev.dataTransfer.setData(DRAG_TYPE, JSON.stringify({ domain: e.value, source: 'whitelist', entryId: e.id }));
                              ev.dataTransfer.effectAllowed = 'move';
                            }}
                            className="flex cursor-grab active:cursor-grabbing items-center justify-between gap-2 border-b border-zinc-100 px-3 py-2 last:border-0 dark:border-zinc-700"
                          >
                            <span className="min-w-0 truncate font-mono text-sm text-zinc-800 dark:text-zinc-200">{e.value}</span>
                            <button
                              type="button"
                              disabled={listLoading}
                              onClick={async () => {
                                setListActionError(null);
                                setListLoading(true);
                                try {
                                  await deleteWhitelistEntry(selectedDevice.id, e.id);
                                  await refreshDashboard();
                                } catch (err) {
                                  setListActionError(err instanceof Error ? err.message : 'Failed to remove');
                                } finally {
                                  setListLoading(false);
                                }
                              }}
                              className="shrink-0 rounded p-1 text-red-600 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-900/30"
                              title="Remove"
                            >
                              ✕
                            </button>
                          </li>
                        ))
                      )}
                    </ul>
                  </div>
                  <div>
                    <h3 className="mb-2 text-sm font-medium text-zinc-700 dark:text-zinc-300">Blacklist</h3>
                    <div className="mb-2 flex gap-2">
                      <input
                        type="text"
                        value={newBlacklistValue}
                        onChange={(e) => { setNewBlacklistValue(e.target.value); setListActionError(null); }}
                        placeholder="e.g. domain.com"
                        className="min-w-0 flex-1 rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-600 dark:bg-zinc-800 dark:text-zinc-100"
                      />
                      <button
                        type="button"
                        disabled={listLoading || !newBlacklistValue.trim()}
                        onClick={async () => {
                          if (!selectedDevice || !newBlacklistValue.trim()) return;
                          setListActionError(null);
                          setListLoading(true);
                          try {
                            await addBlacklistEntry(selectedDevice.id, newBlacklistValue.trim());
                            setNewBlacklistValue('');
                            await refreshDashboard();
                          } catch (err) {
                            setListActionError(err instanceof Error ? err.message : 'Failed to add');
                          } finally {
                            setListLoading(false);
                          }
                        }}
                        className="shrink-0 rounded-md bg-zinc-200 px-3 py-2 text-sm font-medium text-zinc-800 dark:bg-zinc-700 dark:text-zinc-200"
                      >
                        Add
                      </button>
                    </div>
                    <ul
                      className="rounded border border-zinc-200 dark:border-zinc-700 max-h-40 overflow-y-auto"
                      onDragOver={(e) => e.preventDefault()}
                      onDrop={handleDropOnBlacklist}
                    >
                      {(selectedDevice.blacklist ?? []).length === 0 ? (
                        <li className="px-3 py-2 text-sm text-zinc-500 dark:text-zinc-400">No entries. Drop domains here.</li>
                      ) : (
                        (selectedDevice.blacklist ?? []).map((e: ListEntry) => (
                          <li
                            key={e.id}
                            draggable
                            onDragStart={(ev) => {
                              ev.dataTransfer.setData(DRAG_TYPE, JSON.stringify({ domain: e.value, source: 'blacklist', entryId: e.id }));
                              ev.dataTransfer.effectAllowed = 'move';
                            }}
                            className="flex cursor-grab active:cursor-grabbing items-center justify-between gap-2 border-b border-zinc-100 px-3 py-2 last:border-0 dark:border-zinc-700"
                          >
                            <span className="min-w-0 truncate font-mono text-sm text-zinc-800 dark:text-zinc-200">{e.value}</span>
                            <button
                              type="button"
                              disabled={listLoading}
                              onClick={async () => {
                                setListActionError(null);
                                setListLoading(true);
                                try {
                                  await deleteBlacklistEntry(selectedDevice.id, e.id);
                                  await refreshDashboard();
                                } catch (err) {
                                  setListActionError(err instanceof Error ? err.message : 'Failed to remove');
                                } finally {
                                  setListLoading(false);
                                }
                              }}
                              className="shrink-0 rounded p-1 text-red-600 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-900/30"
                              title="Remove"
                            >
                              ✕
                            </button>
                          </li>
                        ))
                      )}
                    </ul>
                  </div>
                  <div>
                    <h3 className="mb-2 text-sm font-medium text-zinc-700 dark:text-zinc-300">Visited list (domains only)</h3>
                    <ul className="rounded border border-zinc-200 dark:border-zinc-700 max-h-40 overflow-y-auto">
                      {visitedDomains.length === 0 ? (
                        <li className="px-3 py-2 text-sm text-zinc-500 dark:text-zinc-400">No visits yet.</li>
                      ) : (
                        visitedDomains.map((domain) => (
                          <li
                            key={domain}
                            draggable
                            onDragStart={(ev) => {
                              ev.dataTransfer.setData(DRAG_TYPE, JSON.stringify({ domain, source: 'visited' }));
                              ev.dataTransfer.effectAllowed = 'copy';
                            }}
                            className="cursor-grab active:cursor-grabbing border-b border-zinc-100 px-3 py-2 last:border-0 dark:border-zinc-700"
                          >
                            <span className="block min-w-0 truncate font-mono text-sm text-zinc-800 dark:text-zinc-200">{domain}</span>
                          </li>
                        ))
                      )}
                    </ul>
                  </div>
                </div>
              </section>
            )}
            <section>
              <h2 className="mb-3 text-lg font-medium text-zinc-900 dark:text-zinc-100">
                Visited list (full) {selectedDevice && `— ${selectedDevice.label}`}
              </h2>
              <p className="mb-2 text-sm text-zinc-500 dark:text-zinc-400">
                History with detection details. Click a row to view full details.
              </p>
              <VisitedSitesTable sites={sites} onSelectSite={setSelectedVisit} />
            </section>
            {selectedVisit && (
              <VisitDetailModal site={selectedVisit} onClose={() => setSelectedVisit(null)} />
            )}
          </>
        ) : (
          <div className="rounded-lg border border-zinc-200 bg-white p-8 dark:border-zinc-700 dark:bg-zinc-900">
            <p className="mb-4 text-zinc-600 dark:text-zinc-400">
              Add a device to start tracking browsing. Each device gets a unique UUID for the extension. Choose Agentic (predetermined settings) or Control (you set a prompt for this device).
            </p>
            <form onSubmit={handleAddDevice} className="space-y-3">
              {addDeviceError && (
                <p className="text-sm text-red-600 dark:text-red-400">{addDeviceError}</p>
              )}
              <div className="flex flex-col gap-4 sm:flex-row sm:items-start">
                <div className="flex min-w-0 flex-1 flex-col gap-3 sm:max-w-xs">
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
                      <option value="agentic">Agentic (predetermined settings)</option>
                      <option value="control">Control (parent-defined prompt)</option>
                    </select>
                  </div>
                </div>
                {addDeviceType === 'control' && (
                  <div className="min-w-0 flex-1">
                    <label htmlFor="first-device-prompt" className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
                      Control prompt
                    </label>
                    <textarea
                      id="first-device-prompt"
                      required={addDeviceType === 'control'}
                      value={addAgenticPrompt}
                      onChange={(e) => setAddAgenticPrompt(e.target.value)}
                      placeholder="Describe rules or goals for this device (e.g. what content to allow or flag)"
                      rows={6}
                      className="mt-1 w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-600 dark:bg-zinc-800 dark:text-zinc-100 resize-y min-h-[120px]"
                    />
                  </div>
                )}
              </div>
              <button
                type="submit"
                disabled={addDeviceLoading || !addLabel.trim() || (addDeviceType === 'control' && !addAgenticPrompt.trim())}
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
