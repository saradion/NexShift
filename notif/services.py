from django.contrib.auth import get_user_model

from .models import Notification


def notify(users, title, message="", kind=Notification.Kind.INFO, related=None):
    unique = {u.pk: u for u in users if u is not None}.values()
    Notification.objects.bulk_create(
        [
            Notification(
                recipient=u,
                kind=kind,
                title=title[:150],
                message=message,
                related_type=related.__class__.__name__ if related is not None else "",
                related_id=related.pk if related is not None else None,
            )
            for u in unique
        ]
    )


def notify_admins(title, message="", kind=Notification.Kind.INFO, related=None):
    User = get_user_model()
    admins = User.objects.filter(role=User.Role.ADMIN, is_active=True)
    notify(admins, title, message, kind, related)