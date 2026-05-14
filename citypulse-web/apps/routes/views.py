from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.routes.models import DriverRoute
from apps.tracking.models import DeliveryTracking


def _is_driver(user):
    return getattr(user, "role", "") == "driver" or user.is_staff


def _is_client(user):
    return getattr(user, "role", "") == "client" or user.is_staff


@login_required(login_url="/driver/login/")
def home_redirect(request):
    if _is_driver(request.user) and not request.user.is_staff:
        return redirect("/driver/")
    if _is_client(request.user) and not request.user.is_staff:
        return redirect("/client/")
    # admin/staff : tableau de bord global
    User = get_user_model()
    ctx = {
        "route_count": DriverRoute.objects.count(),
        "delivery_count": DeliveryTracking.objects.count(),
        "user_count": User.objects.filter(is_active=True).count(),
        "recent_routes": DriverRoute.objects.order_by("-planned_date", "-id")[:5],
        "recent_deliveries": DeliveryTracking.objects.order_by("-last_update")[:5],
    }
    return render(request, "base_home.html", ctx)


@login_required(login_url="/driver/login/")
def driver_dashboard(request):
    if not _is_driver(request.user):
        return redirect("/client/")
    today = timezone.localdate()
    routes = DriverRoute.objects.filter(planned_date=today).order_by("id")
    return render(request, "driver/dashboard.html", {"routes": routes, "today": today})


@login_required(login_url="/driver/login/")
def driver_route_detail(request, route_id):
    if not _is_driver(request.user):
        return redirect("/client/")
    route = get_object_or_404(DriverRoute, pk=route_id)
    return render(request, "driver/route_detail.html", {"route": route})


@login_required(login_url="/driver/login/")
def driver_history(request):
    if not _is_driver(request.user):
        return redirect("/client/")
    start_date = timezone.localdate() - timedelta(days=30)
    routes = DriverRoute.objects.filter(planned_date__gte=start_date).order_by("-planned_date")
    return render(request, "driver/history.html", {"routes": routes})


@login_required(login_url="/client/login/")
def client_dashboard(request):
    if not _is_client(request.user):
        return redirect("/driver/")
    tracks = DeliveryTracking.objects.order_by("-last_update")[:50]
    return render(request, "client/dashboard.html", {"tracks": tracks})
