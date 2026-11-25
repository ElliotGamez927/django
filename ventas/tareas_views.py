# ventas/tareas_views.py
"""Ejecución manual de tareas programadas (solo personal del admin)."""
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse

from .tasks import reporte_ventas_diario, verificar_stock_bajo


@staff_member_required
def ejecutar_stock_bajo(request):
    """Revisa el stock y envía la alerta al admin. ?umbral=5 (opcional)."""
    try:
        umbral = int(request.GET.get('umbral', 5))
    except ValueError:
        umbral = 5
    resultado = verificar_stock_bajo(umbral)
    return JsonResponse(resultado, json_dumps_params={'ensure_ascii': False})


@staff_member_required
def ejecutar_reporte_diario(request):
    """Genera y envía el reporte de ventas del día al admin."""
    resultado = reporte_ventas_diario()
    return JsonResponse(resultado, json_dumps_params={'ensure_ascii': False})