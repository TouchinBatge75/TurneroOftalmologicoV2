from app import db
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from app.models import AtencionServicio
from app.proteccion_recorridos import autorizar_publicacion_recorridos



from app.models import (
    RecorridoServicio,
    RecorridoPaso,
    ServicioSede,
    SedeArea
)


def obtener_recorrido_servicio(
    sede_id,
    servicio_id,
    solo_activo=True
):
    """
    Consulta el recorrido configurado para
    un servicio en una sede.

    No modifica información.
    """

    consulta = RecorridoServicio.query.filter_by(
        sede_id=sede_id,
        servicio_id=servicio_id
    )

    if solo_activo:
        consulta = consulta.filter_by(activo=True)

    recorrido = consulta.order_by(
        RecorridoServicio.version.desc()
    ).first()

    if not recorrido:
        return {
            'success': False,
            'error': 'No existe un recorrido configurado'
        }

    pasos = RecorridoPaso.query.filter_by(
        recorrido_id=recorrido.id
    ).order_by(
        RecorridoPaso.orden
    ).all()

    return {
        'success': True,
        'recorrido_id': recorrido.id,
        'sede_id': recorrido.sede_id,
        'servicio_id': recorrido.servicio_id,
        'version': recorrido.version,
        'activo': recorrido.activo,
        'pasos': [
            {
                'id': paso.id,
                'area_id': paso.area_id,
                'area': paso.area.nombre,
                'orden': paso.orden,
                'tipo_paso': paso.tipo_paso
            }
            for paso in pasos
        ]
    }


def validar_recorrido_servicio(recorrido_id):
    """
    Valida que un recorrido pueda activarse.

    No modifica la base de datos.
    """

    recorrido = RecorridoServicio.query.get(recorrido_id)

    if not recorrido:
        return {
            'success': False,
            'error': 'Recorrido no encontrado'
        }

    servicio_sede = ServicioSede.query.filter_by(
        sede_id=recorrido.sede_id,
        servicio_id=recorrido.servicio_id,
        disponible=True
    ).first()

    if not servicio_sede:
        return {
            'success': False,
            'error': 'El servicio no está disponible en esta sede'
        }

    pasos = RecorridoPaso.query.filter_by(
        recorrido_id=recorrido.id
    ).order_by(
        RecorridoPaso.orden
    ).all()

    if not pasos:
        return {
            'success': False,
            'error': 'El recorrido no tiene pasos'
        }

    for paso in pasos:
        configuracion_area = SedeArea.query.filter_by(
            sede_id=recorrido.sede_id,
            area_id=paso.area_id,
            activo=True
        ).first()

        if not configuracion_area:
            return {
                'success': False,
                'error': (
                    f'El área {paso.area_id} no está '
                    'habilitada en esta sede'
                )
            }

    return {
        'success': True,
        'message': 'Recorrido válido',
        'recorrido_id': recorrido.id,
        'total_pasos': len(pasos)
    }



def activar_recorrido_servicio(recorrido_id):
    """
    Publica un recorrido BORRADOR y archiva
    la version anteriormente publicada.

    Orden de bloqueos:
    1. ServicioSede
    2. RecorridoServicio

    La operacion es transaccional.
    """

    try:
        # ============================================
        # 1. OBTENER REFERENCIA
        # ============================================

        referencia = db.session.get(
            RecorridoServicio,
            recorrido_id
        )

        if referencia is None:
            db.session.rollback()
            return {
                "success": False,
                "error": "Recorrido no encontrado"
            }

        # ============================================
        # 2. BLOQUEAR SEDE-SERVICIO
        # ============================================

        configuracion = (
            ServicioSede.query
            .filter_by(
                sede_id=referencia.sede_id,
                servicio_id=referencia.servicio_id
            )
            .with_for_update()
            .first()
        )

        if configuracion is None:
            db.session.rollback()
            return {
                "success": False,
                "error": "Configuracion del servicio no encontrada"
            }

        # ============================================
        # 3. BLOQUEAR Y REFRESCAR RECORRIDO
        # ============================================

        recorrido = (
            RecorridoServicio.query
            .filter_by(id=recorrido_id)
            .with_for_update()
            .populate_existing()
            .first()
        )

        if recorrido is None:
            db.session.rollback()
            return {
                "success": False,
                "error": "Recorrido no disponible"
            }

        # ============================================
        # 4. VERIFICAR ESTADO
        # ============================================

        if (
            recorrido.estado_publicacion != "BORRADOR"
            or recorrido.activo is not False
        ):
            db.session.rollback()
            return {
                "success": False,
                "error": "Solo se pueden publicar borradores inactivos"
            }

        # ============================================
        # 5. VALIDAR RECORRIDO
        # ============================================

        validacion = validar_recorrido_servicio(
            recorrido.id
        )

        if not validacion["success"]:
            db.session.rollback()
            return validacion

        # ============================================
        # 6. PUBLICAR CON AUTORIZACION TEMPORAL
        # ============================================

        session = db.session()

        with autorizar_publicacion_recorridos(session):

            anteriores = (
                RecorridoServicio.query
                .filter(
                    RecorridoServicio.sede_id == recorrido.sede_id,
                    RecorridoServicio.servicio_id == recorrido.servicio_id,
                    RecorridoServicio.activo.is_(True)
                )
                .all()
            )

            for anterior in anteriores:
                if anterior.id != recorrido.id:
                    anterior.activo = False
                    anterior.estado_publicacion = "ARCHIVADO"

            # Archivar primero para respetar
            # el indice unico de recorridos activos.
            session.flush()

            recorrido.estado_publicacion = "PUBLICADO"
            recorrido.activo = True

            session.commit()

        # ============================================
        # 7. RESPUESTA EXITOSA
        # ============================================

        return {
            "success": True,
            "message": "Recorrido publicado correctamente",
            "recorrido_id": recorrido.id,
            "version": recorrido.version,
            "estado_publicacion": recorrido.estado_publicacion,
            "activo": recorrido.activo
        }

    except (SQLAlchemyError, ValueError) as error:

        db.session.rollback()

        return {
            "success": False,
            "error": "No se pudo publicar el recorrido",
            "detalle": str(error)
        }


    

def consultar_uso_recorrido(recorrido_id):
    """
    Consulta el estado de publicación y uso de un recorrido.
    No modifica registros.
    """

    recorrido = db.session.get(
        RecorridoServicio,
        recorrido_id
    )

    if recorrido is None:
        return {
            "success": False,
            "error": "Recorrido no encontrado"
        }

    total_asignaciones = (
        AtencionServicio.query
        .filter_by(recorrido_id=recorrido.id)
        .count()
    )

    return {
        "success": True,
        "recorrido_id": recorrido.id,
        "version": recorrido.version,
        "estado_publicacion": recorrido.estado_publicacion,
        "activo": recorrido.activo,
        "total_asignaciones": total_asignaciones,
        "puede_editar": (
            recorrido.estado_publicacion == "BORRADOR"
            and not recorrido.activo
            and total_asignaciones == 0
        )
    }



def preparar_asignacion_recorrido(sede_id, servicio_id):
    """
    Consulta el recorrido publicado para un servicio.

    No modifica la base de datos.
    No genera turnos ni movimientos.
    """

    recorrido = (
        RecorridoServicio.query
        .filter_by(
            sede_id=sede_id,
            servicio_id=servicio_id,
            estado_publicacion="PUBLICADO",
            activo=True
        )
        .first()
    )

    if recorrido is None:
        return {
            "success": False,
            "accion": "SIN_RECORRIDO",
            "mensaje": "No existe un recorrido publicado para este servicio"
        }

    pasos = (
        RecorridoPaso.query
        .filter_by(recorrido_id=recorrido.id)
        .order_by(RecorridoPaso.orden, RecorridoPaso.id)
        .all()
    )

    if not pasos:
        return {
            "success": False,
            "accion": "RECORRIDO_SIN_PASOS",
            "mensaje": "El recorrido no tiene pasos configurados"
        }

    primer_paso = pasos[0]

    return {
        "success": True,
        "accion": "ASIGNACION_DISPONIBLE",
        "recorrido_id": recorrido.id,
        "version": recorrido.version,
        "paso_actual_id": primer_paso.id,
        "area_inicial_id": primer_paso.area_id,
        "total_pasos": len(pasos)
    }



def asignar_recorrido_atencion_servicio(
    atencion_servicio,
    confirmar=False
):
    """
    Asigna un recorrido publicado a un servicio
    de una atención.

    No genera turnos.
    No mueve pacientes.
    No modifica pagos.
    No realiza commit.

    Si confirmar=False, solo simula la asignación.
    """

    if atencion_servicio is None:
        return {
            "success": False,
            "error": "Servicio de atención no encontrado"
        }

    if atencion_servicio.recorrido_id is not None:
        return {
            "success": False,
            "error": "El servicio ya tiene un recorrido asignado"
        }

    atencion = atencion_servicio.atencion

    if atencion is None:
        return {
            "success": False,
            "error": "La atención asociada no existe"
        }

    resultado = preparar_asignacion_recorrido(
        sede_id=atencion.sede_id,
        servicio_id=atencion_servicio.servicio_id
    )

    if not resultado["success"]:
        return resultado

    if confirmar:
        atencion_servicio.recorrido_id = resultado["recorrido_id"]
        atencion_servicio.paso_actual_id = resultado["paso_actual_id"]

    return {
        "success": True,
        "accion": (
            "RECORRIDO_ASIGNADO"
            if confirmar
            else "SIMULACION_ASIGNACION"
        ),
        "atencion_id": atencion.id,
        "atencion_servicio_id": atencion_servicio.id,
        "recorrido_id": resultado["recorrido_id"],
        "version": resultado["version"],
        "paso_actual_id": resultado["paso_actual_id"],
        "area_inicial_id": resultado["area_inicial_id"],
        "confirmado": confirmar
    }

    
def crear_nueva_version_recorrido(recorrido_id):
    """
    Crea una nueva versión BORRADOR a partir
    de un recorrido PUBLICADO o ARCHIVADO.

    - No modifica la versión original.
    - Copia sus pasos.
    - No activa el nuevo recorrido.
    - No afecta las atenciones existentes.
    """

    from sqlalchemy import func

    try:
        original = db.session.get(
            RecorridoServicio,
            recorrido_id
        )

        if original is None:
            return {
                "success": False,
                "error": "Recorrido no encontrado"
            }

        if original.estado_publicacion not in (
            "PUBLICADO",
            "ARCHIVADO"
        ):
            return {
                "success": False,
                "error": (
                    "Solo se pueden crear nuevas versiones "
                    "desde recorridos publicados o archivados"
                )
            }

        # Serializar la creación de versiones
        # del mismo servicio y sede.
        configuracion = (
            ServicioSede.query
            .filter_by(
                sede_id=original.sede_id,
                servicio_id=original.servicio_id
            )
            .with_for_update()
            .first()
        )

        if configuracion is None:
            db.session.rollback()
            return {
                "success": False,
                "error": "Configuración del servicio no encontrada"
            }

        # Evitar múltiples borradores para
        # una misma combinación sede-servicio.
        borrador_existente = (
            RecorridoServicio.query
            .filter_by(
                sede_id=original.sede_id,
                servicio_id=original.servicio_id,
                estado_publicacion="BORRADOR"
            )
            .first()
        )

        if borrador_existente is not None:
            db.session.rollback()
            return {
                "success": False,
                "accion": "BORRADOR_EXISTENTE",
                "error": "Ya existe un borrador para este servicio",
                "recorrido_id": borrador_existente.id,
                "version": borrador_existente.version
            }

        version_maxima = (
            db.session.query(
                func.max(RecorridoServicio.version)
            )
            .filter(
                RecorridoServicio.sede_id == original.sede_id,
                RecorridoServicio.servicio_id == original.servicio_id
            )
            .scalar()
        ) or 0

        nueva_version = version_maxima + 1

        nuevo = RecorridoServicio(
            sede_id=original.sede_id,
            servicio_id=original.servicio_id,
            version=nueva_version,
            estado_publicacion="BORRADOR",
            activo=False
        )

        db.session.add(nuevo)
        db.session.flush()

        pasos_originales = (
            RecorridoPaso.query
            .filter_by(recorrido_id=original.id)
            .order_by(
                RecorridoPaso.orden,
                RecorridoPaso.id
            )
            .all()
        )

        for paso in pasos_originales:
            nuevo_paso = RecorridoPaso(
                recorrido_id=nuevo.id,
                area_id=paso.area_id,
                orden=paso.orden,
                tipo_paso=paso.tipo_paso
            )

            db.session.add(nuevo_paso)

        db.session.flush()

        nuevo_id = nuevo.id
        total_pasos = len(pasos_originales)

        db.session.commit()

        return {
            "success": True,
            "accion": "VERSION_CREADA",
            "recorrido_original_id": original.id,
            "recorrido_nuevo_id": nuevo_id,
            "version": nueva_version,
            "estado_publicacion": "BORRADOR",
            "activo": False,
            "total_pasos": total_pasos
        }

    except SQLAlchemyError as error:
        db.session.rollback()

        return {
            "success": False,
            "error": "No se pudo crear la nueva versión",
            "detalle": str(error)
        }
def verificar_edicion_recorrido(recorrido_id):
    """
    Determina si un recorrido puede modificarse.

    Solo lectura.
    No modifica registros ni realiza commit.
    """

    resultado = consultar_uso_recorrido(recorrido_id)

    if not resultado.get("success"):
        return resultado

    if not resultado["puede_editar"]:
        return {
            "success": False,
            "accion": "EDICION_BLOQUEADA",
            "recorrido_id": recorrido_id,
            "mensaje": (
                "Este recorrido no puede modificarse "
                "porque está publicado, archivado "
                "o tiene servicios asignados."
            )
        }

    return {
        "success": True,
        "accion": "EDICION_PERMITIDA",
        "recorrido_id": recorrido_id,
        "mensaje": "El recorrido puede modificarse"
    }



# =====================================================
# BLOQUEO COORDINADO DE RECORRIDOS
# =====================================================

def bloquear_recorrido_para_edicion(recorrido_id):
    """
    Bloquea la configuración sede-servicio y
    después el recorrido, siempre en ese orden.

    No modifica datos.
    No realiza commit.

    Debe ejecutarse dentro de la transacción
    de la operación que lo utiliza.
    """

    # 1. Consultar la identidad del recorrido.
    referencia = db.session.get(
        RecorridoServicio,
        recorrido_id
    )

    if referencia is None:
        return None

    # 2. Bloquear la configuración sede-servicio.
    configuracion = (
        ServicioSede.query
        .filter_by(
            sede_id=referencia.sede_id,
            servicio_id=referencia.servicio_id
        )
        .with_for_update()
        .first()
    )

    if configuracion is None:
        return None

    # 3. Bloquear y refrescar el recorrido.
    recorrido = (
        RecorridoServicio.query
        .filter_by(id=recorrido_id)
        .with_for_update()
        .populate_existing()
        .first()
    )

    return recorrido

def editar_paso_recorrido(
    recorrido_id,
    paso_id,
    nueva_area_id
):
    """
    Modifica el área de un paso únicamente
    cuando el recorrido es un borrador editable.

    No altera versiones publicadas o archivadas.
    """

    try:
        # 1. Bloquear el recorrido durante la edición.
        recorrido = bloquear_recorrido_para_edicion(
            recorrido_id
        )

        if recorrido is None:
            db.session.rollback()
            return {
                "success": False,
                "accion": "RECORRIDO_NO_ENCONTRADO"
            }

        # 2. Comprobar permisos de edición.
        validacion = verificar_edicion_recorrido(
            recorrido_id
        )

        if not validacion["success"]:
            db.session.rollback()
            return validacion

        # 3. Comprobar que el paso pertenece al recorrido.
        paso = RecorridoPaso.query.filter_by(
            id=paso_id,
            recorrido_id=recorrido_id
        ).first()

        if paso is None:
            db.session.rollback()
            return {
                "success": False,
                "accion": "PASO_NO_ENCONTRADO"
            }

        # 4. Verificar el área en la sede.
        area_configurada = SedeArea.query.filter_by(
            sede_id=recorrido.sede_id,
            area_id=nueva_area_id,
            activo=True
        ).first()

        if area_configurada is None:
            db.session.rollback()
            return {
                "success": False,
                "accion": "AREA_NO_HABILITADA",
                "mensaje": (
                    "El área seleccionada no está "
                    "habilitada en esta sede."
                )
            }

        # 5. Actualizar únicamente el borrador.
        area_anterior_id = paso.area_id

        paso.area_id = nueva_area_id

        db.session.commit()

        return {
            "success": True,
            "accion": "PASO_ACTUALIZADO",
            "recorrido_id": recorrido_id,
            "paso_id": paso_id,
            "area_anterior_id": area_anterior_id,
            "area_nueva_id": nueva_area_id
        }

    except SQLAlchemyError as error:
        db.session.rollback()

        return {
            "success": False,
            "accion": "ERROR_EDICION",
            "detalle": str(error)
        }

def agregar_paso_recorrido(
    recorrido_id,
    area_id,
    posicion,
    tipo_paso
):
    """
    Inserta un paso en un recorrido BORRADOR.

    Reorganiza los órdenes sin violar
    UNIQUE(recorrido_id, orden).

    La operación es transaccional.
    """

    try:
        # 1. Bloquear el recorrido.
        recorrido = (
            RecorridoServicio.query
            .filter_by(id=recorrido_id)
            .with_for_update()
            .first()
        )

        if recorrido is None:
            db.session.rollback()
            return {
                "success": False,
                "accion": "RECORRIDO_NO_ENCONTRADO"
            }

        # 2. Validar que sea editable.
        validacion = verificar_edicion_recorrido(
            recorrido_id
        )

        if not validacion["success"]:
            db.session.rollback()
            return validacion

        # 3. Comprobar que el área esté habilitada.
        configuracion = SedeArea.query.filter_by(
            sede_id=recorrido.sede_id,
            area_id=area_id,
            activo=True
        ).first()

        if configuracion is None:
            db.session.rollback()
            return {
                "success": False,
                "accion": "AREA_NO_HABILITADA"
            }

        # 4. Consultar los pasos existentes.
        pasos = (
            RecorridoPaso.query
            .filter_by(recorrido_id=recorrido_id)
            .order_by(
                RecorridoPaso.orden,
                RecorridoPaso.id
            )
            .all()
        )

        total = len(pasos)

        # La posición debe estar entre 1 y total + 1.
        if (
            type(posicion) is not int
            or posicion < 1
            or posicion > total + 1
        ):
            db.session.rollback()
            return {
                "success": False,
                "accion": "POSICION_INVALIDA",
                "posicion_maxima": total + 1
            }

        if not isinstance(tipo_paso, str) or not tipo_paso.strip():
            db.session.rollback()
            return {
                "success": False,
                "accion": "TIPO_PASO_INVALIDO"
            }

        # 5. Mover temporalmente los pasos
        # a órdenes superiores, todos libres.
        orden_maximo = max(
            (paso.orden for paso in pasos),
            default=0
        )

        desplazamiento = orden_maximo + total + 1

        for paso in pasos:
            paso.orden = (
                desplazamiento + paso.orden
            )

        db.session.flush()

        # 6. Crear el nuevo paso.
        nuevo = RecorridoPaso(
            recorrido_id=recorrido_id,
            area_id=area_id,
            orden=desplazamiento + orden_maximo + 1,
            tipo_paso=tipo_paso
        )

        db.session.add(nuevo)
        db.session.flush()

        # 7. Construir la secuencia definitiva.
        secuencia = list(pasos)
        secuencia.insert(posicion - 1, nuevo)

        for numero, paso in enumerate(
            secuencia,
            start=1
        ):
            paso.orden = numero

        db.session.flush()

        nuevo_id = nuevo.id

        db.session.commit()

        return {
            "success": True,
            "accion": "PASO_AGREGADO",
            "recorrido_id": recorrido_id,
            "paso_id": nuevo_id,
            "area_id": area_id,
            "posicion": posicion,
            "total_pasos": total + 1
        }

    except SQLAlchemyError as error:
        db.session.rollback()
        return {
            "success": False,
            "accion": "ERROR_AGREGAR_PASO",
            "detalle": str(error)
        }

def eliminar_paso_recorrido(recorrido_id, paso_id):
    """
    Elimina un paso de un recorrido BORRADOR.

    - Bloquea el recorrido durante la operación.
    - No permite editar versiones publicadas.
    - No permite dejar un recorrido sin pasos.
    - Reorganiza los órdenes de forma segura.
    - Confirma todos los cambios en una transacción.
    """

    try:
        # ============================================
        # 1. BLOQUEAR EL RECORRIDO
        # ============================================

        recorrido = (
            RecorridoServicio.query
            .filter_by(id=recorrido_id)
            .with_for_update()
            .first()
        )

        if recorrido is None:
            db.session.rollback()
            return {
                "success": False,
                "accion": "RECORRIDO_NO_ENCONTRADO"
            }

        # ============================================
        # 2. VALIDAR QUE SEA EDITABLE
        # ============================================

        validacion = verificar_edicion_recorrido(
            recorrido_id
        )

        if not validacion.get("success"):
            db.session.rollback()
            return validacion

        # ============================================
        # 3. CONSULTAR LOS PASOS EXISTENTES
        # ============================================

        pasos = (
            RecorridoPaso.query
            .filter_by(recorrido_id=recorrido_id)
            .order_by(
                RecorridoPaso.orden,
                RecorridoPaso.id
            )
            .all()
        )

        paso_eliminar = next(
            (p for p in pasos if p.id == paso_id),
            None
        )

        if paso_eliminar is None:
            db.session.rollback()
            return {
                "success": False,
                "accion": "PASO_NO_ENCONTRADO"
            }

        if len(pasos) <= 1:
            db.session.rollback()
            return {
                "success": False,
                "accion": "ULTIMO_PASO",
                "mensaje": (
                    "No se puede eliminar el último "
                    "paso de un recorrido."
                )
            }

        # ============================================
        # 4. ELIMINAR EL PASO
        # ============================================

        area_eliminada_id = paso_eliminar.area_id

        restantes = [
            p for p in pasos
            if p.id != paso_id
        ]

        db.session.delete(paso_eliminar)
        db.session.flush()

        # ============================================
        # 5. MOVER LOS ÓRDENES TEMPORALMENTE
        # ============================================

        orden_maximo = max(
            (p.orden for p in restantes),
            default=0
        )

        desplazamiento = (
            orden_maximo + len(restantes) + 1
        )

        for paso in restantes:
            paso.orden = paso.orden + desplazamiento

        db.session.flush()

        # ============================================
        # 6. RENUMERAR LOS PASOS
        # ============================================

        for numero, paso in enumerate(
            restantes,
            start=1
        ):
            paso.orden = numero

        db.session.flush()

        total_restante = len(restantes)

        # ============================================
        # 7. CONFIRMAR CAMBIOS
        # ============================================

        db.session.commit()

        return {
            "success": True,
            "accion": "PASO_ELIMINADO",
            "recorrido_id": recorrido_id,
            "paso_eliminado_id": paso_id,
            "area_eliminada_id": area_eliminada_id,
            "total_pasos": total_restante
        }

    except SQLAlchemyError as error:
        db.session.rollback()

        return {
            "success": False,
            "accion": "ERROR_ELIMINAR_PASO",
            "detalle": str(error)
        }
