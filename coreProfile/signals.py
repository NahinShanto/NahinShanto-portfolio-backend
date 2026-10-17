import logging

from django.conf import settings
from django.core.mail import send_mail
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Comment, Post, Profile, Project

logger = logging.getLogger("devfolio.signals")


@receiver(post_save, sender=Comment)
def notify_new_comment(sender, instance, created, **kwargs):
    if not created or instance.is_approved:
        return
    profile = Profile.get_solo()
    recipient = profile.email if profile else settings.DEFAULT_FROM_EMAIL
    subject = f"New comment awaiting approval on '{instance.post.title}'"
    body = f"{instance.name} ({instance.email}) wrote:\n\n{instance.content}\n"
    logger.info("Signal: %s", subject)
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [recipient])  # console-এ ছাপা হবে
    except Exception:
        logger.exception("Could not send the new-comment email")


@receiver(post_delete, sender=Post)
def delete_post_cover(sender, instance, **kwargs):
    if instance.cover_image:
        instance.cover_image.delete(save=False)  # disk থেকে ফাইলও মোছে


@receiver(post_delete, sender=Project)
def delete_project_cover(sender, instance, **kwargs):
    if instance.cover_image:
        instance.cover_image.delete(save=False)