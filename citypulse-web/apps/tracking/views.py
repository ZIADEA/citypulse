from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .forms import DeliveryConfirmationForm
from .models import DeliveryProof, DeliveryTracking


@login_required
def confirm_delivery(request):
    if request.method == "POST":
        form = DeliveryConfirmationForm(request.POST, request.FILES)
        if form.is_valid():
            ref = form.cleaned_data["order_ref"]
            tracking, _ = DeliveryTracking.objects.get_or_create(
                order_ref=ref,
                defaults={"order_id_ext": ref, "status": "pending"},
            )
            tracking.status = form.cleaned_data["status"]
            tracking.driver_first_name = request.user.first_name or request.user.username
            if form.cleaned_data.get("eta"):
                tracking.eta = form.cleaned_data["eta"]
            tracking.save()
            DeliveryProof.objects.create(
                order_id_ext=tracking.order_id_ext,
                photo=form.cleaned_data.get("photo"),
                signature=form.cleaned_data.get("signature") or "",
            )
            messages.success(request, "Delivery updated.")
    return redirect(request.META.get("HTTP_REFERER", "/driver/"))


@login_required
def client_track(request, ref):
    tracking = get_object_or_404(DeliveryTracking, order_ref=ref)
    return render(request, "client/track.html", {"tracking": tracking})


def public_track(request, ref):
    tracking = get_object_or_404(DeliveryTracking, order_ref=ref)
    driver_name = tracking.driver_first_name or "Driver"
    return render(request, "public/track.html", {"tracking": tracking, "driver_name": driver_name})
