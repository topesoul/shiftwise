# /workspace/shiftwise/accounts/management/commands/cleanup_profile_pictures.py

import logging

from django.core.management.base import BaseCommand

from accounts.models import Profile

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Cleans up profile picture references that point to non-existent files"

    def handle(self, *args, **options):
        self.stdout.write("Starting profile picture cleanup...")
        fixed_count = 0
        total_profiles = Profile.objects.filter(profile_picture__isnull=False).count()

        for profile in Profile.objects.filter(profile_picture__isnull=False):
            if not profile.profile_picture.storage.exists(profile.profile_picture.name):
                old_path = profile.profile_picture.name
                profile.profile_picture = None
                profile.save(update_fields=["profile_picture"])
                logger.info(
                    f"Fixed orphaned profile picture reference for user {profile.user.username}: {old_path}"
                )
                fixed_count += 1
                self.stdout.write(f"Fixed: {profile.user.username} - {old_path}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Cleanup complete! Fixed {fixed_count} out of {total_profiles} profile picture references."
            )
        )
