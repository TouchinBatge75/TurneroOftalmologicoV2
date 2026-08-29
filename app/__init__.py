# app/__init__.py
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

def create_app():
    """Factory de Flask - VERSIÓN SIMPLIFICADA"""
    app = Flask(__name__)
    
    # Configuración BÁSICA
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///turnero.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = 'clave-secreta-temporal'
    
    # Inicializar SQLAlchemy
    db.init_app(app)
    
    # Importar modelos DESPUÉS de inicializar db
    from app import models
    
    # Importar y registrar rutas
    from app import routes
    app.register_blueprint(routes.bp)
    
    # Ruta raíz
    @app.route('/')
    def home():
        return '''
        <h1>🏥 Turnero Oftalmológico</h1>
        <p><strong>Backend funcionando ✅</strong></p>
        <h3>Endpoints disponibles:</h3>
        <ul>
            <li><a href="/api/">/api/</a> - API Index</li>
            <li><a href="/api/doctores">/api/doctores</a> - Lista de doctores</li>
            <li><a href="/api/turnos">/api/turnos</a> - Lista de turnos</li>
            <li><a href="/api/test">/api/test</a> - Prueba de conexión</li>
        </ul>
        <p>Versión: 2.0 - SQLAlchemy</p>
        '''
    
    # Crear tablas en la base de datos
    with app.app_context():
        db.create_all()
        print("✅ Tablas creadas en la base de datos")
    
    return app