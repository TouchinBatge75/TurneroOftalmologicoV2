# run.py
from app import create_app

# Crear la aplicación
app = create_app()

if __name__ == '__main__':
    print("=" * 50)
    print("🏥 TURNERO OFTALMOLÓGICO - BACKEND")
    print("=" * 50)
    print("✅ Base de datos: SQLite (turnero.db)")
    print("✅ ORM: SQLAlchemy")
    print("✅ API REST: Habilitada")
    print("=" * 50)
    print("🌐 Accede a:")
    print("   http://127.0.0.1:5000/")
    print("   http://127.0.0.1:5000/api/")
    print("   http://127.0.0.1:5000/api/test")
    print("   http://127.0.0.1:5000/api/doctores")
    print("   http://127.0.0.1:5000/api/turnos")
    print("=" * 50)
    print("⚡ Presiona Ctrl+C para detener")
    print("=" * 50)
    
    # Ejecutar servidor
    app.run(debug=True, host='127.0.0.1', port=5000)