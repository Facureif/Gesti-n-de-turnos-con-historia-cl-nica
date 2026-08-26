from django.core.management.base import BaseCommand
from datetime import date, datetime, timedelta
from turnos_profesionales.models import TurnoProfesional
from turnos_profesionales.notificaciones import notificar_recordatorio

class Command(BaseCommand):
    help = 'Envía recordatorio de turnos que comienzan en 1 hora'

    def handle(self, *args, **options):
        ahora = datetime.now()
        dentro_una_hora = ahora + timedelta(hours=1)
        turnos = TurnoProfesional.objects.filter(
            fecha=ahora.date(),
            hora_inicio__gte=ahora.time(),
            hora_inicio__lte=dentro_una_hora.time(),
            estado__in=['pendiente', 'confirmado']
        )
        for turno in turnos:
            notificar_recordatorio(turno, horas_antes=1)
            self.stdout.write(f"Recordatorio 1h enviado para turno {turno.id}")