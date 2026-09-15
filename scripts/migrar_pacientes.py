from pacientes.models import Paciente
from turnos_profesionales.models import TurnoProfesional

sin_consultorio = Paciente.objects.filter(establecimiento_creacion__isnull=True)
print(f"Pacientes sin consultorio: {sin_consultorio.count()}")

asignados_por_turno = 0
asignados_por_profesional = 0
sin_asignar = 0

for paciente in sin_consultorio:
    ultimo_turno = TurnoProfesional.objects.filter(
        paciente=paciente,
        establecimiento__isnull=False
    ).order_by('-fecha', '-hora_inicio').first()

    if ultimo_turno and ultimo_turno.establecimiento:
        paciente.establecimiento_creacion = ultimo_turno.establecimiento
        paciente.save(update_fields=['establecimiento_creacion'])
        asignados_por_turno += 1
        print(f"  OK {paciente.nombre_completo} -> {ultimo_turno.establecimiento.nombre} (por turno)")
        continue

    if paciente.creado_por:
        est = paciente.creado_por.establecimientos.first()
        if est:
            paciente.establecimiento_creacion = est
            paciente.save(update_fields=['establecimiento_creacion'])
            asignados_por_profesional += 1
            print(f"  OK {paciente.nombre_completo} -> {est.nombre} (por profesional)")
            continue

    sin_asignar += 1
    print(f"  SIN ASIGNAR {paciente.nombre_completo}")

print()
print(f"Resumen:")
print(f"  Asignados por turno:       {asignados_por_turno}")
print(f"  Asignados por profesional: {asignados_por_profesional}")
print(f"  Sin asignar:               {sin_asignar}")