
from app import db
from app.models import (
    Atencion,
    AtencionServicio,
    SolicitudArea,
    TurnoArea,
)


ESTADOS_TURNO_ACTIVO = (
    "ESPERA",
    "LLAMADO",
    "EN_ATENCION",
    "PAUSADO",
)

ESTADOS_SERVICIO_TERMINADO = (
    "COMPLETADO",
    "CANCELADO",
)


def obtener_estado_card(atencion_id):
    """
    Consulta el estado de la atención viajera.

    No modifica registros.
    No crea turnos.
    No realiza commit.
    """

    atencion = db.session.get(Atencion, atencion_id)

    if atencion is None:
        return {
            "success": False,
            "error": "Atención no encontrada",
        }

    servicios = (
        AtencionServicio.query
        .filter_by(atencion_id=atencion.id)
        .order_by(
            AtencionServicio.orden.asc(),
            AtencionServicio.id.asc(),
        )
        .all()
    )

    turnos_activos = (
        TurnoArea.query
        .filter(
            TurnoArea.atencion_id == atencion.id,
            TurnoArea.estado.in_(ESTADOS_TURNO_ACTIVO),
        )
        .order_by(TurnoArea.id.desc())
        .all()
    )

    solicitudes = (
        SolicitudArea.query
        .filter_by(atencion_id=atencion.id)
        .order_by(
            SolicitudArea.fecha_solicitud.asc(),
            SolicitudArea.id.asc(),
        )
        .all()
    )

    servicios_data = []

    for item in servicios:
        servicios_data.append({
            "atencion_servicio_id": item.id,
            "servicio_id": item.servicio_id,
            "nombre": (
                item.servicio.nombre
                if item.servicio else None
            ),
            "estado": item.estado,
            "orden": item.orden,
            "origen": item.origen,
            "modalidad": item.modalidad,
            "requiere_pago": item.requiere_pago,
            "pagado": item.pagado,
            "solicitud_area_id": item.solicitud_area_id,
        })

    solicitudes_data = []

    for solicitud in solicitudes:
        solicitudes_data.append({
            "id": solicitud.id,
            "estado": solicitud.estado,
            "prioridad": solicitud.prioridad,
            "area_destino_id": solicitud.area_destino_id,
            "tipo_retorno": solicitud.tipo_retorno,
            "estado_retorno": solicitud.estado_retorno,
            "area_retorno_id": solicitud.area_retorno_id,
            "doctor_retorno_id": solicitud.doctor_retorno_id,
        })

    turno_actual = turnos_activos[0] if turnos_activos else None

    pendientes = [
        item for item in servicios_data
        if item["estado"] not in ESTADOS_SERVICIO_TERMINADO
    ]

    solicitudes_abiertas = [
        item for item in solicitudes_data
        if item["estado"] not in ("COMPLETADA", "CANCELADA")
    ]

    retornos_pendientes = [
        item for item in solicitudes_data
        if item["estado_retorno"] == "PENDIENTE"
    ]

    return {
        "success": True,
        "atencion": {
            "id": atencion.id,
            "folio": atencion.folio,
            "estado": atencion.estado,
            "sede_id": atencion.sede_id,
            "paciente_id": atencion.paciente_id,
            "nombre_paciente": atencion.nombre_paciente,
            "servicio_inicial_id": atencion.servicio_inicial_id,
        },
        "turno_actual": (
            {
                "id": turno_actual.id,
                "numero": turno_actual.numero_turno,
                "area_id": turno_actual.area_id,
                "area": (
                    turno_actual.area.nombre
                    if turno_actual.area else None
                ),
                "estado": turno_actual.estado,
                "servicio_id": turno_actual.servicio_id,
            }
            if turno_actual else None
        ),
        "total_turnos_activos": len(turnos_activos),
        "servicios": servicios_data,
        "total_servicios": len(servicios_data),
        "servicios_pendientes": pendientes,
        "solicitudes": solicitudes_data,
        "solicitudes_abiertas": solicitudes_abiertas,
        "retornos_pendientes": retornos_pendientes,
    }



def resolver_siguiente_paso_atencion(atencion_id):
    """
    Analiza la card viajera y propone el siguiente paso.

    SOLO LECTURA:
    - No mueve turnos.
    - No registra pagos.
    - No modifica servicios.
    - No realiza commit.
    """

    card = obtener_estado_card(atencion_id)

    if not card["success"]:
        return card

    atencion = card["atencion"]
    turno = card["turno_actual"]

    if atencion["estado"] == "FINALIZADA":
        return {
            "success": True,
            "accion": "ATENCION_FINALIZADA",
            "mensaje": "La atención ya terminó",
        }

    if card["total_turnos_activos"] > 1:
        return {
            "success": False,
            "accion": "REVISAR_INCONSISTENCIA",
            "error": "La atención tiene varios turnos activos",
        }

    if card["solicitudes_abiertas"]:
        return {
            "success": True,
            "accion": "REVISAR_SOLICITUDES",
            "mensaje": "Existen solicitudes de área abiertas",
            "solicitudes": card["solicitudes_abiertas"],
        }

    if card["retornos_pendientes"]:
        return {
            "success": True,
            "accion": "REVISAR_RETORNOS",
            "mensaje": "Existen retornos pendientes de decisión",
            "retornos": card["retornos_pendientes"],
        }

    pendientes = card["servicios_pendientes"]

    if not pendientes:
        return {
            "success": True,
            "accion": "REVISAR_FINALIZACION",
            "mensaje": "No hay servicios pendientes; verificar cierre",
        }

    servicio = pendientes[0]

    if (
        servicio["requiere_pago"]
        and not servicio["pagado"]
    ):
        return {
            "success": True,
            "accion": "PAGO_PENDIENTE",
            "atencion_id": atencion_id,
            "servicio_id": servicio["servicio_id"],
            "servicio": servicio["nombre"],
            "area_actual": turno["area"] if turno else None,
            "mensaje": "El servicio requiere confirmar su pago",
        }

    if not turno:
        return {
            "success": True,
            "accion": "REVISAR_TURNO",
            "servicio_id": servicio["servicio_id"],
            "mensaje": "No existe un turno activo",
        }

    return {
        "success": True,
        "accion": "RESOLVER_RECORRIDO",
        "atencion_id": atencion_id,
        "servicio_id": servicio["servicio_id"],
        "servicio": servicio["nombre"],
        "area_actual_id": turno["area_id"],
        "mensaje": "Servicio listo para consultar su recorrido",
    }




def diagnosticar_recorrido_atencion(atencion_id):
    """
    Diagnostica el siguiente paso utilizando el recorrido
    y la versión asignados al servicio de la atención.

    SOLO LECTURA:
    - No mueve turnos.
    - No modifica servicios.
    - No confirma pagos.
    - No realiza commit.
    """

    from app.models import Area, SedeArea

    # =================================================
    # 1. RESOLVER BLOQUEOS OPERATIVOS
    # =================================================

    decision = resolver_siguiente_paso_atencion(
        atencion_id
    )

    if not decision.get("success"):
        return decision

    resultado = {
        "success": True,
        "atencion_id": atencion_id,
        "accion": decision["accion"],
        "decision": decision,
        "recorrido": None,
        "puede_avanzar": False,
        "listo_para_evaluar_movimiento": False
    }

    # Los pagos, solicitudes y retornos tienen prioridad.
    if decision["accion"] != "RESOLVER_RECORRIDO":
        return resultado

    # =================================================
    # 2. CONSULTAR LA CARD VIAJERA
    # =================================================

    card = obtener_estado_card(atencion_id)

    if not card.get("success"):
        return card

    pendientes = card["servicios_pendientes"]

    if not pendientes:
        resultado["accion"] = "SIN_SERVICIOS_PENDIENTES"
        return resultado

    # Es el mismo servicio seleccionado por el motor.
    servicio = pendientes[0]

    atencion_servicio_id = servicio[
        "atencion_servicio_id"
    ]

    # =================================================
    # 3. VALIDAR RECORRIDO Y PASO ASIGNADOS
    # =================================================

    verificacion = verificar_paso_recorrido_atencion(
        atencion_servicio_id
    )

    if not verificacion.get("success"):
        resultado["accion"] = verificacion["accion"]
        resultado["mensaje"] = (
            "El servicio no tiene un recorrido o "
            "paso válido asignado."
        )
        resultado["verificacion"] = verificacion
        return resultado

    # Las versiones archivadas siguen siendo válidas.
    if verificacion["estado_publicacion"] not in (
        "PUBLICADO",
        "ARCHIVADO"
    ):
        resultado["accion"] = "RECORRIDO_NO_PUBLICADO"
        resultado["mensaje"] = (
            "La versión asignada no está publicada "
            "ni archivada."
        )
        return resultado

    # =================================================
    # 4. IDENTIFICAR EL ÁREA DEL PASO
    # =================================================

    area_id = verificacion["area_id"]

    area = db.session.get(
        Area,
        area_id
    )

    if area is None or not area.activo:
        resultado["accion"] = "AREA_NO_DISPONIBLE"
        resultado["mensaje"] = (
            "El área del paso no existe o está inactiva."
        )
        return resultado

    sede_id = card["atencion"]["sede_id"]

    sede_area = (
        SedeArea.query
        .filter_by(
            sede_id=sede_id,
            area_id=area_id,
            activo=True
        )
        .first()
    )

    if sede_area is None:
        resultado["accion"] = "AREA_NO_HABILITADA"
        resultado["mensaje"] = (
            "El área del recorrido no está "
            "habilitada en esta sede."
        )
        return resultado

    # =================================================
    # 5. PREPARAR INFORMACIÓN DEL RECORRIDO
    # =================================================

    resultado["recorrido"] = {
        "recorrido_id": verificacion["recorrido_id"],
        "version": verificacion["version"],
        "estado_publicacion": verificacion[
            "estado_publicacion"
        ],
        "paso_actual_id": verificacion[
            "paso_actual_id"
        ],
        "orden": verificacion["orden"],
        "area_id": area.id,
        "area_nombre": area.nombre,
        "atencion_servicio_id": atencion_servicio_id
    }

    # =================================================
    # 6. COMPARAR CON EL TURNO ACTUAL
    # =================================================

    turno = card["turno_actual"]

    if turno is None:
        resultado["accion"] = "REVISAR_TURNO"
        resultado["mensaje"] = (
            "La atención no tiene un turno activo."
        )
        return resultado

    if turno["estado"] == "PAUSADO":
        resultado["accion"] = "TURNO_PAUSADO"
        resultado["mensaje"] = (
            "El turno debe reanudarse antes de "
            "evaluar cualquier movimiento."
        )
        return resultado

    if turno["area_id"] == area.id:
        resultado["accion"] = "PASO_EN_AREA_ACTUAL"
        resultado["mensaje"] = (
            "El paciente ya se encuentra en el "
            "área correspondiente al paso."
        )
        return resultado

    # =================================================
    # 7. DIAGNÓSTICO FAVORABLE
    # =================================================

    resultado["accion"] = "PASO_DISPONIBLE"

    resultado["mensaje"] = (
        f"El siguiente paso corresponde al área "
        f"{area.nombre}. "
        "Falta validar y autorizar el movimiento."
    )

    resultado["listo_para_evaluar_movimiento"] = True

    # IMPORTANTE:
    # No equivale a autorización para mover pacientes.
    # El ejecutor y sus controles aún no están integrados.
    resultado["puede_avanzar"] = False

    return resultado




def verificar_paso_recorrido_atencion(atencion_servicio_id):
    """
    Comprueba que el paso actual pertenece al
    recorrido asignado a un servicio.

    Solo lectura:
    - No mueve turnos.
    - No modifica pagos.
    - No realiza commit.
    """

    from app import db
    from app.models import (
        AtencionServicio,
        RecorridoServicio,
        RecorridoPaso
    )

    servicio = db.session.get(
        AtencionServicio,
        atencion_servicio_id
    )

    if servicio is None:
        return {
            "success": False,
            "accion": "SERVICIO_NO_ENCONTRADO"
        }

    if servicio.recorrido_id is None:
        return {
            "success": False,
            "accion": "SIN_RECORRIDO"
        }

    if servicio.paso_actual_id is None:
        return {
            "success": False,
            "accion": "SIN_PASO_ACTUAL"
        }

    recorrido = db.session.get(
        RecorridoServicio,
        servicio.recorrido_id
    )

    if recorrido is None:
        return {
            "success": False,
            "accion": "RECORRIDO_NO_ENCONTRADO"
        }

    if (
        recorrido.sede_id != servicio.atencion.sede_id
        or recorrido.servicio_id != servicio.servicio_id
    ):
        return {
            "success": False,
            "accion": "RECORRIDO_INCOMPATIBLE"
        }

    paso = (
        RecorridoPaso.query
        .filter_by(
            id=servicio.paso_actual_id,
            recorrido_id=recorrido.id
        )
        .first()
    )

    if paso is None:
        return {
            "success": False,
            "accion": "PASO_INCOMPATIBLE"
        }

    return {
        "success": True,
        "accion": "PASO_VALIDO",
        "atencion_id": servicio.atencion_id,
        "atencion_servicio_id": servicio.id,
        "recorrido_id": recorrido.id,
        "version": recorrido.version,
        "estado_publicacion": recorrido.estado_publicacion,
        "paso_actual_id": paso.id,
        "orden": paso.orden,
        "area_id": paso.area_id
    }

