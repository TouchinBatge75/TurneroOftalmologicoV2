"""Turnero V2 · Indicadores de Recepción/Caja por sede.

Los indicadores se calculan sobre las atenciones INGRESADAS en el periodo
seleccionado, incluso si sus turnos se atendieron después. Las marcas de tiempo
DateTime del proyecto se guardan como UTC sin tzinfo (datetime.utcnow).

Este módulo NO modifica pagos, turnos ni recorridos.
"""

import csv
from datetime import date, datetime, time, timedelta, timezone
from io import StringIO
from zoneinfo import ZoneInfo

from flask import Blueprint, Response, current_app, jsonify, request
from flask_login import current_user
from sqlalchemy import and_, case, func
from sqlalchemy.exc import SQLAlchemyError

from app import db
from app.models import Area, Atencion, Sede, TurnoArea
from app.permisos import verificar_area, verificar_permiso


bp_recepcion_kpis = Blueprint(
    'recepcion_kpis', __name__, url_prefix='/api/recepcion'
)

ZONA_OPERATIVA = ZoneInfo('America/Mexico_City')
MAX_DIAS = 366


@bp_recepcion_kpis.before_request
def proteger_consultas_recepcion():
    """Solo operadores autorizados a Recepción/Caja en su propia sede."""
    if not current_user.is_authenticated:
        return jsonify(success=False, error='Debe iniciar sesión'), 401

    if not current_user.is_active or not current_user.activo:
        return jsonify(success=False, error='Operador inactivo'), 403

    sede_id = current_user.sede_id
    if (
        sede_id is None
        or not verificar_permiso('recepcion_ver')
        or not verificar_area(current_user, sede_id, 'CAJA')
    ):
        return jsonify(success=False, error='Acceso no autorizado a Recepción/Caja'), 403

    return None


def _rango_fechas():
    """Devuelve fechas y límites UTC (naive) para filtrar correctamente por día local."""
    hoy = datetime.now(ZONA_OPERATIVA).date()
    texto_desde = request.args.get('desde')
    texto_hasta = request.args.get('hasta')

    if texto_desde is None and texto_hasta is None:
        desde = hasta = hoy
    elif not texto_desde or not texto_hasta:
        raise ValueError('Envía tanto desde como hasta en formato AAAA-MM-DD.')
    else:
        try:
            desde = date.fromisoformat(texto_desde)
            hasta = date.fromisoformat(texto_hasta)
        except ValueError as error:
            raise ValueError('Fechas inválidas. Utiliza AAAA-MM-DD.') from error
        if desde.isoformat() != texto_desde or hasta.isoformat() != texto_hasta:
            raise ValueError('Fechas inválidas. Utiliza AAAA-MM-DD.')

    if desde > hasta:
        raise ValueError('La fecha inicial no puede ser posterior a la final.')
    if (hasta - desde).days >= MAX_DIAS:
        raise ValueError(f'Selecciona como máximo {MAX_DIAS} días.')
    if hasta > hoy:
        raise ValueError('La fecha final no puede estar en el futuro.')

    inicio_local = datetime.combine(desde, time.min, tzinfo=ZONA_OPERATIVA)
    fin_local = datetime.combine(hasta + timedelta(days=1), time.min, tzinfo=ZONA_OPERATIVA)
    inicio_utc = inicio_local.astimezone(timezone.utc).replace(tzinfo=None)
    fin_utc = fin_local.astimezone(timezone.utc).replace(tzinfo=None)
    return desde, hasta, inicio_utc, fin_utc


def _entero(valor):
    return int(valor or 0)


def _redondear(valor):
    return round(float(valor), 1) if valor is not None else None


def _calcular_indicadores():
    desde, hasta, inicio_utc, fin_utc = _rango_fechas()
    sede_id = current_user.sede_id  # NUNCA aceptar sede_id desde el navegador.

    base_atenciones = [
        Atencion.sede_id == sede_id,
        Atencion.fecha_hora_llegada >= inicio_utc,
        Atencion.fecha_hora_llegada < fin_utc,
    ]

    # Conteos por atención, no por servicio ni por turno.
    totales = (
        db.session.query(
            func.count(Atencion.id).label('ingresos'),
            func.sum(case((Atencion.estado == 'FINALIZADA', 1), else_=0)).label('finalizadas'),
            func.sum(case((Atencion.estado == 'ACTIVA', 1), else_=0)).label('activas'),
        )
        .filter(*base_atenciones)
        .one()
    )

    # Los registros del proyecto son UTC naive. Convertir a horario local para
    # las barras diarias sin alterar los timestamps de la base de datos.
    dia_local = func.date(
        func.timezone('America/Mexico_City',
                      func.timezone('UTC', Atencion.fecha_hora_llegada))
    )
    registros_diarios = (
        db.session.query(dia_local.label('dia'), func.count(Atencion.id).label('total'))
        .filter(*base_atenciones)
        .group_by(dia_local)
        .order_by(dia_local)
        .all()
    )
    conteo_diario = {fila.dia.isoformat(): _entero(fila.total) for fila in registros_diarios}
    tendencia = []
    fecha = desde
    while fecha <= hasta:
        tendencia.append({'fecha': fecha.isoformat(), 'ingresos': conteo_diario.get(fecha.isoformat(), 0)})
        fecha += timedelta(days=1)

    # Tiempo de espera observado: entrada a la cola -> llamado registrado (si existe).
    # Tiempo de atención: inicio -> finalización (si ambos existen).
    # Un evento sin ambas fechas NO participa del promedio.
    espera_valida = and_(
        TurnoArea.fecha_llamado.isnot(None),
        TurnoArea.fecha_entrada_cola.isnot(None),
        TurnoArea.fecha_llamado >= TurnoArea.fecha_entrada_cola,
    )
    atencion_valida = and_(
        TurnoArea.fecha_inicio.isnot(None),
        TurnoArea.fecha_fin.isnot(None),
        TurnoArea.fecha_fin >= TurnoArea.fecha_inicio,
    )
    minutos_espera = func.extract('epoch', TurnoArea.fecha_llamado - TurnoArea.fecha_entrada_cola) / 60.0
    minutos_atencion = func.extract('epoch', TurnoArea.fecha_fin - TurnoArea.fecha_inicio) / 60.0

    filas_areas = (
        db.session.query(
            Area.id.label('area_id'),
            Area.codigo.label('codigo'),
            Area.nombre.label('nombre'),
            func.count(TurnoArea.id).label('total_turnos'),
            func.sum(case((TurnoArea.estado == 'ESPERA', 1), else_=0)).label('en_espera'),
            func.sum(case((TurnoArea.estado == 'LLAMADO', 1), else_=0)).label('llamados'),
            func.sum(case((TurnoArea.estado == 'EN_ATENCION', 1), else_=0)).label('en_atencion'),
            func.sum(case((TurnoArea.estado == 'PAUSADO', 1), else_=0)).label('pausados'),
            func.sum(case((TurnoArea.estado == 'FINALIZADO', 1), else_=0)).label('finalizados'),
            func.sum(func.coalesce(TurnoArea.veces_omitido, 0)).label('omisiones'),
            func.count(case((espera_valida, TurnoArea.id))).label('muestras_espera'),
            func.avg(case((espera_valida, minutos_espera))).label('promedio_espera'),
            func.count(case((atencion_valida, TurnoArea.id))).label('muestras_atencion'),
            func.avg(case((atencion_valida, minutos_atencion))).label('promedio_atencion'),
        )
        .join(TurnoArea, TurnoArea.area_id == Area.id)
        .join(Atencion, Atencion.id == TurnoArea.atencion_id)
        .filter(*base_atenciones)
        .group_by(Area.id, Area.codigo, Area.nombre)
        .order_by(Area.nombre)
        .all()
    )

    areas = []
    sum_espera = 0.0
    sum_atencion = 0.0
    muestras_espera = 0
    muestras_atencion = 0
    for fila in filas_areas:
        n_espera = _entero(fila.muestras_espera)
        n_atencion = _entero(fila.muestras_atencion)
        if n_espera:
            sum_espera += float(fila.promedio_espera) * n_espera
        if n_atencion:
            sum_atencion += float(fila.promedio_atencion) * n_atencion
        muestras_espera += n_espera
        muestras_atencion += n_atencion

        areas.append({
            'area_id': fila.area_id,
            'codigo': fila.codigo,
            'nombre': fila.nombre,
            'total_turnos': _entero(fila.total_turnos),
            'en_espera': _entero(fila.en_espera),
            'llamados': _entero(fila.llamados),
            'en_atencion': _entero(fila.en_atencion),
            'pausados': _entero(fila.pausados),
            'finalizados': _entero(fila.finalizados),
            'omisiones': _entero(fila.omisiones),
            'muestras_espera': n_espera,
            'promedio_espera_min': _redondear(fila.promedio_espera),
            'muestras_atencion': n_atencion,
            'promedio_atencion_min': _redondear(fila.promedio_atencion),
        })

    sede = db.session.get(Sede, sede_id)
    ingresos = _entero(totales.ingresos)
    finalizadas = _entero(totales.finalizadas)
    return {
        'success': True,
        'sede': {'id': sede_id, 'nombre': sede.nombre if sede else 'Sede'},
        'periodo': {'desde': desde.isoformat(), 'hasta': hasta.isoformat(),
                    'zona_horaria': 'America/Mexico_City',
                    'criterio': 'atenciones ingresadas en el periodo'},
        'metricas': {
            'ingresos': ingresos,
            'finalizadas': finalizadas,
            'activas': _entero(totales.activas),
            'tasa_finalizacion_pct': round(finalizadas * 100.0 / ingresos, 1) if ingresos else None,
            'turnos_generados': sum(a['total_turnos'] for a in areas),
            'en_espera': sum(a['en_espera'] for a in areas),
            'llamados': sum(a['llamados'] for a in areas),
            'en_atencion': sum(a['en_atencion'] for a in areas),
            'pausados': sum(a['pausados'] for a in areas),
            'omisiones': sum(a['omisiones'] for a in areas),
            'promedio_espera_min': round(sum_espera / muestras_espera, 1) if muestras_espera else None,
            'promedio_atencion_min': round(sum_atencion / muestras_atencion, 1) if muestras_atencion else None,
            'muestras_espera': muestras_espera,
            'muestras_atencion': muestras_atencion,
        },
        'tendencia_diaria': tendencia,
        'areas': areas,
    }


@bp_recepcion_kpis.route('/indicadores', methods=['GET'])
def indicadores_recepcion():
    try:
        return jsonify(_calcular_indicadores())
    except ValueError as error:
        return jsonify(success=False, error=str(error)), 400
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception('Error al consultar indicadores de Recepción')
        return jsonify(success=False, error='No fue posible consultar los indicadores'), 500


def _celda_csv(valor):
    """Evita fórmulas de hojas de cálculo en textos editables del catálogo."""
    if valor is None:
        return ''
    if isinstance(valor, str) and valor.lstrip().startswith(('=', '+', '-', '@')):
        return "'" + valor
    return valor


@bp_recepcion_kpis.route('/reporte.csv', methods=['GET'])
def descargar_reporte_recepcion():
    try:
        datos = _calcular_indicadores()
    except ValueError as error:
        return jsonify(success=False, error=str(error)), 400
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception('Error al generar reporte de Recepción')
        return jsonify(success=False, error='No fue posible generar el reporte'), 500

    salida = StringIO(newline='')
    escritor = csv.writer(salida)
    escritor.writerow([
        'Sede', 'Desde', 'Hasta', 'Área', 'Código', 'Turnos generados',
        'En espera', 'Llamados', 'En atención', 'Pausados', 'Finalizados',
        'Omisiones', 'Espera promedio (min)', 'Muestras espera',
        'Atención promedio (min)', 'Muestras atención',
    ])
    p = datos['periodo']
    for area in datos['areas']:
        escritor.writerow([
            _celda_csv(datos['sede']['nombre']), p['desde'], p['hasta'],
            _celda_csv(area['nombre']), _celda_csv(area['codigo']),
            area['total_turnos'], area['en_espera'], area['llamados'],
            area['en_atencion'], area['pausados'], area['finalizados'],
            area['omisiones'], area['promedio_espera_min'] if area['promedio_espera_min'] is not None else '',
            area['muestras_espera'], area['promedio_atencion_min'] if area['promedio_atencion_min'] is not None else '',
            area['muestras_atencion'],
        ])

    nombre_archivo = f"turnero_recepcion_{p['desde']}_{p['hasta']}.csv"
    # Excel suele reconocer UTF-8 más fácilmente con BOM.
    contenido = '\ufeff' + salida.getvalue()
    return Response(
        contenido,
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename="{nombre_archivo}"',
                 'Cache-Control': 'no-store'},
    )
