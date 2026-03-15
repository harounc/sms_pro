from django.core.management.base import BaseCommand
from django.utils import timezone

from messaging.models import Message
from messaging.services import send_sms


class Command(BaseCommand):
    help = "Envoie les SMS programmés"


    def handle(self, *args, **kwargs):

        now = timezone.now()

        scheduled_messages = Message.objects.filter(
            status='scheduled',
            scheduled_at__lte=now
        )

        count = 0

        for msg in scheduled_messages:

            result = send_sms(
                msg.user,
                msg.phone,
                msg.message,
                msg.message_type,
                msg.campaign
            )

            if result["success"]:

                msg.status = "sent"
                msg.sent_at = timezone.now()
                msg.save()

                count += 1

            else:

                msg.status = "failed"
                msg.save()

        self.stdout.write(self.style.SUCCESS(f"{count} SMS programmés envoyés."))