from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import connection
import os


class Command(BaseCommand):
    help = 'Resets a user password from environment variables (RESET_USER_EMAIL / RESET_USER_PASSWORD)'

    def handle(self, *args, **options):
        User = get_user_model()
        email = os.environ.get('RESET_USER_EMAIL')
        password = os.environ.get('RESET_USER_PASSWORD')

        # Always print the DB the build is connected to — this is the crucial
        # diagnostic that tells us whether we're on Postgres or SQLite.
        self.stdout.write('--- reset_password diagnostic ---')
        self.stdout.write(f'DB engine: {connection.settings_dict["ENGINE"]}')
        self.stdout.write(f'DB host:   {connection.settings_dict["HOST"]}')
        self.stdout.write(f'DB name:   {connection.settings_dict["NAME"]}')
        self.stdout.write('----------------------------------')

        if not email or not password:
            self.stdout.write(
                self.style.WARNING(
                    'RESET_USER_EMAIL or RESET_USER_PASSWORD not set — skipping.'
                )
            )
            return

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(
                    f'User {email} does not exist in this database. '
                    f'Create it first via createsuperuser or the API.'
                )
            )
            return

        user.set_password(password)
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.save()

        # Re-fetch from DB to confirm the hash was actually persisted
        user.refresh_from_db()
        ok = user.check_password(password)

        self.stdout.write(
            self.style.SUCCESS(
                f'Password reset for {email}. '
                f'check_password = {ok}. '
                f'is_staff = {user.is_staff}, '
                f'is_superuser = {user.is_superuser}, '
                f'is_active = {user.is_active}'
            )
        )