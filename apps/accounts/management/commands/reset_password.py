from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
import os

class Command(BaseCommand):
    help = 'Resets a user password from environment variables'

    def handle(self, *args, **options):
        User = get_user_model()
        email = os.environ.get('RESET_USER_EMAIL')
        password = os.environ.get('RESET_USER_PASSWORD')
        
        if not email or not password:
            self.stdout.write(self.style.WARNING('RESET_USER_EMAIL or RESET_USER_PASSWORD not set. Skipping.'))
            return
        
        try:
            user = User.objects.get(email=email)
            user.set_password(password)
            user.is_staff = True
            user.is_superuser = True
            user.is_active = True
            user.save()
            self.stdout.write(self.style.SUCCESS(f'Successfully reset password for {email}'))
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'User {email} not found'))