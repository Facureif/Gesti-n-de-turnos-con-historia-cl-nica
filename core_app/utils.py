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