from django.apps import AppConfig


class GovernanceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.governance"
    verbose_name = "Platform Governance"

    def ready(self):
        # Register signal handlers for audit logging
        import apps.governance.signals  # noqa: F401
