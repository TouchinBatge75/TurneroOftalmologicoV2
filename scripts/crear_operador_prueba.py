
from getpass import getpass

from app import create_app, db
from app.models import Operador, Sede


def crear_operador_prueba():
    app = create_app()

    with app.app_context():
        usuario = "recepcion_prueba"

        existente = Operador.query.filter_by(
            usuario=usuario
        ).first()

        if existente:
            print(
                f"El operador {usuario} ya existe. "
                f"ID: {existente.id}"
            )
            return

        sede = Sede.query.filter_by(
            codigo="ORIZABA"
        ).first()

        if sede is None:
            print("ERROR: No existe la sede ORIZABA.")
            return

        password = getpass(
            "Contraseña del operador de prueba: "
        )

        if len(password) < 12:
            print(
                "ERROR: La contraseña debe tener "
                "al menos 12 caracteres."
            )
            return

        confirmacion = getpass(
            "Confirmar contraseña: "
        )

        if password != confirmacion:
            print("ERROR: Las contraseñas no coinciden.")
            return

        operador = Operador(
            nombre="Recepción Prueba",
            usuario=usuario,
            rol="RECEPCION",
            sede_id=sede.id,
            proveedor_identidad="LOCAL",
            activo=True
        )

        operador.establecer_password(password)

        try:
            db.session.add(operador)
            db.session.commit()

            print()
            print("Operador creado correctamente.")
            print(f"ID: {operador.id}")
            print(f"Usuario: {operador.usuario}")
            print(f"Rol: {operador.rol}")
            print(f"Sede: {sede.nombre}")

        except Exception:
            db.session.rollback()
            raise


if __name__ == "__main__":
    crear_operador_prueba()
