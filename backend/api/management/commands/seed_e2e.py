from django.core.management.base import BaseCommand
from django.db import transaction

from artifact_history.models import ArtifactHistory
from authentication.models import User
from custom_schemas.models import CustomSchema


DEFAULT_E2E_EMAIL = "e2e.user@example.com"
DEFAULT_E2E_PASSWORD = "E2E-Test#123"
DEFAULT_E2E_NAME = "E2E User"
DEFAULT_E2E_SCHEMA_NAME = "E2E Baseline Schema"
DEFAULT_E2E_SCHEMA_DESCRIPTION = "Reusable schema seeded for Playwright behavioral tests."

SEEDED_HISTORIES = (
    {
        "original_name": "e2e-upload-report.pdf",
        "custom_name": "",
        "status_processing": "completed",
        "output_json": {
            "document_info": {
                "source_type": "PDF",
                "filename": "e2e-upload-report.pdf",
            },
            "summary": {
                "total_rows": 1,
                "total_columns": 5,
            },
            "content_data": [
                {
                    "table_name": "Page 1",
                    "headers": ["unit", "item", "num_type", "status_type", "value"],
                    "rows": [
                        {
                            "unit": "Finance",
                            "item": "Revenue",
                            "num_type": "amount",
                            "status_type": "actual",
                            "value": 125000000,
                        }
                    ],
                }
            ],
        },
    },
    {
        "original_name": "e2e-budget-snapshot.xlsx",
        "custom_name": "E2E Budget Snapshot",
        "status_processing": "completed",
        "output_json": {
            "document_info": {
                "source_type": "Excel",
                "filename": "e2e-budget-snapshot.xlsx",
            },
            "summary": {
                "total_sheets": 1,
                "total_rows": 2,
                "total_columns": 5,
            },
            "content_data": [
                {
                    "table_name": "Sheet1",
                    "headers": ["unit", "item", "num_type", "status_type", "value"],
                    "rows": [
                        {
                            "unit": "Operations",
                            "item": "Travel",
                            "num_type": "expense",
                            "status_type": "target",
                            "value": 15000000,
                        }
                    ],
                }
            ],
        },
    },
)


def build_schema_definition():
    return {
        "columns": [
            {
                "name": "unit",
                "description": "Business unit or grouping label.",
            },
            {
                "name": "item",
                "description": "The metric or line item being recorded.",
            },
            {
                "name": "value",
                "description": "The numeric value for the selected item.",
            },
        ]
    }


class Command(BaseCommand):
    help = "Seed deterministic data for Playwright behavioral tests."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Reset the seeded e2e user's schema and history data before recreating it.",
        )
        parser.add_argument("--email", default=DEFAULT_E2E_EMAIL)
        parser.add_argument("--password", default=DEFAULT_E2E_PASSWORD)
        parser.add_argument("--name", default=DEFAULT_E2E_NAME)

    @transaction.atomic
    def handle(self, *args, **options):
        email = options["email"].strip().lower()
        password = options["password"]
        name = options["name"].strip() or DEFAULT_E2E_NAME

        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "name": name,
                "status": "verified",
            },
        )

        user.name = name
        user.status = "verified"
        user.set_password(password)
        user.save(update_fields=["name", "status", "password"])

        if options["reset"]:
            ArtifactHistory.objects.filter(owner=user).delete()
            CustomSchema.objects.filter(owner=user).delete()

        CustomSchema.objects.update_or_create(
            owner=user,
            name=DEFAULT_E2E_SCHEMA_NAME,
            defaults={
                "description": DEFAULT_E2E_SCHEMA_DESCRIPTION,
                "is_active": False,
                "definition": build_schema_definition(),
            },
        )

        for seeded_history in SEEDED_HISTORIES:
            ArtifactHistory.objects.update_or_create(
                owner=user,
                original_name=seeded_history["original_name"],
                defaults={
                    "custom_name": seeded_history["custom_name"],
                    "status_processing": seeded_history["status_processing"],
                    "output_json": seeded_history["output_json"],
                },
            )

        self.stdout.write(
            self.style.SUCCESS(
                f'Playwright e2e data ready for "{email}". '
                f"User created: {created}. "
                f"Schemas: {CustomSchema.objects.filter(owner=user).count()}, "
                f'Histories: {ArtifactHistory.objects.filter(owner=user).count()}'
            )
        )
