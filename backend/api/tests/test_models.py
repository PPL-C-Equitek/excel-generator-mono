from django.test import TestCase

from api.models import GroupMember


class GroupMemberModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        GroupMember.objects.create(npm="2306152172", name="Siti Shofi Nadhifa")

    def test_group_member_string_representation(self):
        member = GroupMember.objects.get(npm="2306152172")
        self.assertEqual(str(member), "2306152172 - Siti Shofi Nadhifa")

