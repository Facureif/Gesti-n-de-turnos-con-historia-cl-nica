# pacientes/utils.py
from turnos_profesionales.models import TurnoProfesional

def paciente_tiene_relacion_con_establecimiento(paciente, establecimiento):
    """
    Verifica si el paciente tiene al menos un turno en el establecimiento dado.
    """
    if not establecimiento:
        return False
    return TurnoProfesional.objects.filter(
        paciente=paciente,
        establecimiento=establecimiento
    ).exists()


from django.db.models import Q
from turnos_profesionales.models import TurnoProfesional
from .models import PacienteCompartido

def tiene_acceso(profesional, paciente, establecimiento):
    if not establecimiento:
        return False

    # Turnos propios en el establecimiento
    if TurnoProfesional.objects.filter(
        profesional=profesional,
        paciente=paciente,
        establecimiento=establecimiento
    ).exists():
        return True

    # Compartido explícitamente
    if PacienteCompartido.objects.filter(
        paciente=paciente,
        profesional_destino=profesional
    ).exists():
        return True

    # Creado por el profesional
    if paciente.creado_por == profesional:
        return True

    # ✅ Paciente creado en el mismo establecimiento (visible para todo el consultorio)
    if paciente.establecimiento_creacion == establecimiento:
        return True

    return False


def puede_editar(profesional, paciente, establecimiento):
    if not establecimiento:
        return False

    # Dueño por turnos
    if TurnoProfesional.objects.filter(
        profesional=profesional,
        paciente=paciente,
        establecimiento=establecimiento
    ).exists():
        return True

    # Compartido con permiso de edición
    if PacienteCompartido.objects.filter(
        paciente=paciente,
        profesional_destino=profesional,
        puede_editar=True
    ).exists():
        return True

    # Creado por el profesional
    if paciente.creado_por == profesional:
        return True

    # ✅ Paciente del mismo establecimiento (todos pueden editarlo)
    if paciente.establecimiento_creacion == establecimiento:
        return True

    return False