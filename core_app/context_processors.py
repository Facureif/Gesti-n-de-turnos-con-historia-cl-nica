from .models import ClienteSaaS

def cliente_global(request):
    cliente = None

    # 1. Intentar obtener cliente desde el slug de la URL (si existe)
    cliente_slug = request.resolver_match.kwargs.get('cliente_slug') if request.resolver_match else None
    if cliente_slug:
        cliente = ClienteSaaS.objects.filter(slug=cliente_slug, activo=True).first()
        if cliente:
            # Guardar en sesión para mantener el contexto en páginas internas
            request.session['cliente_slug'] = cliente_slug
    else:
        # 2. Si no hay slug en la URL, buscar en la sesión (último consultorio visitado)
        slug_session = request.session.get('cliente_slug')
        if slug_session:
            cliente = ClienteSaaS.objects.filter(slug=slug_session, activo=True).first()

    # 3. Si no se encontró cliente, devolvemos None
    return {'cliente': cliente}