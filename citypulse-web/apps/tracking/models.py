from django.db import models


class DeliveryTracking(models.Model):
    order_id_ext = models.CharField(max_length=64)
    order_ref = models.CharField(max_length=100, db_index=True)
    status = models.CharField(max_length=32, default="pending")
    driver_first_name = models.CharField(max_length=150, blank=True)
    eta = models.DateTimeField(null=True, blank=True)
    last_update = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.order_ref


class DeliveryProof(models.Model):
    order_id_ext = models.CharField(max_length=64)
    photo = models.ImageField(upload_to="proofs/", blank=True)
    signature = models.TextField(blank=True)
    confirmed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Proof {self.order_id_ext}"
