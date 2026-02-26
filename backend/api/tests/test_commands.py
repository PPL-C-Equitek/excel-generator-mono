from django.core.management import call_command
from django.test import TestCase

from api.models import GroupMember


class SeedMembersCommandTest(TestCase):
    def test_seed_members_creates_expected_records(self):
        call_command("seed_members")
        self.assertEqual(GroupMember.objects.count(), 7)

    def test_seed_members_is_idempotent(self):
        call_command("seed_members")
        call_command("seed_members")
        self.assertEqual(GroupMember.objects.count(), 7)

