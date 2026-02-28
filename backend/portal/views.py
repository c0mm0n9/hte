import json
import uuid as uuid_module
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from .models import Device, DeviceWhitelist, DeviceBlacklist, VisitedSite


def _parse_api_key(key):
    """Parse api_key string into (uuid_str, device_type) or (None, None). Accepts -agent as -agentic."""
    if not key or not isinstance(key, str):
        return None, None
    key = key.strip()
    uuid_part, sep, type_part = key.rpartition('-')
    if not sep or not uuid_part or not type_part:
        return None, None
    type_part = type_part.lower().strip()
    if type_part == 'agent':
        type_part = Device.TYPE_AGENTIC
    if type_part not in (Device.TYPE_CONTROL, Device.TYPE_AGENTIC):
        return None, None
    try:
        parsed = uuid_module.UUID(uuid_part)
        return str(parsed), type_part
    except (ValueError, TypeError):
        return None, None

# Predetermined suggested lists (parent can add these in one click)
SUGGESTED_WHITELIST = [
    'youtube.com',
    'kids.youtube.com',
    'pbskids.org',
    'nickjr.com',
    'disneyjunior.com',
    'khanacademy.org',
    'duolingo.com',
    'nationalgeographic.com',
    'abcya.com',
]
SUGGESTED_BLACKLIST = [
    'pornhub.com',
    'xvideos.com',
    'xnxx.com',
    'redtube.com',
    'youporn.com',
    'xhamster.com',
]


def _require_parent(view_func):
    """Decorator: return 401 if request.user is not an authenticated parent."""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Authentication required'}, status=401)
        return view_func(request, *args, **kwargs)
    return wrapper


def _serialize_visited_site(site):
    return {
        'id': site.id,
        'url': site.url,
        'title': site.title or '',
        'visited_at': site.visited_at.isoformat(),
        'updated_at': getattr(site, 'updated_at', site.visited_at).isoformat(),
        'has_harmful_content': getattr(site, 'has_harmful_content', site.harmful_content_detected),
        'has_pii': getattr(site, 'has_pii', False),
        'has_predators': getattr(site, 'has_predators', False),
        'ai_detected': site.ai_detected,
        'fake_news_detected': site.fake_news_detected,
        'harmful_content_detected': site.harmful_content_detected,
        'notes': site.notes or '',
    }


def _serialize_device(device):
    return {
        'id': device.id,
        'label': device.label,
        'uuid': str(device.uuid),
        'device_type': device.device_type,
        'api_key': f"{device.uuid}-{device.device_type}",
        'agentic_prompt': device.agentic_prompt or '',
        'whitelist': [{'id': e.id, 'value': e.value} for e in device.whitelist_entries.all()],
        'blacklist': [{'id': e.id, 'value': e.value} for e in device.blacklist_entries.all()],
    }


@_require_parent
def api_devices_list(request):
    """GET: list devices. POST: create a device (body: label, device_type, agentic_prompt?)."""
    if request.method == 'GET':
        devices = Device.objects.filter(parent=request.user).order_by('label')
        return JsonResponse({
            'devices': [_serialize_device(d) for d in devices],
        })
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        label = (data.get('label') or '').strip()
        if not label:
            return JsonResponse({'error': 'Label is required'}, status=400)
        device_type = (data.get('device_type') or Device.TYPE_CONTROL).strip()
        if device_type not in (Device.TYPE_CONTROL, Device.TYPE_AGENTIC):
            device_type = Device.TYPE_CONTROL
        agentic_prompt = (data.get('agentic_prompt') or '').strip()
        if device_type == Device.TYPE_CONTROL and not agentic_prompt:
            return JsonResponse({'error': 'Control prompt is required for control devices'}, status=400)
        device = Device.objects.create(
            parent=request.user,
            label=label,
            device_type=device_type,
            agentic_prompt=agentic_prompt if device_type == Device.TYPE_CONTROL else '',
        )
        for value in SUGGESTED_WHITELIST:
            DeviceWhitelist.objects.get_or_create(device=device, value=value)
        for value in SUGGESTED_BLACKLIST:
            DeviceBlacklist.objects.get_or_create(device=device, value=value)
        # Refetch with prefetch so response includes whitelist/blacklist
        device = Device.objects.prefetch_related('whitelist_entries', 'blacklist_entries').get(pk=device.pk)
        return JsonResponse({**_serialize_device(device), 'status': 'created'})
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@require_http_methods(['DELETE'])
@_require_parent
def api_device_delete(request, device_id):
    """Delete a device; only allowed if it belongs to the authenticated parent."""
    device = Device.objects.filter(parent=request.user, pk=device_id).first()
    if not device:
        return JsonResponse({'error': 'Device not found'}, status=404)
    device.delete()
    return JsonResponse({'status': 'deleted'})


def _get_device_for_parent(request, device_id):
    """Return device if it belongs to request.user, else None."""
    return Device.objects.filter(parent=request.user, pk=device_id).first()


@require_POST
@_require_parent
def api_device_whitelist_add(request, device_id):
    """Add a whitelist entry. Body: { value: string }."""
    device = _get_device_for_parent(request, device_id)
    if not device:
        return JsonResponse({'error': 'Device not found'}, status=404)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    value = (data.get('value') or '').strip()
    if not value:
        return JsonResponse({'error': 'value is required'}, status=400)
    if len(value) > 500:
        return JsonResponse({'error': 'value too long'}, status=400)
    entry, created = DeviceWhitelist.objects.get_or_create(device=device, value=value)
    return JsonResponse({'id': entry.id, 'value': entry.value, 'status': 'created' if created else 'exists'})


@require_http_methods(['DELETE'])
@_require_parent
def api_device_whitelist_delete(request, device_id, entry_id):
    """Remove a whitelist entry."""
    device = _get_device_for_parent(request, device_id)
    if not device:
        return JsonResponse({'error': 'Device not found'}, status=404)
    entry = DeviceWhitelist.objects.filter(device=device, pk=entry_id).first()
    if not entry:
        return JsonResponse({'error': 'Whitelist entry not found'}, status=404)
    entry.delete()
    return JsonResponse({'status': 'deleted'})


@require_POST
@_require_parent
def api_device_blacklist_add(request, device_id):
    """Add a blacklist entry. Body: { value: string }."""
    device = _get_device_for_parent(request, device_id)
    if not device:
        return JsonResponse({'error': 'Device not found'}, status=404)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    value = (data.get('value') or '').strip()
    if not value:
        return JsonResponse({'error': 'value is required'}, status=400)
    if len(value) > 500:
        return JsonResponse({'error': 'value too long'}, status=400)
    entry, created = DeviceBlacklist.objects.get_or_create(device=device, value=value)
    return JsonResponse({'id': entry.id, 'value': entry.value, 'status': 'created' if created else 'exists'})


@require_http_methods(['DELETE'])
@_require_parent
def api_device_blacklist_delete(request, device_id, entry_id):
    """Remove a blacklist entry."""
    device = _get_device_for_parent(request, device_id)
    if not device:
        return JsonResponse({'error': 'Device not found'}, status=404)
    entry = DeviceBlacklist.objects.filter(device=device, pk=entry_id).first()
    if not entry:
        return JsonResponse({'error': 'Blacklist entry not found'}, status=404)
    entry.delete()
    return JsonResponse({'status': 'deleted'})


@require_GET
@_require_parent
def api_visited_sites_list(request, device_id=None):
    """List visited sites for the parent's devices only, optionally filtered by device_id."""
    qs = VisitedSite.objects.filter(device__parent=request.user).select_related('device').order_by('-visited_at')
    if device_id:
        qs = qs.filter(device_id=device_id)
    sites = qs[:500]  # limit for performance
    return JsonResponse({
        'visited_sites': [_serialize_visited_site(s) for s in sites],
    })


@csrf_exempt
@require_GET
def api_validate_key(request):
    """Validate API key for extension. GET ?api_key=<key>. Returns { valid, mode } (mode: control | agentic). When mode is control, also returns prompt (parent-defined prompt for the device)."""
    api_key = (request.GET.get('api_key') or '').strip()
    if not api_key:
        return JsonResponse({'valid': False, 'error': 'api_key required'}, status=400)
    uuid_str, device_type = _parse_api_key(api_key)
    if uuid_str is None:
        return JsonResponse({'valid': False, 'error': 'Invalid api_key format'}, status=400)
    try:
        device = Device.objects.get(uuid=uuid_str, device_type=device_type)
    except Device.DoesNotExist:
        return JsonResponse({'valid': False, 'error': 'Device not found'}, status=404)
    payload = {'valid': True, 'mode': device.device_type}
    if device.device_type == Device.TYPE_CONTROL:
        payload['prompt'] = device.agentic_prompt or ''
    return JsonResponse(payload)


@csrf_exempt
@require_GET
def api_blacklist(request):
    """Return blacklist for extension. GET ?api_key=<key>. Returns { blacklist: [value, ...] }."""
    api_key = (request.GET.get('api_key') or '').strip()
    if not api_key:
        return JsonResponse({'error': 'api_key required'}, status=400)
    uuid_str, device_type = _parse_api_key(api_key)
    if uuid_str is None:
        return JsonResponse({'error': 'Invalid api_key format'}, status=400)
    try:
        device = Device.objects.get(uuid=uuid_str, device_type=device_type)
    except Device.DoesNotExist:
        return JsonResponse({'error': 'Device not found'}, status=404)
    values = list(device.blacklist_entries.values_list('value', flat=True))
    return JsonResponse({'blacklist': values})


@csrf_exempt
@require_POST
def api_record_visit(request):
    """Record a site visit from the extension/API gateway.

    Body supports:
    - api_key: "<uuid>-<type>" (preferred), e.g. "73ee...-control" / "73ee...-agentic"
    - device_id: int pk or uuid string (fallback)
    - url, title?, ai_detected?, fake_news_detected?, harmful_content_detected?, notes?
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    api_key = data.get('api_key')
    device_id = data.get('device_id')  # can be int (pk) or uuid string
    url = data.get('url')
    if (api_key is None and device_id is None) or not url:
        return JsonResponse({'error': 'api_key (or device_id) and url required'}, status=400)

    # Do not record Google search in visited list
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        hostname = (parsed.netloc or '').lower().lstrip('www.')
        path = (parsed.path or '').lower()
        if 'google' in hostname and '/search' in path:
            return JsonResponse({'status': 'skipped', 'reason': 'google_search'})
    except Exception:
        pass

    device = None
    if isinstance(api_key, str) and api_key.strip():
        uuid_str, device_type = _parse_api_key(api_key.strip())
        if uuid_str is None:
            return JsonResponse({'error': 'Invalid api_key format'}, status=400)
        try:
            device = Device.objects.get(uuid=uuid_str, device_type=device_type)
        except Device.DoesNotExist:
            return JsonResponse({'error': 'Device not found'}, status=404)
    else:
        try:
            if isinstance(device_id, int) or (isinstance(device_id, str) and device_id.isdigit()):
                device = Device.objects.get(pk=int(device_id))
            else:
                device = Device.objects.get(uuid=device_id)
        except (Device.DoesNotExist, ValueError):
            return JsonResponse({'error': 'Device not found'}, status=404)

    title = (data.get('title') or '').strip()
    has_harmful = bool(data.get('has_harmful_content', data.get('harmful_content_detected', False)))
    has_pii = bool(data.get('has_pii', False))
    has_predators = bool(data.get('has_predators', False))
    notes = (data.get('notes') or '').strip()

    from django.utils import timezone
    now = timezone.now()
    site, created = VisitedSite.objects.update_or_create(
        device=device,
        url=url,
        defaults={
            'title': title,
            'visited_at': now,
            'updated_at': now,
            'has_harmful_content': has_harmful,
            'has_pii': has_pii,
            'has_predators': has_predators,
            'ai_detected': bool(data.get('ai_detected', False)),
            'fake_news_detected': bool(data.get('fake_news_detected', False)),
            'harmful_content_detected': has_harmful,
            'notes': notes,
        },
    )
    return JsonResponse({'id': site.id, 'status': 'created' if created else 'updated'})


@require_POST
def api_login(request):
    """Log in a parent. Body: username, password. Requires CSRF token in X-CSRFToken header."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    if not username or not password:
        return JsonResponse({'error': 'Username and password required'}, status=400)
    user = authenticate(request, username=username, password=password)
    if user is None:
        return JsonResponse({'error': 'Invalid username or password'}, status=401)
    login(request, user)
    return JsonResponse({'user': {'id': user.id, 'username': user.username}})


@require_POST
def api_logout(request):
    """Log out the current user. Requires CSRF token in X-CSRFToken header."""
    logout(request)
    return JsonResponse({'status': 'ok'})


@require_GET
def api_me(request):
    """Return current user if authenticated, else 401."""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Not authenticated'}, status=401)
    return JsonResponse({'user': {'id': request.user.id, 'username': request.user.username}})


@ensure_csrf_cookie
@require_GET
def api_csrf(request):
    """Return CSRF token for use in login/logout POST requests (frontend on different origin cannot read cookie)."""
    from django.middleware.csrf import get_token
    token = get_token(request)
    return JsonResponse({'csrfToken': token})


@csrf_exempt
@require_POST
def api_register(request):
    """Register a new parent account. Body: username, password, email (required)."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    email = (data.get('email') or '').strip()
    if not username:
        return JsonResponse({'error': 'Username is required'}, status=400)
    if not email:
        return JsonResponse({'error': 'Email is required'}, status=400)
    if not password:
        return JsonResponse({'error': 'Password is required'}, status=400)
    if User.objects.filter(username=username).exists():
        return JsonResponse({'error': 'Username already taken'}, status=400)
    if User.objects.filter(email=email).exists():
        return JsonResponse({'error': 'Email already registered'}, status=400)
    if len(password) < 8:
        return JsonResponse({'error': 'Password must be at least 8 characters'}, status=400)
    user = User.objects.create_user(username=username, password=password, email=email)
    return JsonResponse({'id': user.id, 'username': user.username, 'status': 'created'})


@require_GET
@_require_parent
def api_dashboard(request):
    """Dashboard summary: only the authenticated parent's devices and their visits."""
    devices = (
        Device.objects.filter(parent=request.user)
        .order_by('label')
        .prefetch_related('whitelist_entries', 'blacklist_entries')
    )
    result = {'devices': []}
    for device in devices:
        sites = VisitedSite.objects.filter(device=device).order_by('-visited_at')[:100]
        result['devices'].append({
            **_serialize_device(device),
            'visited_sites': [_serialize_visited_site(s) for s in sites],
        })
    return JsonResponse(result)
