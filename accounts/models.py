from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "Scheduler / Admin"
        NURSE = "nurse", "Nurse"

    role = models.CharField(max_length=10, choices=Role.choices, default=Role.NURSE)
    phone = models.CharField(max_length=20, blank=True)

    def save(self, *args, **kwargs):
        if self.is_superuser:
            self.role = self.Role.ADMIN
        super().save(*args, **kwargs)

    @property
    def is_scheduler(self) -> bool:
        return self.role == self.Role.ADMIN

    def __str__(self):
        return self.get_full_name() or self.username