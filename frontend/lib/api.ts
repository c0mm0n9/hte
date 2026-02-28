// Use same origin so requests go through the Next.js proxy (app/api/portal/[...path]), and session cookies work over HTTP
const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? '';

const defaultCredentials: RequestInit['credentials'] = 'include';

export type VisitedSite = {
  id: number;
  url: string;
  title: string;
  visited_at: string;
  updated_at?: string;
  has_harmful_content: boolean;
  has_pii: boolean;
  has_predators: boolean;
  ai_detected?: boolean;
  fake_news_detected?: boolean;
  harmful_content_detected?: boolean;
  notes: string;
};

export type ListEntry = { id: number; value: string };

export type Device = {
  id: number;
  label: string;
  uuid: string;
  device_type: 'control' | 'agentic';
  agentic_prompt: string;
  whitelist: ListEntry[];
  blacklist: ListEntry[];
};

export type DashboardDevice = Device & {
  visited_sites: VisitedSite[];
};

export type DashboardResponse = {
  devices: DashboardDevice[];
};

export async function fetchDashboard(): Promise<DashboardResponse> {
  const res = await fetch(`${API_BASE}/api/portal/dashboard/`, {
    cache: 'no-store',
    credentials: defaultCredentials,
  });
  if (res.status === 401) throw new Error('Not authenticated');
  if (!res.ok) throw new Error('Failed to fetch dashboard');
  return res.json();
}

export type UserInfo = { id: number; username: string };

export async function fetchCsrfToken(): Promise<string> {
  const res = await fetch(`${API_BASE}/api/portal/csrf/`, { credentials: defaultCredentials });
  if (!res.ok) throw new Error('Failed to get CSRF token');
  const data = await res.json();
  return data.csrfToken ?? '';
}

export async function fetchMe(): Promise<{ user: UserInfo }> {
  const res = await fetch(`${API_BASE}/api/portal/me/`, {
    credentials: defaultCredentials,
  });
  if (!res.ok) throw new Error('Not authenticated');
  return res.json();
}

export async function login(username: string, password: string): Promise<{ user: UserInfo }> {
  const csrfToken = await fetchCsrfToken();
  const res = await fetch(`${API_BASE}/api/portal/login/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': csrfToken,
    },
    credentials: defaultCredentials,
    body: JSON.stringify({ username, password }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || 'Login failed');
  return data;
}

export async function logout(): Promise<void> {
  const csrfToken = await fetchCsrfToken();
  await fetch(`${API_BASE}/api/portal/logout/`, {
    method: 'POST',
    headers: { 'X-CSRFToken': csrfToken },
    credentials: defaultCredentials,
  });
}

export type RegisterPayload = {
  username: string;
  password: string;
  email: string;
};

export type RegisterResponse = {
  id: number;
  username: string;
  status: string;
};

export async function registerAdmin(payload: RegisterPayload): Promise<RegisterResponse> {
  const res = await fetch(`${API_BASE}/api/portal/register/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: defaultCredentials,
    body: JSON.stringify(payload),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.error || 'Registration failed');
  }
  return data;
}

export type CreateDevicePayload = {
  label: string;
  device_type: 'control' | 'agentic';
  agentic_prompt?: string;
};

export async function createDevice(payload: CreateDevicePayload): Promise<Device & { status: string }> {
  const csrfToken = await fetchCsrfToken();
  const res = await fetch(`${API_BASE}/api/portal/devices/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': csrfToken,
    },
    credentials: defaultCredentials,
    body: JSON.stringify({
      label: payload.label,
      device_type: payload.device_type,
      agentic_prompt: payload.agentic_prompt ?? '',
    }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || 'Failed to add device');
  return data;
}

export async function deleteDevice(deviceId: number): Promise<void> {
  const csrfToken = await fetchCsrfToken();
  const res = await fetch(`${API_BASE}/api/portal/devices/${deviceId}/`, {
    method: 'DELETE',
    headers: { 'X-CSRFToken': csrfToken },
    credentials: defaultCredentials,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || 'Failed to remove device');
}

export async function addWhitelistEntry(deviceId: number, value: string): Promise<ListEntry> {
  const csrfToken = await fetchCsrfToken();
  const res = await fetch(`${API_BASE}/api/portal/devices/${deviceId}/whitelist/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': csrfToken,
    },
    credentials: defaultCredentials,
    body: JSON.stringify({ value }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || 'Failed to add whitelist entry');
  return { id: data.id, value: data.value };
}

export async function deleteWhitelistEntry(deviceId: number, entryId: number): Promise<void> {
  const csrfToken = await fetchCsrfToken();
  const res = await fetch(`${API_BASE}/api/portal/devices/${deviceId}/whitelist/${entryId}/`, {
    method: 'DELETE',
    headers: { 'X-CSRFToken': csrfToken },
    credentials: defaultCredentials,
  });
  if (!res.ok) throw new Error('Failed to remove whitelist entry');
}

export async function addBlacklistEntry(deviceId: number, value: string): Promise<ListEntry> {
  const csrfToken = await fetchCsrfToken();
  const res = await fetch(`${API_BASE}/api/portal/devices/${deviceId}/blacklist/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': csrfToken,
    },
    credentials: defaultCredentials,
    body: JSON.stringify({ value }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || 'Failed to add blacklist entry');
  return { id: data.id, value: data.value };
}

export async function deleteBlacklistEntry(deviceId: number, entryId: number): Promise<void> {
  const csrfToken = await fetchCsrfToken();
  const res = await fetch(`${API_BASE}/api/portal/devices/${deviceId}/blacklist/${entryId}/`, {
    method: 'DELETE',
    headers: { 'X-CSRFToken': csrfToken },
    credentials: defaultCredentials,
  });
  if (!res.ok) throw new Error('Failed to remove blacklist entry');
}
