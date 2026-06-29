from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction

from messaging.models import Message
from messaging.services import send_sms_api, apply_billing, calculate_sms_cost

class Command(BaseCommand):
    help = "Envoie les SMS programmés"

    def handle(self, *args, **kwargs):

        now = timezone.now()
        processed = 0
        sent = 0
        failed = 0
        skipped = 0

        messages = Message.objects.filter(
            status="scheduled",
            scheduled_at__lte=now
        )

        self.stdout.write(f"{messages.count()} SMS a traiter")

        for msg in messages:

            try:
                api_failed = False
                api_error = None

                with transaction.atomic():

                    # 🔄 recharge depuis DB
                    msg = Message.objects.select_for_update().get(pk=msg.pk)

                    if msg.status != "scheduled":
                        skipped += 1
                        continue

                    processed += 1
                    self.stdout.write(
                        f"Traitement SMS #{msg.id} - user={msg.user_id} cost={msg.cost}"
                    )

                    # ===============================
                    # 💰 FACTURATION (IMPORTANT)
                    # ===============================
                    sms_parts, _ = calculate_sms_cost(msg.message)

                    billing = apply_billing(
                        user=msg.user,
                        company=msg.company,
                        cost=msg.cost,
                        phone=msg.phone,
                        sms_parts=sms_parts
                    )

                    if not billing.get("success"):
                        failed += 1
                        msg.status = "failed"
                        msg.save(update_fields=["status"])
                        self.stdout.write(
                            self.style.WARNING(
                                f"SMS #{msg.id} echec facturation: {billing.get('error')}"
                            )
                        )
                        continue

                    # ===============================
                    # 📡 ENVOI
                    # ===============================
                    result = send_sms_api(msg.phone, msg.message)

                    if not result.get("success"):
                        api_failed = True
                        api_error = result.get("error")
                        transaction.set_rollback(True)
                    else:
                        # ===============================
                        # ✅ SUCCESS
                        # ===============================
                        msg.status = "sent"
                        msg.sent_at = timezone.now()
                        msg.save(update_fields=["status", "sent_at"])

                        sent += 1
                        self.stdout.write(self.style.SUCCESS(f"SMS #{msg.id} envoye"))

                if api_failed:
                    failed += 1
                    Message.objects.filter(pk=msg.pk).update(status="failed")
                    self.stdout.write(
                        self.style.ERROR(f"SMS #{msg.id} echec API: {api_error}")
                    )

            except Exception as e:

                failed += 1
                self.stdout.write(self.style.ERROR(f"SMS #{msg.id} erreur: {e}"))

                msg.status = "failed"
                msg.save(update_fields=["status"])

        self.stdout.write(
            self.style.SUCCESS(
                f"Fin traitement: {processed} traites, {sent} envoyes, "
                f"{failed} echoues, {skipped} ignores"
            )
        )
