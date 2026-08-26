from django.core.management.base import BaseCommand
from datetime import date, timedelta
from turnos_profesionales.models import TurnoProfesional
from turnos_profesionales.notificaciones import notificar_recordatorio

class Command(BaseCommand):
    help = 'Envía recordatorio de turnos para mañana'

    def handle(self, *args, **options):
        manana = date.today() + timedelta(days=1)
        turnos = TurnoProfesional.objects.filter(
            fecha=manana,
            estado__in=['pendiente', 'confirmado']
        )
        for turno in turnos:
            notificar_recordatorio(turno, horas_antes=24)
            self.stdout.write(f"Recordatorio enviado para turno {turno.id}")