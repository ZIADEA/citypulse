import json
from datetime import date, datetime

from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from apps.api.models import SyncLog
from apps.routes.models import DriverRoute
from apps.tracking.models import DeliveryProof, DeliveryTracking


def _authorized(request):
    return request.headers.get("X-CityPulse-Secret", "") == settings.CITYPULSE_API_SECRET


def _json_body(request):
    try:
        return json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return {}


def _log(direction, kind, count, status, error_msg=""):
    SyncLog.objects.create(
        direction=direction,
        type=kind,
        records_count=count,
        status=status,
        error_msg=error_msg,
    )


def _serialize_dt(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


@require_GET
def health_check(request):
    return JsonResponse({"ok": True, "service": "citypulse-web", "timestamp": timezone.now().isoformat()})


@csrf_exempt
@require_POST
def sync_clients(request):
    if not _authorized(request):
        _log("in", "clients", 0, "error", "unauthorized")
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)
    payload = _json_body(request)
    if isinstance(payload, list):
        clients = payload
    else:
        clients = payload.get("clients", []) if isinstance(payload, dict) else []
    count = len(clients)
    _log("in", "clients", count, "success")
    return JsonResponse({"ok": True, "data": {"received": count}, "error": ""})


@csrf_exempt
@require_POST
def sync_routes(request):
    if not _authorized(request):
        _log("in", "routes", 0, "error", "unauthorized")
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)
    payload = _json_body(request)
    routes = payload.get("routes", []) if isinstance(payload, dict) else []
    created = 0
    for route in routes:
        planned_date = route.get("planned_date")
        if isinstance(planned_date, str):
            try:
                planned_date = date.fromisoformat(planned_date)
            except ValueError:
                planned_date = timezone.localdate()
        elif not planned_date:
            planned_date = timezone.localdate()

        DriverRoute.objects.create(
            vehicle_id_ext=str(route.get("vehicle_id", "")),
            driver_id_ext=str(route.get("driver_id", "")),
            planned_date=planned_date,
            stops_json=route.get("stops", []),
        )
        created += 1
    _log("in", "routes", created, "success")
    return JsonResponse({"ok": True, "data": {"received": created}, "error": ""})


@csrf_exempt
@require_GET
def deliveries_confirmations(request):
    if not _authorized(request):
        _log("out", "confirmations", 0, "error", "unauthorized")
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)
    rows = DeliveryTracking.objects.values(
        "order_id_ext", "order_ref", "status", "driver_first_name", "eta", "last_update"
    ).order_by("-last_update")[:500]
    items = []
    for row in rows:
        row["eta"] = _serialize_dt(row["eta"])
        row["last_update"] = _serialize_dt(row["last_update"])
        items.append(row)
    _log("out", "confirmations", len(items), "success")
    return JsonResponse({"ok": True, "data": items, "count": len(items)})


@csrf_exempt
@require_GET
def deliveries_proofs(request):
    if not _authorized(request):
        _log("out", "proofs", 0, "error", "unauthorized")
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)
    items = []
    for p in DeliveryProof.objects.order_by("-confirmed_at")[:500]:
        items.append(
            {
                "order_id_ext": p.order_id_ext,
                "photo_url": p.photo.url if p.photo else "",
                "signature": p.signature,
                "confirmed_at": p.confirmed_at.isoformat(),
            }
        )
    _log("out", "proofs", len(items), "success")
    return JsonResponse({"ok": True, "data": items, "count": len(items)})


@csrf_exempt
@require_POST
def create_web_user(request):
    if not _authorized(request):
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)
    from django.contrib.auth import get_user_model
    User = get_user_model()
    payload = _json_body(request)
    username = str(payload.get("username", "")).strip().lower()
    password = str(payload.get("password", "")).strip()
    role = str(payload.get("role", "client")).strip()
    first_name = str(payload.get("first_name", "")).strip()
    last_name = str(payload.get("last_name", "")).strip()
    email = str(payload.get("email", "")).strip()
    desktop_id = payload.get("desktop_id")
    if not username or not password:
        return JsonResponse({"ok": False, "error": "username and password required"}, status=400)
    if role not in ("client", "driver"):
        return JsonResponse({"ok": False, "error": "role must be client or driver"}, status=400)
    existing = None
    if desktop_id:
        existing = User.objects.filter(desktop_id=desktop_id, role=role).first()
    if not existing:
        existing = User.objects.filter(username=username).first()
    if existing:
        existing.set_password(password)
        existing.first_name = first_name or existing.first_name
        existing.last_name = last_name or existing.last_name
        existing.email = email or existing.email
        existing.desktop_id = desktop_id or existing.desktop_id
        existing.is_active = True
        existing.save()
        return JsonResponse({"ok": True, "created": False, "username": existing.username})
    base = username
    candidate = base
    n = 1
    while User.objects.filter(username=candidate).exists():
        candidate = f"{base}{n}"
        n += 1
    user = User.objects.create_user(
        username=candidate,
        password=password,
        role=role,
        first_name=first_name,
        last_name=last_name,
        email=email,
    )
    if desktop_id:
        user.desktop_id = desktop_id
        user.save(update_fields=["desktop_id"])
    _log("in", "user_create", 1, "success")
    return JsonResponse({"ok": True, "created": True, "username": candidate})


@csrf_exempt
@require_POST
def delivery_confirm(request):
    if not _authorized(request):
        _log("in", "delivery_confirm", 0, "error", "unauthorized")
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)

    payload = _json_body(request)
    order_ref = str(payload.get("order_ref", "")).strip()
    if not order_ref:
        _log("in", "delivery_confirm", 0, "error", "missing order_ref")
        return JsonResponse({"ok": False, "error": "order_ref is required"}, status=400)

    tracking, _ = DeliveryTracking.objects.get_or_create(
        order_ref=order_ref,
        defaults={"order_id_ext": str(payload.get("order_id_ext", order_ref)), "status": "pending"},
    )
    tracking.status = str(payload.get("status", tracking.status))
    tracking.driver_first_name = str(payload.get("driver_first_name", tracking.driver_first_name))
    eta_value = payload.get("eta")
    if eta_value:
        try:
            parsed = datetime.fromisoformat(str(eta_value).replace("Z", "+00:00"))
            tracking.eta = timezone.make_aware(parsed) if timezone.is_naive(parsed) else parsed
        except ValueError:
            pass
    tracking.save()

    DeliveryProof.objects.create(
        order_id_ext=tracking.order_id_ext,
        signature=str(payload.get("signature", "")),
    )
    _log("in", "delivery_confirm", 1, "success")
    return JsonResponse({"ok": True, "data": {"order_ref": order_ref}, "error": ""})
