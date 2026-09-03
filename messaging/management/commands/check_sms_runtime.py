from datetime import timedelta

from celery import current_app
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count
from django.utils import timezone

from messaging.models import Message


class Command(BaseCommand):
    help = "Controle l'etat operationnel des envois SMS et du worker Celery."

    def add_arguments(self, parser):
        parser.add_argument(
            "--max-pending",
            type=int,
            default=100,
            help="Nombre maximum de SMS pending accepte avant alerte.",
        )
        parser.add_argument(
            "--max-pending-age-minutes",
            type=int,
            default=10,
            help="Age maximum accepte pour le plus ancien SMS pending.",
        )
        parser.add_argument(
            "--max-due-scheduled",
            type=int,
            default=0,
            help="Nombre maximum de SMS programmes echus encore en scheduled.",
        )
        parser.add_argument(
            "--skip-celery",
            action="store_true",
            help="Ne controle pas la reponse du worker Celery.",
        )

    def handle(self, *args, **options):
        errors = []
        now = timezone.now()

        pending_qs = Message.objects.filter(status="pending")
        pending_count = pending_qs.count()
        pending_by_type = list(
            pending_qs.values("message_type").annotate(total=Count("id")).order_by("message_type")
        )
        oldest_pending = pending_qs.order_by("created_at").first()

        self.stdout.write(f"SMS pending: {pending_count}")
        self.stdout.write(f"Pending par type: {pending_by_type or 'aucun'}")

        if pending_count > options["max_pending"]:
            errors.append(
                f"{pending_count} SMS pending depassent le seuil de {options['max_pending']}."
            )

        if oldest_pending:
            age = now - oldest_pending.created_at
            age_minutes = int(age.total_seconds() // 60)
            self.stdout.write(
                f"Plus ancien pending: #{oldest_pending.id}, age {age_minutes} min"
            )
            if age > timedelta(minutes=options["max_pending_age_minutes"]):
                errors.append(
                    "Le plus ancien SMS pending a "
                    f"{age_minutes} min, seuil {options['max_pending_age_minutes']} min."
                )
        else:
            self.stdout.write("Aucun SMS pending.")

        due_scheduled_count = Message.objects.filter(
            status="scheduled",
            scheduled_at__lte=now,
        ).count()
        self.stdout.write(f"SMS programmes echus non traites: {due_scheduled_count}")

        if due_scheduled_count > options["max_due_scheduled"]:
            errors.append(
                f"{due_scheduled_count} SMS scheduled echus restent non traites."
            )

        if not options["skip_celery"]:
            inspector = current_app.control.inspect(timeout=5)
            pings = inspector.ping() or {}
            self.stdout.write(f"Workers Celery detectes: {len(pings)}")
            if not pings:
                errors.append("Aucun worker Celery ne repond au ping.")

        if errors:
            for error in errors:
                self.stderr.write(self.style.ERROR(error))
            raise CommandError("Controle runtime SMS en erreur.")

        self.stdout.write(self.style.SUCCESS("Controle runtime SMS OK."))
