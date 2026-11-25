# ventas/urls.py
"""URLs de la app ventas — W07."""
from django.urls import path
from . import views
from . import tareas_views, views

app_name = 'ventas'

urlpatterns = [
    path('',
         views.VentaListView.as_view(),
         name='lista'),
    path('<int:venta_id>/',
         views.VentaDetailView.as_view(),
         name='detalle'),
    path('nueva/',                  views.crear_venta,                 name='crear'),
    path('<int:venta_id>/eliminar/',views.VentaDeleteView.as_view(),   name='eliminar'),
    # ... tus otras rutas de ventas ...
    path('<int:venta_id>/pdf/', views.venta_pdf, name='pdf'),
    path('tareas/stock-bajo/',     tareas_views.ejecutar_stock_bajo,     name='tarea_stock'),
    path('tareas/reporte-diario/', tareas_views.ejecutar_reporte_diario, name='tarea_reporte'),
    # ... tus rutas de siempre, sin tocar ...
]