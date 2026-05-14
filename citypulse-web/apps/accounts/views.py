from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect, render


def driver_login(request):
    if request.user.is_authenticated:
        if getattr(request.user, "role", "") == "driver" or request.user.is_staff:
            return redirect("/driver/")
        return redirect("/client/")

    error = None
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        user = authenticate(request, username=username, password=password)
        if user is None or not user.is_active:
            error = "Identifiant ou mot de passe incorrect."
        elif getattr(user, "role", "") not in ("driver",) and not user.is_staff:
            error = "Ce compte n'est pas un compte chauffeur."
        else:
            login(request, user)
            return redirect("/driver/")

    return render(request, "driver/login.html", {"error": error})


def client_login(request):
    if request.user.is_authenticated:
        if getattr(request.user, "role", "") == "client":
            return redirect("/client/")
        return redirect("/driver/")

    error = None
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        user = authenticate(request, username=username, password=password)
        if user is None or not user.is_active:
            error = "Identifiant ou mot de passe incorrect."
        elif getattr(user, "role", "") not in ("client",) and not user.is_staff:
            error = "Ce compte n'est pas un compte client."
        else:
            login(request, user)
            return redirect("/client/")

    return render(request, "client/login.html", {"error": error})


def do_logout(request):
    role = getattr(request.user, "role", "") if request.user.is_authenticated else ""
    logout(request)
    if role == "driver":
        return redirect("/driver/login/")
    return redirect("/client/login/")
