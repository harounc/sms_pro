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

        for msg in scheduled_messages:

            send_sms(
                msg.user,
                msg.phone,
                msg.message,
                msg.message_type,
                msg.campaign
            )

            msg.delete()

        self.stdout.write("SMS programmés traités.")