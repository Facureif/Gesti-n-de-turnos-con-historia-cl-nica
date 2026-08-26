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
    """
    Devuelve True si el profesional puede ver al paciente en ese establecimiento.
    Condiciones:
    - Tiene turnos con el paciente en ese establecimiento.
    - El paciente le fue compartido (cualquier permiso).
    - Es el creador (si usás ese campo).
    """
    # Turnos propios en el establecimiento
    tiene_turnos = TurnoProfesional.objects.filter(
        profesional=profesional,
        paciente=paciente,
        establecimiento=establecimiento
    ).exists()
    if tiene_turnos:
        return True

    # Compartido explícitamente
    compartido = PacienteCompartido.objects.filter(
        paciente=paciente,
        profesional_destino=profesional
    ).exists()
    if compartido:
        return True

    # Si tenés campo creado_por, podés agregarlo
    # if paciente.creado_por == profesional:
    #     return True

    return False

def puede_editar(profesional, paciente, establecimiento):
    """
    Devuelve True si el profesional puede editar la ficha, cargar evoluciones, etc.
    Condiciones:
    - Es el dueño (tiene turnos o es creador) → se asume que puede editar.
    - Le fue compartido con puede_editar=True.
    """
    # Dueño por turnos
    tiene_turnos = TurnoProfesional.objects.filter(
        profesional=profesional,
        paciente=paciente,
        establecimiento=establecimiento
    ).exists()
    if tiene_turnos:
        return True

    # Compartido con permiso de edición
    compartido_editable = PacienteCompartido.objects.filter(
        paciente=paciente,
        profesional_destino=profesional,
        puede_editar=True
    ).exists()
    return compartido_editable    