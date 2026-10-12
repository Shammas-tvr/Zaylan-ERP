from django.apps import AppConfig
from django.db.models.signals import post_migrate


class SubscriptionsConfig(AppConfig):
    name = "apps.subscriptions"
    label = "subscriptions"

    def ready(self) -> None:
        from .services import sync_feature_catalog_on_migrate

        post_migrate.connect(sync_feature_catalog_on_migrate, sender=self)
