from core_app.models import ClienteSaaS


def get_establecimiento_activo(request, profesional):
    """
    Devuelve el establecimiento correspondiente al cliente activo en la sesión,
    siempre que el profesional trabaje allí.
    Si no hay cliente activo, devuelve None.
    """
    slug = request.session.get('cliente_slug')
    if not slug:
        return None

    try:
        cliente = ClienteSaaS.objects.get(slug=slug, activo=True)
    except ClienteSaaS.DoesNotExist:
        return None

    if cliente.establecimiento in profesional.establecimientos.all():
        return cliente.establecimiento

    return None


# En core_app/utils.py o turnos_profesionales/utils.py
from datetime import date
from pacientes.models import PacienteObraSocial  

def obtener_obras_sociales_para_mostrar(paciente, profesional=None):
    """
    Devuelve una lista de diccionarios con la info de las OS para mostrar.
    Si existe una OS con sesiones restantes > 0 y no vencida, devuelve solo esa.
    Caso contrario, devuelve todas las activas.
    """
    # Filtrar por paciente, y opcionalmente por profesional
    qs = PacienteObraSocial.objects.filter(paciente=paciente, activa=True)
    if profesional:
        qs = qs.filter(profesional=profesional)

    hoy = date.today()

    # Buscar OS con sesiones disponibles y no vencidas
    os_con_sesiones = []
    for os in qs:
        sesiones = os.sesiones_restantes  # asumo que existe este campo
        vencida = False
        if os.fecha_vencimiento and os.fecha_vencimiento < hoy:
            vencida = True
        if sesiones and sesiones > 0 and not vencida:
            os_con_sesiones.append(os)

    if os_con_sesiones:
        # Podés ordenar por fecha de vencimiento o prioridad
        # Por ahora tomamos la primera
        os_elegida = os_con_sesiones[0]
        return [{
            'nombre': os_elegida.obra_social.nombre,
            'numero_afiliado': os_elegida.numero_afiliado,
            'sesiones_restantes': os_elegida.sesiones_restantes,
            'es_recomendada': True,
        }]
    else:
        # No hay con sesiones: devolver todas las activas
        resultado = []
        for os in qs:
            resultado.append({
                'nombre': os.obra_social.nombre,
                'numero_afiliado': os.numero_afiliado,
                'sesiones_restantes': os.sesiones_restantes,
                'es_recomendada': False,
            })
        return resultado