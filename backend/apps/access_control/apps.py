from django.apps import AppConfig
from django.db.models.signals import post_migrate


class AccessControlConfig(AppConfig):
    name = "apps.access_control"
    label = "access_control"

    def ready(self) -> None:
        from .services import sync_permission_catalog_on_migrate

        post_migrate.connect(sync_permission_catalog_on_migrate, sender=self)
