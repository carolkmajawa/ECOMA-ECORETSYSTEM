from django.apps import AppConfig

class GroupsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.groups'
    verbose_name = 'Group Management'

    def ready(self):
        # Import signals to register them
        import apps.groups.signals