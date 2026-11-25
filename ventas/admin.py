# ventas/admin.py
"""Configuración del panel admin para la app ventas."""
from django.contrib import admin

from .models import DetalleVenta, Pedido, Venta


class DetalleVentaInline(admin.TabularInline):
    """Líneas de detalle dentro del admin de Venta."""

    model       = DetalleVenta
    extra       = 1            # mostrar 1 fila vacía para agregar
    fields      = ['producto', 'cantidad', 'precio_unitario']
    readonly_fields = []


@admin.register(Venta)
class VentaAdmin(admin.ModelAdmin):
    """Admin de ventas con detalles inline y total calculado."""

    list_display    = ['pk', 'cliente', 'fecha', 'total_admin']
    search_fields   = ['cliente__nombre', 'cliente__correo']
    readonly_fields = ['fecha']
    inlines         = [DetalleVentaInline]
    date_hierarchy  = 'fecha'

    @admin.display(description='Total ($)')
    def total_admin(self, obj: Venta) -> str:
        """Muestra el total calculado de la venta en la lista."""
        return f"${obj.total:.2f}"


@admin.register(DetalleVenta)
class DetalleVentaAdmin(admin.ModelAdmin):
    """Admin de líneas de detalle (vista independiente)."""

    list_display  = ['pk', 'venta', 'producto', 'cantidad',
                     'precio_unitario', 'subtotal_admin']
    search_fields = ['producto__nombre', 'venta__pk']
    readonly_fields = ['precio_unitario']



    @admin.display(description='Subtotal ($)')
    def subtotal_admin(self, obj: DetalleVenta) -> str:
        return f"${obj.subtotal:.2f}"

@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    """Admin de pedidos de e-commerce."""

    list_display   = ['numero_pedido', 'cliente', 'estado',
                      'fecha_pedido', 'total_pagado']
    search_fields  = ['numero_pedido', 'cliente__nombre']
    list_filter    = ['estado']
    readonly_fields = ['fecha_pedido']

    actions = ['reenviar_correo_confirmacion']

    @admin.action(description='Reenviar correo de confirmación')
    def reenviar_correo_confirmacion(self, request, queryset):
        from ventas.tasks import enviar_confirmacion_pedido
        total = 0
        for pedido in queryset.filter(estado='pagado'):
            # correo_enviado=False para que la tarea no lo salte
            Pedido.objects.filter(pk=pedido.pk).update(correo_enviado=False)
            enviar_confirmacion_pedido.delay(pedido.pk)
            total += 1
        self.message_user(request, f'Reenvío solicitado para {total} pedido(s).')