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


from .models import ClienteSaaS

def get_cliente_actual(request):
    slug = request.session.get('cliente_slug')
    if slug:
        return ClienteSaaS.objects.filter(slug=slug, activo=True).first()
    return None    

from django.db.models import Q
from establecimientos.models import Establecimiento
from agendas.models import Agenda


def resolver_establecimiento(request, profesional):
    """
    Resuelve el establecimiento a usar:
    1. GET/POST 'establecimiento' (si el profesional tiene acceso vía M2M o vía Agenda)
    2. sesión 'establecimiento_activo_id'
    3. get_establecimiento_activo (cliente_slug)
    4. Si tiene 1 solo, ese
    5. Primer consultorio con agenda activa
    """
    # 1. URL / POST
    est_id = request.GET.get('establecimiento') or request.POST.get('establecimiento')
    if est_id:
        est = Establecimiento.objects.filter(id=est_id).filter(
            Q(profesionales=profesional) |
            Q(agenda__profesional=profesional, agenda__activo=True)
        ).distinct().first()
        if est:
            request.session['establecimiento_activo_id'] = est.id
            return est

    # 2. Sesión propia
    est_sesion_id = request.session.get('establecimiento_activo_id')
    if est_sesion_id:
        est = Establecimiento.objects.filter(id=est_sesion_id).filter(
            Q(profesionales=profesional) |
            Q(agenda__profesional=profesional, agenda__activo=True)
        ).distinct().first()
        if est:
            return est

    # 3. Fallback: cliente SaaS
    est = get_establecimiento_activo(request, profesional)
    if est:
        return est

    # 4. Si tiene 1 solo
    if profesional.establecimientos.count() == 1:
        return profesional.establecimientos.first()

    # 5. Primer consultorio con agenda activa
    ag = Agenda.objects.filter(
        profesional=profesional, activo=True
    ).select_related('establecimiento').first()
    if ag:
        return ag.establecimiento

    return None

def get_consultorios_para_selector(request, profesional):
    """
    Devuelve [] si es cliente tipo consultorio (no mostrar selector),
    o la lista de consultorios si es independiente.
    """
    from core_app.models import ClienteSaaS

    cliente_slug = request.session.get('cliente_slug')
    if cliente_slug:
        cliente = ClienteSaaS.objects.filter(slug=cliente_slug, activo=True).first()
        if cliente and cliente.tipo == 'consultorio':
            return []

    return list(
        Establecimiento.objects.filter(
            Q(agenda__profesional=profesional, agenda__activo=True) |
            Q(profesionales=profesional)
        ).distinct().order_by('nombre')
    )


import logging
import threading

logger = logging.getLogger(__name__)


def safe_task(target, *args, **kwargs):
    """
    Ejecuta una función en un thread y loguea errores sin romper el request.
    Reemplaza el patrón:
        try:
            threading.Thread(target=..., args=...).start()
        except:
            pass
    """
    def wrapper():
        try:
            target(*args, **kwargs)
        except Exception as e:
            logger.exception(
                f"Error en tarea de background '{target.__name__}': {e}"
            )

    threading.Thread(target=wrapper, daemon=True).start()


def safe_call(target, *args, **kwargs):
    """
    Llama a una función y loguea errores sin propagarlos.
    Para tareas donde no querés que falle el flujo principal.
    """
    try:
        return target(*args, **kwargs)
    except Exception as e:
        logger.exception(f"Error en '{target.__name__}': {e}")
        return None