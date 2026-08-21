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