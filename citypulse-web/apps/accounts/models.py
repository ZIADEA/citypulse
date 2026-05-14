from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        DRIVER = "driver", "Driver"
        CLIENT = "client", "Client"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CLIENT)
    phone = models.CharField(max_length=32, blank=True)
    desktop_id = models.CharField(max_length=64, blank=True)
