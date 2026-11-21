from django.contrib.auth.signals import user_logged_in
from django.db.backends.signals import connection_created
from django.dispatch import receiver


@receiver(connection_created)
def configure_sqlite(sender, connection, **kwargs):
    if connection.vendor != "sqlite":
        return
    with connection.cursor() as cursor:
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.execute("PRAGMA busy_timeout=5000;")
        cursor.execute("PRAGMA synchronous=NORMAL;")


@receiver(user_logged_in)
def log_login(sender, request, user, **kwargs):
    from audit.services import log

    log(
        actor=user,
        action="login",
        entity_type="user",
        entity_id=str(user.pk),
        summary=f"{user.username} signed in",
        request=request,
    )
