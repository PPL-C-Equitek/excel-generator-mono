from django.db import models

class GroupMember(models.Model):
    npm = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=120)

    class Meta:
        ordering = ["npm"]

    def __str__(self):
        return f"{self.npm} - {self.name}"
