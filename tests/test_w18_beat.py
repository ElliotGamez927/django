"""Suite de pruebas W18 — Celery Beat y tarea de reporte diario.

Verifica la configuración del schedule, la ejecución de la tarea
y el envío del correo de reporte.
NO se conecta a SendGrid ni a Redis (laboratorio sin Docker).

Ejecutar con:
    python manage.py test tests.test_w18_beat --verbosity=2

Resultado esperado:
    Ran 13 tests in X.XXXs
    OK
"""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from celery.schedules import crontab

from django.conf import settings
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from clientes.models      import Cliente
from configuracion.models import ConfiguracionERP
from productos.models     import Categoria, Producto
from ventas.models        import DetalleVenta, Pedido, Venta
from ventas.tasks         import reporte_ventas_diario

EMAIL_SETTINGS = {
    'EMAIL_BACKEND':                'django.core.mail.backends.locmem.EmailBackend',
    'CELERY_TASK_ALWAYS_EAGER':     True,
    'CELERY_TASK_EAGER_PROPAGATES': True,
    'ADMINS':                       [('Admin Test', 'admin@test.com')],
    'DEFAULT_FROM_EMAIL':           'test@erp.com',
    'SITE_URL':                     'https://erp-test.onrender.com',
}


def _entrada_schedule(nombre_tarea: str) -> dict:
    """Devuelve la entrada de CELERY_BEAT_SCHEDULE de una tarea."""
    for config in settings.CELERY_BEAT_SCHEDULE.values():
        if config['task'] == nombre_tarea:
            return config
    raise AssertionError(
        f'{nombre_tarea} no está en CELERY_BEAT_SCHEDULE'
    )


class BeatScheduleConfigTest(TestCase):
    """Verifica la configuración de CELERY_BEAT_SCHEDULE."""

    def test_beat_schedule_tiene_verificar_stock(self):
        """El schedule debe incluir verificar_stock_bajo."""
        tareas = [v['task'] for v in settings.CELERY_BEAT_SCHEDULE.values()]
        self.assertIn('ventas.verificar_stock_bajo', tareas)

    def test_beat_schedule_tiene_reporte_diario(self):
        """El schedule debe incluir reporte_ventas_diario."""
        tareas = [v['task'] for v in settings.CELERY_BEAT_SCHEDULE.values()]
        self.assertIn('ventas.reporte_ventas_diario', tareas)

    def test_reporte_usa_crontab(self):
        """El reporte diario debe usar crontab (no timedelta)."""
        config = _entrada_schedule('ventas.reporte_ventas_diario')
        self.assertIsInstance(config['schedule'], crontab)

    def test_reporte_corre_a_las_8_am(self):
        """El crontab del reporte debe ser exactamente 8:00."""
        schedule = _entrada_schedule('ventas.reporte_ventas_diario')['schedule']
        self.assertEqual(schedule.hour,   {8})
        self.assertEqual(schedule.minute, {0})

    def test_verificar_stock_usa_timedelta(self):
        """verificar_stock_bajo debe usar timedelta (intervalo)."""
        config = _entrada_schedule('ventas.verificar_stock_bajo')
        self.assertIsInstance(config['schedule'], timedelta)

    def test_tareas_programadas_usan_cola_erp_django(self):
        """El worker solo escucha la cola 'erp_django'."""
        for nombre, config in settings.CELERY_BEAT_SCHEDULE.items():
            self.assertEqual(
                config['options']['queue'], 'erp_django',
                f'{nombre} debe usar la cola erp_django',
            )

    def test_celery_usa_zona_horaria_de_mexico(self):
        """Beat interpreta las horas con CELERY_TIMEZONE (W16)."""
        self.assertEqual(settings.CELERY_TIMEZONE, 'America/Mexico_City')


@override_settings(**EMAIL_SETTINGS)
class ReporteVentasTest(TestCase):
    """Tests de la tarea reporte_ventas_diario."""

    def setUp(self):
        ConfiguracionERP.get_instance()
        cat       = Categoria.objects.create(nombre='Cat Rep')
        self.prod = Producto.objects.create(
            nombre='Producto Reporte', precio=Decimal('500.00'),
            stock=10, categoria=cat,
        )
        cli = Cliente.objects.create(
            nombre='Cliente Rep', correo='rep@test.com'
        )
        # Una venta de HOY (alimenta el "Top productos")
        venta = Venta.objects.create(cliente=cli)
        DetalleVenta.objects.create(
            venta=venta, producto=self.prod,
            cantidad=3, precio_unitario=Decimal('500.00'),
        )
        # Un pedido pagado de HOY (alimenta los KPIs)
        Pedido.objects.create(
            numero_pedido  = 'PED-REP-001',
            cliente        = cli,
            estado         = 'pagado',
            total_pagado   = Decimal('1500.00'),
            items_snapshot = [],
        )

    def test_reporte_envia_correo_al_admin(self):
        """La tarea debe enviar un correo al administrador."""
        reporte_ventas_diario.delay()
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('admin@test.com', mail.outbox[0].to)

    def test_reporte_asunto_contiene_fecha(self):
        """El asunto debe contener la fecha del reporte."""
        reporte_ventas_diario.delay()
        fecha_str = timezone.localdate().strftime('%d/%m/%Y')
        self.assertIn(fecha_str, mail.outbox[0].subject)

    def test_reporte_sin_ventas_hoy_envia_correo(self):
        """Aunque no haya ventas, el reporte debe enviarse (con 0 pedidos)."""
        Pedido.objects.all().delete()
        DetalleVenta.objects.all().delete()

        reporte_ventas_diario.delay()

        self.assertEqual(len(mail.outbox), 1)
        cuerpo = mail.outbox[0].body
        self.assertIn('Pedidos pagados hoy: 0', cuerpo)
        self.assertIn('Sin ventas registradas hoy', cuerpo)

    def test_reporte_devuelve_dict_con_totales(self):
        """La tarea devuelve totales correctos y serializables."""
        resultado = reporte_ventas_diario.delay().get()
        self.assertEqual(resultado['total_pedidos'], 1)
        self.assertEqual(resultado['top_productos'][0]['nombre'],
                         'Producto Reporte')
        self.assertEqual(resultado['top_productos'][0]['unidades'], 3)
        self.assertTrue(resultado['correo_enviado'])
        # El total facturado viaja como texto (JSON-safe)
        self.assertIsInstance(resultado['total_facturado'], str)

    def test_reporte_usa_site_url_en_el_enlace(self):
        """El enlace al admin sale de SITE_URL, no de una URL fija."""
        reporte_ventas_diario.delay()
        self.assertIn(
            'https://erp-test.onrender.com/admin/',
            mail.outbox[0].body,
        )

    def test_reporte_tolera_fallo_de_envio(self):
        """Si SendGrid falla, la tarea no revienta y lo informa."""
        with patch(
            'ventas.tasks.EmailMultiAlternatives.send',
            side_effect=Exception('SendGrid caído'),
        ):
            resultado = reporte_ventas_diario.delay().get()
        self.assertFalse(resultado['correo_enviado'])