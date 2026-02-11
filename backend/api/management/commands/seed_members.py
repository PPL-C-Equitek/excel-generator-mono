from django.core.management.base import BaseCommand
from api.models import GroupMember


MEMBERS = [
    {"npm": "2306152172", "name": "Siti Shofi Nadhifa"},
    {"npm": "2306244961", "name": "Mirfak Naufal Pratama Putra"},
    {"npm": "2306152140", "name": "Arisha Shaista Aurelya"},
    {"npm": "2306202694", "name": "Zufar Romli Amri"},
    {"npm": "2306213426", "name": "Nayla Farah Nida"},
    {"npm": "2306203526", "name": "Belva Ghani Abhinaya"},
    {"npm": "2306152260", "name": "Steven Setiawan"},
]


class Command(BaseCommand):
    help = "Seed database with Group 7 members"

    def handle(self, *args, **options):
        created_count = 0
        updated_count = 0

        for member in MEMBERS:
            _, created = GroupMember.objects.update_or_create(
                npm=member["npm"],
                defaults={"name": member["name"]},
            )
            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Members seeded. Created: {created_count}, Updated: {updated_count}"
            )
        )
