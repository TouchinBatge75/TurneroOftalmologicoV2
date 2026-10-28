
"""
TURNERO OFTALMOLÓGICO V2
Verificación de políticas y accesos denegados.

Ejecutar desde la carpeta raíz del proyecto:
    python verificar_routes_turnero_v2.py

IMPORTANTE:
Usar solo en desarrollo y con respaldo.
Las peticiones POST son reales; si la seguridad falla,
podrían modificar datos.
"""

import ast
from pathlib import Path

from app import create_app, db
from app.models import Operador, TurnoArea


# =====================================================
# 1. COBERTURA ESTÁTICA DE POLÍTICAS
# =====================================================

RUTA_ARCHIVO = (
    Path(__file__).resolve().parent
    / "app"
    / "routes.py"
)

if not RUTA_ARCHIVO.is_file():
    raise SystemExit(
        f"No se encontró el archivo: {RUTA_ARCHIVO}"
    )

modulo = ast.parse(
    RUTA_ARCHIVO.read_text(encoding="utf-8")
)

politicas = None

for nodo in modulo.body:
    if (
        isinstance(nodo, ast.Assign)
        and any(
            isinstance(destino, ast.Name)
            and destino.id == "_POLITICAS_API"
            for destino in nodo.targets
        )
    ):
        politicas = ast.literal_eval(nodo.value)
        break

if not isinstance(politicas, dict):
    raise SystemExit(
        "No se encontró el diccionario "
        "_POLITICAS_API en routes.py"
    )

funciones_con_ruta = {
    nodo.name
    for nodo in modulo.body
    if isinstance(
        nodo,
        (ast.FunctionDef, ast.AsyncFunctionDef)
    )
    and any(
        isinstance(decorador, ast.Call)
        and isinstance(
            decorador.func,
            ast.Attribute
        )
        and decorador.func.attr == "route"
        for decorador in nodo.decorator_list
    )
}

sin_politica = (
    funciones_con_ruta - set(politicas)
)

print("=" * 55)
print("TURNERO V2 - VERIFICACIÓN DE SEGURIDAD")
print("=" * 55)

print(
    "Políticas configuradas:",
    len(politicas)
)

print(
    "Rutas detectadas:",
    len(funciones_con_ruta)
)

if sin_politica:
    raise AssertionError(
        f"Rutas sin política: "
        f"{sorted(sin_politica)}"
    )

print(
    "Cobertura de políticas: CORRECTA"
)


# =====================================================
# 2. CARGAR IDENTIFICADORES
# =====================================================

app = create_app()

with app.app_context():

    admin = Operador.query.filter_by(
        usuario="admin"
    ).first()

    recepcion = Operador.query.filter_by(
        usuario="recepcion_prueba"
    ).first()

    turno = TurnoArea.query.filter_by(
        numero_turno="TRA-0047"
    ).first()

    if admin is None:
        raise SystemExit(
            "No se encontró el operador admin"
        )

    if recepcion is None:
        raise SystemExit(
            "No se encontró el operador recepcion_prueba"
        )

    admin_id = admin.id
    recepcion_id = recepcion.id

    turno_id = None
    estado_inicial = None

    paciente_id = None
    afiliado_inicial = None
    numero_afiliacion_inicial = None

    if (
        turno is not None
        and turno.estado == "ESPERA"
    ):

        if (
            turno.area is not None
            and turno.area.codigo == "TRABAJO_SOCIAL"
        ):

            turno_id = turno.id
            estado_inicial = turno.estado

            if (
                turno.atencion is not None
                and turno.atencion.paciente is not None
            ):

                paciente = turno.atencion.paciente

                paciente_id = paciente.id

                afiliado_inicial = (
                    paciente.afiliado
                )

                numero_afiliacion_inicial = (
                    paciente.numero_afiliacion
                )


# =====================================================
# 3. FUNCIONES AUXILIARES DE PRUEBA
# =====================================================

def simular_sesion(cliente, operador_id):
    """
    Configura una sesión para un cliente de pruebas.

    Cada operador utiliza un cliente independiente.
    """

    with cliente.session_transaction() as sesion:

        sesion["_user_id"] = str(
            operador_id
        )

        sesion["_fresh"] = True


def comprobar_respuesta(
    nombre,
    respuesta,
    esperado
):
    """
    Comprueba que una petición HTTP devuelva
    el código esperado.
    """

    print(
        f"{nombre}: HTTP "
        f"{respuesta.status_code}"
    )

    if respuesta.status_code != esperado:

        print(
            "Respuesta:",
            respuesta.get_json(silent=True)
        )

        raise AssertionError(
            f"{nombre}: se esperaba HTTP "
            f"{esperado} pero llegó "
            f"{respuesta.status_code}"
        )

    print("  CORRECTO")


# =====================================================
# 4. PRUEBA: USUARIO SIN SESIÓN
# =====================================================

cliente_anonimo = app.test_client()

respuesta = cliente_anonimo.post(
    "/api/control/registrar",
    json={}
)

comprobar_respuesta(
    "Sin sesión",
    respuesta,
    401
)


# =====================================================
# 5. PRUEBA: ADMINISTRADOR
# =====================================================

# Crear un cliente independiente.
cliente_admin = app.test_client()

# Simular su sesión.
simular_sesion(
    cliente_admin,
    admin_id
)

# =============================================
# 5.1 VERIFICAR QUE FLASK RECONOZCA AL ADMIN
# =============================================

respuesta_sesion = cliente_admin.get(
    "/auth/me"
)

comprobar_respuesta(
    "Sesión simulada de admin",
    respuesta_sesion,
    200
)

# =============================================
# 5.2 ADMIN SIN PERMISO DE RECEPCIÓN
# =============================================

respuesta = cliente_admin.post(
    "/api/control/registrar",
    json={}
)

comprobar_respuesta(
    "Admin sin permiso de recepción",
    respuesta,
    403
)


# =====================================================
# 6. PRUEBAS: RECEPCIÓN CONTRA TRABAJO SOCIAL
# =====================================================

if turno_id is None:

    print(
        "AVISO: No existe TRA-0047 "
        "en Trabajo Social y estado ESPERA."
    )

    print(
        "Se omiten las pruebas "
        "dependientes de ese turno."
    )

else:

    print(
        "Turno de prueba:",
        "TRA-0047"
    )

    print(
        "Estado inicial:",
        estado_inicial
    )

    # Cliente independiente para Recepción.
    cliente_recepcion = app.test_client()

    simular_sesion(
        cliente_recepcion,
        recepcion_id
    )

    # =============================================
    # 6.1 VERIFICAR SESIÓN DE RECEPCIÓN
    # =============================================

    respuesta_sesion = cliente_recepcion.get(
        "/auth/me"
    )

    comprobar_respuesta(
        "Sesión simulada de recepción",
        respuesta_sesion,
        200
    )

    # =============================================
    # 6.2 INTENTAR LLAMAR, INICIAR Y OMITIR
    # =============================================

    for accion in (
        "llamar",
        "iniciar",
        "omitir"
    ):

        respuesta = cliente_recepcion.post(
            f"/api/turnos/{turno_id}/{accion}",
            json={}
        )

        comprobar_respuesta(
            accion.upper(),
            respuesta,
            403
        )

    # =============================================
    # 6.3 INTENTAR AFILIAR PACIENTE
    # =============================================

    respuesta = cliente_recepcion.post(
        f"/api/trabajo-social/{turno_id}/afiliar",
        json={}
    )

    comprobar_respuesta(
        "AFILIAR",
        respuesta,
        403
    )

    # =============================================
    # 6.4 COMPROBAR INTEGRIDAD DE LOS DATOS
    # =============================================

    # Usamos un contexto nuevo, separado
    # de todas las peticiones HTTP.

    with app.app_context():

        turno_final = db.session.get(
            TurnoArea,
            turno_id
        )

        if turno_final is None:
            raise AssertionError(
                "Desapareció el turno de prueba"
            )

        # Verificar estado del turno.
        if turno_final.estado != estado_inicial:

            raise AssertionError(
                f"El turno cambió: "
                f"{estado_inicial} -> "
                f"{turno_final.estado}"
            )

        # Verificar datos del paciente.
        if paciente_id is not None:

            paciente_final = (
                turno_final.atencion.paciente
            )

            if (
                paciente_final is None
                or paciente_final.id != paciente_id
            ):

                raise AssertionError(
                    "Cambió la relación con el paciente"
                )

            if (
                paciente_final.afiliado
                != afiliado_inicial
            ):

                raise AssertionError(
                    "Cambió el estado de afiliación"
                )

            if (
                paciente_final.numero_afiliacion
                != numero_afiliacion_inicial
            ):

                raise AssertionError(
                    "Cambió el número de afiliación"
                )

        print(
            "Estado final del turno:",
            turno_final.estado
        )

        print(
            "Integridad de turno y afiliación: "
            "CORRECTA"
        )


# =====================================================
# 7. RESULTADO FINAL
# =====================================================

print("=" * 55)
print("VERIFICACIONES COMPLETADAS")
print("=" * 55)

print(
    "Todas las comprobaciones "
    "ejecutadas fueron aprobadas."
)

print(
    "NOTA: Este script no valida "
    "operaciones autorizadas ni protección CSRF."
)
