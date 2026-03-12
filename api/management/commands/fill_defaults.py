from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from api.models import UserLifestyle, UserBudgetLocation

User = get_user_model()

class Command(BaseCommand):
    help = "Fill default lifestyle and budget data"

    def handle(self, *args, **kwargs):

        for user in User.objects.all():

            # Lifestyle
            lifestyle, created = UserLifestyle.objects.get_or_create(
                user=user,
                defaults={
                    "sleep_schedule": "Balanced",
                    "cleanliness": "Organized",
                    "social_interaction": "Moderate"
                }
            )

            if created:
                self.stdout.write(f"Created lifestyle for: {user.email}")

            # Budget & Location
            budget, created = UserBudgetLocation.objects.get_or_create(
                user=user,
                defaults={
                    "monthly_budget": 5000,
                    "preferred_city": "Chennai"
                }
            )

            if created:
                self.stdout.write(f"Created budget for: {user.email}")