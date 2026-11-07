
# =====================================================
# TURNERO V2 - PROTECCIÓN DE RECORRIDOS
# Archivo: app/proteccion_recorridos.py
# =====================================================

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

from app.models import RecorridoServicio, RecorridoPaso


@event.listens_for(Session, "before_flush")
def proteger_pasos_recorridos(session, flush_context, instances):
    """
    Protege los pasos de recorridos publicados
    y archivados frente a cambios ordinarios del ORM.

    No realiza commit.
    """

    
    # ================================================
    # 0. BLOQUEAR CAMBIOS DE PASOS DURANTE PUBLICACION
    # ================================================

    clave = "turnero_publicacion_recorridos_autorizada"

    if session.info.get(clave, False):

        cambios_pasos = any(
            isinstance(objeto, RecorridoPaso)
            for objeto in session.new
        )

        cambios_pasos = cambios_pasos or any(
            isinstance(objeto, RecorridoPaso)
            for objeto in session.deleted
        )

        cambios_pasos = cambios_pasos or any(
            isinstance(objeto, RecorridoPaso)
            and session.is_modified(
                objeto,
                include_collections=False
            )
            for objeto in session.dirty
        )

        if cambios_pasos:
            raise ValueError(
                "No se pueden modificar pasos durante "
                "la publicacion de recorridos."
            )


    # ================================================
    # 1. VERIFICAR PASOS MODIFICADOS
    # ================================================

    for paso in session.dirty:

        if not isinstance(paso, RecorridoPaso):
            continue

        if not session.is_modified(
            paso,
            include_collections=False
        ):
            continue

        estado = inspect(paso)

        if estado.attrs.recorrido_id.history.has_changes():
            raise ValueError(
                "No se permite cambiar el recorrido "
                "de un paso existente."
            )

        recorrido = session.get(
            RecorridoServicio,
            paso.recorrido_id
        )

        if recorrido is None:
            raise ValueError(
                "El recorrido asociado no existe."
            )

        if recorrido.estado_publicacion != "BORRADOR":
            raise ValueError(
                "No se pueden modificar pasos de "
                "recorridos publicados o archivados."
            )

    # ================================================
    # 2. VERIFICAR PASOS ELIMINADOS
    # ================================================

    for paso in session.deleted:

        if not isinstance(paso, RecorridoPaso):
            continue

        recorrido = session.get(
            RecorridoServicio,
            paso.recorrido_id
        )

        if recorrido is None:
            raise ValueError(
                "El recorrido asociado no existe."
            )

        if recorrido.estado_publicacion != "BORRADOR":
            raise ValueError(
                "No se pueden eliminar pasos de "
                "recorridos publicados o archivados."
            )

    # ================================================
    # 3. VERIFICAR PASOS NUEVOS
    # ================================================

    for paso in session.new:

        if not isinstance(paso, RecorridoPaso):
            continue

        recorrido = (
            paso.recorrido
            if paso.recorrido is not None
            else session.get(
                RecorridoServicio,
                paso.recorrido_id
            )
        )

        if recorrido is None:
            raise ValueError(
                "El recorrido asociado no existe."
            )

        if recorrido.estado_publicacion != "BORRADOR":
            raise ValueError(
                "Solo se pueden agregar pasos "
                "a recorridos en BORRADOR."
            )

        
# =====================================================
# PROTECCIÓN DE IDENTIDAD DE RECORRIDOS
# =====================================================

@event.listens_for(Session, "before_flush")
def proteger_identidad_recorridos(
    session,
    flush_context,
    instances
):
    """
    Impide modificar la identidad de recorridos
    existentes.

    Protege:
    - sede_id
    - servicio_id
    - version

    Las transiciones de estado se gestionarán
    mediante las funciones de publicación.
    """

    campos_protegidos = (
        "sede_id",
        "servicio_id",
        "version"
    )

    for recorrido in session.dirty:

        if not isinstance(recorrido, RecorridoServicio):
            continue

        estado = inspect(recorrido)

        for campo in campos_protegidos:
            historial = estado.attrs[campo].history

            if historial.has_changes():
                raise ValueError(
                    f"No se permite modificar {campo} "
                    "de un recorrido existente. "
                    "Para cambiar su configuración, "
                    "debe crearse un nuevo recorrido."
                )

    for recorrido in session.deleted:

        if not isinstance(recorrido, RecorridoServicio):
            continue

        if recorrido.estado_publicacion != "BORRADOR":
            raise ValueError(
                "No se pueden eliminar recorridos "
                "publicados o archivados."
            )

from contextlib import contextmanager


@contextmanager
def autorizar_publicacion_recorridos(session):
    """
    Marca temporalmente una operación de publicación
    como autorizada dentro de la sesión SQLAlchemy.

    No modifica registros ni realiza commit.
    """

    clave = "turnero_publicacion_recorridos_autorizada"

    if session.info.get(clave):
        raise RuntimeError(
            "Ya existe una autorización de publicación activa"
        )

    session.info[clave] = True

    try:
        yield
    finally:
        session.info.pop(clave, None)




# =====================================================
# PROTECCION DE ESTADOS DE PUBLICACION
# =====================================================

@event.listens_for(Session, "before_flush")
def proteger_estado_publicacion(
    session,
    flush_context,
    instances
):
    """
    Protege las transiciones de estado.

    Solo permite:
    BORRADOR  -> PUBLICADO
    PUBLICADO -> ARCHIVADO

    Ambas requieren autorizacion temporal.
    """

    clave = "turnero_publicacion_recorridos_autorizada"

    def valor_anterior(atributo):
        """
        Recupera el valor previo conocido por
        SQLAlchemy. Si no esta disponible,
        se rechaza la operacion.
        """

        historial = atributo.history

        if historial.deleted:
            return historial.deleted[0]

        if historial.unchanged:
            return historial.unchanged[0]

        raise ValueError(
            "No se pudo comprobar el estado anterior "
            "del recorrido."
        )

    for recorrido in session.dirty:

        if not isinstance(recorrido, RecorridoServicio):
            continue

        estado = inspect(recorrido)

        atributo_publicacion = (
            estado.attrs.estado_publicacion
        )

        atributo_activo = estado.attrs.activo

        cambio_publicacion = (
            atributo_publicacion.history.has_changes()
        )

        cambio_activo = (
            atributo_activo.history.has_changes()
        )

        if not cambio_publicacion and not cambio_activo:
            continue

        # ---------------------------------------------
        # 1. EXIGIR AUTORIZACION
        # ---------------------------------------------

        if not session.info.get(clave, False):
            raise ValueError(
                "No se permite modificar directamente "
                "el estado de publicacion o activacion "
                "de un recorrido."
            )

        # ---------------------------------------------
        # 2. RECUPERAR ESTADO ANTERIOR
        # ---------------------------------------------

        estado_anterior = valor_anterior(
            atributo_publicacion
        )

        activo_anterior = valor_anterior(
            atributo_activo
        )

        estado_nuevo = recorrido.estado_publicacion
        activo_nuevo = recorrido.activo

        # ---------------------------------------------
        # 3. DEFINIR TRANSICIONES PERMITIDAS
        # ---------------------------------------------

        transiciones_validas = (
            (
                "BORRADOR",
                False,
                "PUBLICADO",
                True
            ),
            (
                "PUBLICADO",
                True,
                "ARCHIVADO",
                False
            )
        )

        transicion = (
            estado_anterior,
            activo_anterior,
            estado_nuevo,
            activo_nuevo
        )

        if transicion not in transiciones_validas:
            raise ValueError(
                "Transicion de recorrido no permitida: "
                f"{estado_anterior} ({activo_anterior}) "
                "-> "
                f"{estado_nuevo} ({activo_nuevo})."
            )
