
from getpass import getpass

from app import create_app, db
from app.models import Operador, Sede


def crear_administrador():
    app = create_app()

    with app.app_context():

        sede = Sede.query.filter_by(
            codigo="ORIZABA"
        ).first()

        if sede is None:
            print("ERROR: No existe la sede ORIZABA.")
            return

        existente = Operador.query.filter_by(
            usuario="admin"
        ).first()

        if existente is not None:
            print("El administrador ya existe.")
            print(f"ID: {existente.id}")
            return

        password = getpass(
            "Contraseña del administrador: "
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
            nombre="Administrador General",
            usuario="admin",
            rol="ADMIN",
            sede_id=sede.id,
            proveedor_identidad="LOCAL",
            activo=True
        )

        operador.establecer_password(password)

        try:
            db.session.add(operador)
            db.session.commit()

            print()
            print("Administrador creado correctamente.")
            print(f"ID: {operador.id}")
            print(f"Usuario: {operador.usuario}")
            print(f"Rol: {operador.rol}")
            print(f"Sede: {sede.nombre}")

        except Exception:
            db.session.rollback()
            raise


if __name__ == "__main__":
    crear_administrador()
