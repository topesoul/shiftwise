# /workspace/shiftwise/accounts/signals.py

import logging
from io import BytesIO

from PIL import Image, ImageOps

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import Profile

logger = logging.getLogger(__name__)

User = get_user_model()

MAX_IMAGE_SIZE_MB = 5
MAX_SIZE = (500, 500)


@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    """Create or update Profile when User is saved."""
    if created:
        Profile.objects.create(user=instance)
        logger.info(f"Profile created for user {instance.username}.")
    else:
        instance.profile.save()
        logger.info(f"Profile updated for user {instance.username}.")


@receiver(post_save, sender=Profile)
def handle_profile_picture_resize(sender, instance, **kwargs):
    """Resize and optimize profile picture to MAX_SIZE with compression if needed."""
    if instance.profile_picture:
        try:
            # Verify file exists in storage
            if not instance.profile_picture.storage.exists(instance.profile_picture.name):
                logger.error(
                    f"Profile picture file does not exist: {instance.profile_picture.name}"
                )
                with transaction.atomic():
                    Profile.objects.filter(pk=instance.pk).update(profile_picture=None)
                logger.info(f"Reset missing profile picture for user {instance.user.username}")
                return

            # Check file size
            instance.profile_picture.seek(0, 2)
            file_size_mb = instance.profile_picture.size / (1024 * 1024)
            instance.profile_picture.seek(0)

            if file_size_mb > MAX_IMAGE_SIZE_MB:
                logger.warning(
                    f"Profile picture size ({file_size_mb:.2f} MB) exceeds limit ({MAX_IMAGE_SIZE_MB} MB). Resizing."
                )

            # Process image
            img_temp = BytesIO(instance.profile_picture.read())
            img = Image.open(img_temp)
            img = ImageOps.exif_transpose(img)
            img.thumbnail(MAX_SIZE, Image.LANCZOS)

            # Compress if necessary
            quality = 85
            max_size_bytes = MAX_IMAGE_SIZE_MB * 1024 * 1024

            img_temp = BytesIO()
            img.save(img_temp, format="JPEG", quality=quality)

            while img_temp.tell() > max_size_bytes and quality > 10:
                img_temp = BytesIO()
                img.save(img_temp, format="JPEG", quality=quality)
                quality -= 5

            # Convert to RGB for JPEG compatibility
            if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
                img = img.convert("RGB")

            # Save processed image
            img_io = BytesIO()
            img_format = img.format if img.format else "JPEG"
            img.save(img_io, format=img_format, quality=quality)

            with transaction.atomic():
                new_filename = f"processed_{instance.profile_picture.name.split('/')[-1]}"
                instance.profile_picture.save(
                    new_filename,
                    ContentFile(img_io.getvalue()),
                    save=False,
                )
                Profile.objects.filter(pk=instance.pk).update(
                    profile_picture=instance.profile_picture.name
                )

            logger.info(f"Profile picture resized for user {instance.user.username}.")
        except Exception as e:
            logger.error(f"Error resizing profile picture for {instance.user.username}: {e}")
            try:
                with transaction.atomic():
                    Profile.objects.filter(pk=instance.pk).update(profile_picture=None)
                logger.info(
                    f"Reset profile picture due to processing error for user {instance.user.username}"
                )
            except Exception as inner_e:
                logger.error(
                    f"Failed to reset profile picture for {instance.user.username}: {inner_e}"
                )


@receiver(pre_save, sender=Profile)
def delete_old_profile_picture(sender, instance, **kwargs):
    """Delete previous profile picture when a new one is uploaded."""
    if not instance.pk:
        return

    try:
        old_profile = Profile.objects.get(pk=instance.pk)
    except Profile.DoesNotExist:
        return

    old_picture = old_profile.profile_picture
    new_picture = instance.profile_picture

    if old_picture and old_picture != new_picture:
        try:
            # Preserve default profile image
            if "default_profile.png" not in old_picture.name:
                if old_picture.storage.exists(old_picture.name):
                    old_picture.delete(save=False)
                    logger.info(f"Deleted old profile picture for user {instance.user.username}.")
                else:
                    logger.warning(
                        f"Attempted to delete non-existent profile picture for user {instance.user.username}"
                    )
            else:
                logger.info(
                    f"Skipped deletion of default profile picture for user {instance.user.username}."
                )
        except Exception as e:
            logger.error(f"Error deleting old profile picture for {instance.user.username}: {e}")
