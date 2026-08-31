from app import db
from app.models import Area, Servicio


def seed_areas():
    areas = [
        {
            'codigo': 'CONTROL',
            'nombre': 'Recepción Inicial / Control',
            'descripcion': 'Primer contacto del paciente. Identificación, afiliación y orientación inicial.',
            'genera_cola': False,
            'orden_visual': 1
        },
        {
            'codigo': 'TRABAJO_SOCIAL',
            'nombre': 'Trabajo Social',
            'descripcion': 'Afiliación, estudio socioeconómico y orientación para cirugías.',
            'genera_cola': True,
            'orden_visual': 2
        },
        {
            'codigo': 'CAJA',
            'nombre': 'Recepción / Caja',
            'descripcion': 'Cobro, confirmación de servicios y generación de turnos por área.',
            'genera_cola': True,
            'orden_visual': 3
        },
        {
            'codigo': 'CONSULTA',
            'nombre': 'Consulta Médica',
            'descripcion': 'Atención médica con doctor asignado.',
            'genera_cola': True,
            'orden_visual': 4
        },
        {
            'codigo': 'GABINETE',
            'nombre': 'Gabinete',
            'descripcion': 'Mediciones, cálculos y estudios oftalmológicos.',
            'genera_cola': True,
            'orden_visual': 5
        },
        {
            'codigo': 'FARMACIA',
            'nombre': 'Farmacia',
            'descripcion': 'Entrega de medicamentos y atención relacionada con recetas.',
            'genera_cola': True,
            'orden_visual': 6
        },
        {
            'codigo': 'OPTICA',
            'nombre': 'Asesoría Visual',
            'descripcion': 'Cotización, pedido, entrega y seguimiento de lentes.',
            'genera_cola': True,
            'orden_visual': 7
        },
        {
            'codigo': 'SALIDA',
            'nombre': 'Salida',
            'descripcion': 'Finalización de la atención del paciente.',
            'genera_cola': False,
            'orden_visual': 8
        }
    ]

    for datos in areas:
        area = Area.query.filter_by(codigo=datos['codigo']).first()

        if not area:
            area = Area(**datos)
            db.session.add(area)
        else:
            area.nombre = datos['nombre']
            area.descripcion = datos['descripcion']
            area.genera_cola = datos['genera_cola']
            area.orden_visual = datos['orden_visual']
            area.activo = True

    db.session.commit()


def seed_servicios():
    areas = {
        area.codigo: area
        for area in Area.query.all()
    }

    servicios = [
        # =========================
        # CONSULTA
        # =========================
        {
            'codigo': 'CONSULTA_GENERAL',
            'nombre': 'Consulta Oftalmológica',
            'area': 'CONSULTA',
            'requiere_pago': True
        },

        # =========================
        # GABINETE
        # =========================
        {
            'codigo': 'AGUDEZA_VISUAL',
            'nombre': 'Agudeza Visual',
            'area': 'GABINETE',
            'requiere_pago': True
        },
        {
            'codigo': 'PRESION_INTRAOCULAR',
            'nombre': 'Presión Intraocular',
            'area': 'GABINETE',
            'requiere_pago': True
        },
        {
            'codigo': 'QUERATOMETRIA',
            'nombre': 'Queratometría',
            'area': 'GABINETE',
            'requiere_pago': True
        },
        {
            'codigo': 'TONOMETRIA',
            'nombre': 'Tonometría',
            'area': 'GABINETE',
            'requiere_pago': True
        },
        {
            'codigo': 'REFRACCION',
            'nombre': 'Refracción',
            'area': 'GABINETE',
            'requiere_pago': True
        },
        {
            'codigo': 'CALCULO_LIO',
            'nombre': 'Cálculo de LIO',
            'area': 'GABINETE',
            'requiere_pago': True
        },

        # =========================
        # FARMACIA
        # =========================
        {
            'codigo': 'SURTIR_RECETA',
            'nombre': 'Surtir Receta',
            'area': 'FARMACIA',
            'requiere_pago': True
        },

        # =========================
        # ÓPTICA
        # =========================
        {
            'codigo': 'ASESORIA_VISUAL',
            'nombre': 'Asesoría Visual',
            'area': 'OPTICA',
            'requiere_pago': False
        },
        {
            'codigo': 'COTIZACION_LENTES',
            'nombre': 'Cotización de Lentes',
            'area': 'OPTICA',
            'requiere_pago': False
        },
        {
            'codigo': 'PEDIDO_LENTES',
            'nombre': 'Pedido de Lentes',
            'area': 'OPTICA',
            'requiere_pago': True
        },
        {
            'codigo': 'ENTREGA_LENTES',
            'nombre': 'Entrega de Lentes',
            'area': 'OPTICA',
            'requiere_pago': False
        },

        # =========================
        # TRABAJO SOCIAL
        # =========================
        {
            'codigo': 'AFILIACION',
            'nombre': 'Afiliación',
            'area': 'TRABAJO_SOCIAL',
            'requiere_pago': False
        },
        {
            'codigo': 'ESTUDIO_SOCIOECONOMICO',
            'nombre': 'Estudio Socioeconómico',
            'area': 'TRABAJO_SOCIAL',
            'requiere_pago': False
        },
        {
            'codigo': 'ORIENTACION_CIRUGIA',
            'nombre': 'Orientación / Programación de Cirugía',
            'area': 'TRABAJO_SOCIAL',
            'requiere_pago': False
        }
    ]

    for datos in servicios:
        area = areas.get(datos['area'])

        if not area:
            print(
                f"Área no encontrada para servicio "
                f"{datos['codigo']}: {datos['area']}"
            )
            continue

        servicio = Servicio.query.filter_by(
            codigo=datos['codigo']
        ).first()

        if not servicio:
            servicio = Servicio(
                codigo=datos['codigo'],
                nombre=datos['nombre'],
                area_id=area.id,
                requiere_pago=datos['requiere_pago'],
                activo=True
            )

            db.session.add(servicio)

        else:
            servicio.nombre = datos['nombre']
            servicio.area_id = area.id
            servicio.requiere_pago = datos['requiere_pago']
            servicio.activo = True

    db.session.commit()


def seed_all():
    print("Cargando catálogos iniciales...")

    seed_areas()
    print("Áreas cargadas")

    seed_servicios()
    print("Servicios cargados")

    print("Seed completado correctamente")