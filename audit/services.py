from .models import AuditLog


def log_action(actor, action, obj=None, summary="", data=None):
    
    AuditLog.objects.create(
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        action=action,
        object_type=obj.__class__.__name__ if obj is not None else "",
        object_id=obj.pk if obj is not None else None,
        summary=summary[:300],
        data=data or {},
    )