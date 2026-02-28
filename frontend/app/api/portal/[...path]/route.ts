import { NextRequest, NextResponse } from 'next/server';

// Use 127.0.0.1 so Django is reachable when localhost resolves to IPv6 (::1)
const DJANGO_API = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

function getCookieHeader(request: NextRequest): string {
  const cookie = request.headers.get('cookie');
  return cookie || '';
}

function copySetCookies(djangoResponse: Response, nextResponse: NextResponse): void {
  const setCookies = djangoResponse.headers.getSetCookie?.() ?? [];
  for (const cookie of setCookies) {
    nextResponse.headers.append('Set-Cookie', cookie);
  }
  const legacy = djangoResponse.headers.get('set-cookie');
  if (legacy && setCookies.length === 0) {
    nextResponse.headers.append('Set-Cookie', legacy);
  }
}

export async function GET(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  const pathStr = path.filter(Boolean).join('/');
  const url = `${DJANGO_API}/api/portal/${pathStr}/`;
  const cookie = getCookieHeader(request);
  const res = await fetch(url, {
    headers: { cookie },
    cache: 'no-store',
  });
  const body = await res.text();
  const nextResponse = new NextResponse(body, { status: res.status, statusText: res.statusText });
  nextResponse.headers.set('Content-Type', res.headers.get('Content-Type') || 'application/json');
  copySetCookies(res, nextResponse);
  return nextResponse;
}

export async function POST(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  const pathStr = path.filter(Boolean).join('/');
  const url = `${DJANGO_API}/api/portal/${pathStr}/`;
  const cookie = getCookieHeader(request);
  const contentType = request.headers.get('content-type') || '';
  const csrf = request.headers.get('x-csrftoken') || '';
  const body = await request.text();
  const headers: Record<string, string> = { cookie };
  if (contentType) headers['Content-Type'] = contentType;
  if (csrf) headers['X-CSRFToken'] = csrf;
  const res = await fetch(url, {
    method: 'POST',
    body,
    headers,
  });
  const resBody = await res.text();
  const nextResponse = new NextResponse(resBody, { status: res.status, statusText: res.statusText });
  nextResponse.headers.set('Content-Type', res.headers.get('Content-Type') || 'application/json');
  copySetCookies(res, nextResponse);
  return nextResponse;
}

export async function DELETE(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  const pathStr = path.filter(Boolean).join('/');
  const url = `${DJANGO_API}/api/portal/${pathStr}/`;
  const cookie = getCookieHeader(request);
  const csrf = request.headers.get('x-csrftoken') || '';
  const headers: Record<string, string> = { cookie };
  if (csrf) headers['X-CSRFToken'] = csrf;
  const res = await fetch(url, { method: 'DELETE', headers });
  const resBody = await res.text();
  const nextResponse = new NextResponse(resBody, { status: res.status, statusText: res.statusText });
  nextResponse.headers.set('Content-Type', res.headers.get('Content-Type') || 'application/json');
  copySetCookies(res, nextResponse);
  return nextResponse;
}
