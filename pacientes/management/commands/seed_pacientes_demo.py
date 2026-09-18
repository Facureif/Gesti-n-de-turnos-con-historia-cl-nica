"""
Carga masiva de pacientes + turnos históricos (6 meses) + futuros (3 meses).
Solo usa agendas de Consultorio Salta + Gonzalo Martinez.
Incluye precios para probar el dashboard y la cobranza.

Uso:
    python manage.py seed_pacientes_demo
    python manage.py seed_pacientes_demo --reset   # solo limpia, no crea
"""

import random
from datetime import date, time, datetime, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from usuarios.models import Usuario
from obras_sociales.models import ObraSocial, Plan
from profesionales.models import Profesional
from agendas.models import Agenda
from establecimientos.models import Establecimiento
from pacientes.models import Paciente, PacienteObraSocial
from turnos_profesionales.models import TurnoProfesional


# ============ PACIENTES BASE (los que ya tenías) ============
PACIENTES_BASE = [
    ('pedro.rodriguez', '30123456', 'Pedro',    'Rodriguez', 'M', 'OSDE',          '210',     '3874001001'),
    ('maria.gonzalez',  '28765432', 'Maria',    'Gonzalez',  'F', 'OSDE',          '210',     '3874001002'),
    ('juan.perez',      '32123456', 'Juan',     'Perez',     'M', 'Swiss Medical', 'SMG-1',   '3874001003'),
    ('sofia.diaz',      '25678901', 'Sofia',    'Diaz',      'F', 'Galeno',        'Platino', '3874001004'),
    ('lucas.torres',    '33456789', 'Lucas',    'Torres',    'M', 'Galeno',        'Bronce',  '3874001005'),
    ('valentina.ruiz',  '28901234', 'Valentina','Ruiz',      'F', 'Galeno',        'Oro',     '3874001006'),
    ('mateo.flores',    '31234567', 'Mateo',    'Flores',    'M', None,             None,     '3874001007'),
    ('camila.sosa',     '27890123', 'Camila',   'Sosa',      'F', 'OSDE',          '310',     '3874001008'),
    ('benjamin.acosta', '34567890', 'Benjamin', 'Acosta',    'M', 'Swiss Medical', 'SMG-2',   '3874001009'),
    ('martina.medina',  '26789012', 'Martina',  'Medina',    'F', None,             None,     '3874001010'),
    ('mnuñez',          '26541322', 'Maxi',     'Nuñez',     'M', None,             None,     '3874001011'),
]

# ============ PACIENTES NUEVOS GENERADOS ============
NOMBRES_M = ['Santiago', 'Facundo', 'Tomas', 'Joaquin', 'Nicolas', 'Agustin',
             'Federico', 'Ramiro', 'Bruno', 'Emiliano', 'Lautaro', 'Thiago',
             'Gonzalo', 'Franco', 'Ivan', 'Leandro', 'Martin']
NOMBRES_F = ['Julieta', 'Martina', 'Catalina', 'Renata', 'Emilia', 'Guadalupe',
             'Malena', 'Micaela', 'Delfina', 'Antonella', 'Florencia', 'Josefina',
             'Milagros', 'Celeste', 'Agustina', 'Camila', 'Victoria']
APELLIDOS = ['Fernandez', 'Alvarez', 'Romero', 'Benitez', 'Villalba', 'Sosa',
             'Gimenez', 'Pereyra', 'Acosta', 'Molina', 'Cabrera', 'Silva',
             'Cordoba', 'Rojas', 'Maldonado', 'Figueroa', 'Medina', 'Herrera',
             'Rios', 'Chavez']

OBRAS_SOCIALES_DEMO = [
    ('OSDE', '210'), ('OSDE', '310'), ('OSDE', '410'),
    ('Swiss Medical', 'SMG-1'), ('Swiss Medical', 'SMG-2'), ('Swiss Medical', 'SMG-3'),
    ('Galeno', 'Bronce'), ('Galeno', 'Oro'), ('Galeno', 'Plata'), ('Galeno', 'Platino'),
    (None, None), (None, None),  # 2/12 van a particular para variedad
]


# ============ PRECIOS POR ESPECIALIDAD ============
PRECIO_PARTICULAR = {
    'kinesiologia': 35000,
    'odontologia': 45000,
    'nutricion': 30000,
    'psicologia': 40000,
    'fonoaudiologia': 35000,
    'medicina_general': 30000,
    'laboratorio': 25000,
}

PRECIO_OS = {
    'kinesiologia': 28000,
    'odontologia': 32000,
    'nutricion': 24000,
    'psicologia': 30000,
    'fonoaudiologia': 28000,
    'medicina_general': 24000,
    'laboratorio': 20000,
}

COSEGURO_DEFAULT = {
    'kinesiologia': 1500,
    'odontologia': 4000,
    'nutricion': 1200,
    'psicologia': 2000,
    'fonoaudiologia': 1500,
    'medicina_general': 1500,
    'laboratorio': 0,
}

TIPOS_CONSULTA = [
    'Primera consulta',
    'Control',
    'Seguimiento',
    'Certificado (escolar/laboral)',
    'Urgencia',
]


def buscar_os(nombre):
    if not nombre:
        return None
    return (
        ObraSocial.objects.filter(nombre__iexact=nombre).first()
        or ObraSocial.objects.filter(nombre__icontains=nombre).first()
        or ObraSocial.objects.filter(sigla__iexact=nombre).first()
    )


def siguiente_horario_libre(profesional, establecimiento, fecha):
    """Devuelve (hora_inicio, hora_fin) evitando colisiones."""
    slots_posibles = [
        time(9, 0), time(9, 45), time(10, 30), time(11, 15),
        time(14, 0), time(14, 45), time(15, 30), time(16, 15), time(17, 0),
    ]
    random.shuffle(slots_posibles)
    for h in slots_posibles:
        if not TurnoProfesional.objects.filter(
            profesional=profesional, establecimiento=establecimiento,
            fecha=fecha, hora_inicio=h,
            estado__in=['pendiente', 'confirmado', 'completado'],
        ).exists():
            return h
    return None


class Command(BaseCommand):
    help = 'Carga masiva de pacientes y turnos (6 meses históricos + 3 futuros)'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true', help='Solo limpia, sin recrear')

    @transaction.atomic
    def handle(self, *args, **options):
        random.seed(42)

        # ============ 1. LIMPIEZA ============
        self.stdout.write('=== Limpieza previa ===')
        # Borrar TODOS los turnos de demo (para hacerlo idempotente)
        agendas = Agenda.objects.filter(
            Q(establecimiento__nombre__icontains='Consultorio Salta') |
            Q(profesional__usuario__username='lic.martinez')
        )
        n_turnos = TurnoProfesional.objects.filter(
            Q(profesional__in=[a.profesional for a in agendas]) &
            Q(establecimiento__in=[a.establecimiento for a in agendas])
        ).delete()[0]

        # Borrar pacientes demo
        usernames_base = [p[0] for p in PACIENTES_BASE]
        pacientes_demo_previos = Paciente.objects.filter(
            Q(usuario__username__in=usernames_base) |
            Q(email__endswith='@demo.local')
        )
        PacienteObraSocial.objects.filter(paciente__in=pacientes_demo_previos).delete()
        pacientes_demo_previos.delete()
        Usuario.objects.filter(
            Q(username__in=usernames_base) | Q(email__endswith='@demo.local')
        ).delete()

        self.stdout.write(f'  🗑 {n_turnos} turnos eliminados')

        if options['reset']:
            self.stdout.write(self.style.SUCCESS('=== Reset completado ==='))
            return

        # ============ 2. PACIENTES ============
        self.stdout.write('')
        self.stdout.write('=== Cargando pacientes ===')

        # Sumar pacientes base + generados hasta llegar a 30
        pacientes_data = list(PACIENTES_BASE)
        objetivo = 30
        contador = 0
        while len(pacientes_data) < objetivo:
            genero = random.choice(['M', 'F'])
            nombre = random.choice(NOMBRES_M if genero == 'M' else NOMBRES_F)
            apellido = random.choice(APELLIDOS)
            username = f'{nombre.lower()}.{apellido.lower()}{contador}'
            dni = str(random.randint(20000000, 45000000))
            telefono = f'3874{random.randint(100000, 999999)}'
            os_nombre, plan_nombre = random.choice(OBRAS_SOCIALES_DEMO)
            pacientes_data.append((username, dni, nombre, apellido, genero, os_nombre, plan_nombre, telefono))
            contador += 1

        pacientes_creados = []
        hoy = date.today()

        for username, dni, nombre, apellido, genero, os_nombre, plan_nombre, telefono in pacientes_data:
            usuario = Usuario.objects.create_user(
                username=username,
                password=dni,
                first_name=nombre,
                last_name=apellido,
                rol='paciente',
                is_active=True,
                telefono=telefono,
            )
            paciente = Paciente.objects.create(
                usuario=usuario,
                nombre=nombre,
                apellido=apellido,
                genero=genero,
                dni=dni,
                telefono=telefono,
                email=f'{username}@demo.local',
                fecha_nacimiento=date(1960, 1, 1) + timedelta(days=random.randint(0, 15000)),
            )
            pacientes_creados.append(paciente)

            if os_nombre:
                os_obj = buscar_os(os_nombre)
                if os_obj:
                    plan_obj = Plan.objects.filter(
                        obra_social=os_obj, nombre=plan_nombre
                    ).first() if plan_nombre else None
                    paciente.obra_social = os_obj
                    paciente.plan_obra_social = plan_obj
                    paciente.save()

        self.stdout.write(f'  ✓ {len(pacientes_creados)} pacientes')

        # ============ 3. AGENDAS ============
        self.stdout.write('')
        self.stdout.write('=== Buscando agendas ===')

        agendas_disponibles = list(
            Agenda.objects.filter(activo=True).filter(
                Q(establecimiento__nombre__icontains='Consultorio Salta') |
                Q(profesional__usuario__username='lic.martinez')
            ).select_related('profesional', 'establecimiento')
        )

        if not agendas_disponibles:
            self.stdout.write(self.style.ERROR('No hay agendas disponibles'))
            return

        self.stdout.write(f'  → {len(agendas_disponibles)} agendas:')
        for a in agendas_disponibles:
            self.stdout.write(f'     · {a.profesional.nombre_completo} ({a.profesional.especialidad}) en {a.establecimiento.nombre}')

        # ============ 4. PacienteObraSocial por cada profesional ============
        self.stdout.write('')
        self.stdout.write('=== Asignando OS a pacientes por profesional ===')

        for paciente in pacientes_creados:
            if not paciente.obra_social:
                continue
            for agenda in agendas_disponibles:
                PacienteObraSocial.objects.get_or_create(
                    paciente=paciente, obra_social=paciente.obra_social,
                    plan=paciente.plan_obra_social,
                    profesional=agenda.profesional,
                    defaults={'activa': True},
                )

        # ============ 5. HISTÓRICOS (6 meses atrás) ============
        self.stdout.write('')
        self.stdout.write('=== Generando turnos históricos (6 meses) ===')

        # Estados históricos: mayoría completados
        estados_hist = ['completado'] * 8 + ['no_asistio'] * 1 + ['cancelado'] * 1
        turnos_hist_creados = 0

        # Cada profesional genera turnos de lunes a viernes en los últimos 180 días
        for agenda in agendas_disponibles:
            prof = agenda.profesional
            est = agenda.establecimiento
            esp = prof.especialidad

            for dia_offset in range(2, 180):
                fecha = hoy - timedelta(days=dia_offset)
                if fecha.weekday() >= 5:
                    continue

                # 35% de probabilidad de que tenga turnos ese día
                if random.random() > 0.35:
                    continue

                # 1 a 3 turnos por día
                n_turnos_dia = random.randint(1, 3)
                for _ in range(n_turnos_dia):
                    hora = siguiente_horario_libre(prof, est, fecha)
                    if not hora:
                        continue
                    hora_fin = (datetime.combine(fecha, hora) + timedelta(minutes=45)).time()

                    paciente = random.choice(pacientes_creados)
                    estado = random.choice(estados_hist)

                    # Precios solo aplican a completados
                    monto_total = None
                    monto_os = None
                    monto_coseguro = None
                    os_cobrado = False

                    if estado == 'completado':
                        if paciente.obra_social:
                            monto_os = PRECIO_OS.get(esp, 25000) + random.choice([-2000, 0, 0, 2000])
                            monto_coseguro = COSEGURO_DEFAULT.get(esp, 0) + random.choice([0, 0, 500, 1000])
                            monto_total = monto_os + monto_coseguro
                            os_cobrado = random.random() < 0.7  # 70% ya cobrado
                        else:
                            monto_total = PRECIO_PARTICULAR.get(esp, 30000) + random.choice([-3000, 0, 0, 0, 3000])
                            monto_os = 0
                            monto_coseguro = monto_total

                    TurnoProfesional.objects.create(
                        profesional=prof,
                        establecimiento=est,
                        paciente=paciente,
                        fecha=fecha,
                        hora_inicio=hora,
                        hora_fin=hora_fin,
                        estado=estado,
                        tipo_consulta=random.choice(TIPOS_CONSULTA),
                        no_asistio_automatico=(estado == 'no_asistio' and random.random() < 0.5),
                        monto_total=monto_total,
                        monto_os=monto_os,
                        monto_coseguro=monto_coseguro,
                        os_cobrado=os_cobrado,
                        fecha_cobro_os=(fecha + timedelta(days=15)) if os_cobrado else None,
                    )
                    turnos_hist_creados += 1

        self.stdout.write(f'  ✓ {turnos_hist_creados} turnos históricos')

        # ============ 6. FUTUROS (3 meses) ============
        self.stdout.write('')
        self.stdout.write('=== Generando turnos futuros (3 meses) ===')

        estados_fut = ['confirmado'] * 6 + ['pendiente'] * 3
        turnos_fut_creados = 0

        for agenda in agendas_disponibles:
            prof = agenda.profesional
            est = agenda.establecimiento

            for dia_offset in range(1, 90):
                fecha = hoy + timedelta(days=dia_offset)
                if fecha.weekday() >= 5:
                    continue

                # 50% de días con turnos
                if random.random() > 0.5:
                    continue

                # 1 a 2 turnos por día (mínimo 3 por semana por profesional)
                n_turnos_dia = random.randint(1, 2)
                for _ in range(n_turnos_dia):
                    hora = siguiente_horario_libre(prof, est, fecha)
                    if not hora:
                        continue
                    hora_fin = (datetime.combine(fecha, hora) + timedelta(minutes=45)).time()

                    paciente = random.choice(pacientes_creados)

                    TurnoProfesional.objects.create(
                        profesional=prof,
                        establecimiento=est,
                        paciente=paciente,
                        fecha=fecha,
                        hora_inicio=hora,
                        hora_fin=hora_fin,
                        estado=random.choice(estados_fut),
                        tipo_consulta=random.choice(TIPOS_CONSULTA),
                    )
                    turnos_fut_creados += 1

        self.stdout.write(f'  ✓ {turnos_fut_creados} turnos futuros')

        # ============ 7. RESUMEN ============
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=== Carga finalizada ==='))
        self.stdout.write('')
        self.stdout.write(f'Pacientes:       {Paciente.objects.count()}')
        self.stdout.write(f'Turnos totales:  {TurnoProfesional.objects.count()}')
        self.stdout.write(f'  · Históricos:  {turnos_hist_creados}')
        self.stdout.write(f'  · Futuros:     {turnos_fut_creados}')
        self.stdout.write('')
        self.stdout.write('Contraseña de pacientes demo: DNI')

        # Stats rápidas
        from django.db.models import Count
        por_estado = TurnoProfesional.objects.values('estado').annotate(n=Count('id')).order_by('-n')
        self.stdout.write('')
        self.stdout.write('Por estado:')
        for r in por_estado:
            self.stdout.write(f'  · {r["estado"]:12s} {r["n"]}')

        total_facturado = sum(
            TurnoProfesional.objects.filter(estado='completado').values_list('monto_total', flat=True)
            or [0]
        )
        self.stdout.write('')
        self.stdout.write(f'Facturación total completada: ${sum(t for t in TurnoProfesional.objects.filter(estado="completado").values_list("monto_total", flat=True) if t):,}')