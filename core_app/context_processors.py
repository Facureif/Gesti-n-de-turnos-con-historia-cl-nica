# core_app/context_processors.py
from .models import ClienteSaaS

def cliente_global(request):
    """
    Obtiene el cliente activo para mostrarlo en TODAS las páginas.
    """
    cliente = None
    
    # 1. Intentar obtener el cliente por slug de la URL (si es multi-tenant)
    cliente_slug = request.resolver_match.kwargs.get('cliente_slug') if request.resolver_match else None
    if cliente_slug:
        cliente = ClienteSaaS.objects.filter(slug=cliente_slug).first()
    
    # 2. Si no hay slug (por ejemplo en el login o el panel), cargar el primero o el configurado
    if not cliente:
        # Si tienes una ConfiguracionSistema, usa eso. Si no, toma el primer cliente activo.
        cliente = ClienteSaaS.objects.filter(activo=True).first()
        
    return {'cliente': cliente}