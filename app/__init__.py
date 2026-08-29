# app/__init__.py
from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def create_app():
    """Factory de Flask - VERSIÓN SIMPLIFICADA"""

    app = Flask(__name__, template_folder='../templates')

    # =========================
    # CONFIGURACIÓN
    # =========================
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///turnero.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = 'clave-secreta-temporal'

    # =========================
    # INICIALIZAR SQLALCHEMY
    # =========================
    db.init_app(app)

    # Importar modelos DESPUÉS de inicializar db
    from app import models

    # =========================
    # REGISTRAR API
    # =========================
    from app import routes
    app.register_blueprint(routes.bp)

    # =========================
    # RUTAS DE INTERFAZ
    # =========================

    @app.route('/')
    def home():
        return render_template('recepcion.html')

    @app.route('/recepcion')
    def recepcion():
        return render_template('recepcion.html')

    @app.route('/doctor/login')
    def doctor_login():
        return render_template('doctor_login.html')

    @app.route('/doctor/dashboard')
    def doctor_dashboard():
        return render_template('doctor_dashboard.html')

    @app.route('/toma-calculos')
    def toma_calculos():
        return render_template('toma_calculos_dashboard.html')

    @app.route('/trabajo-social')
    def trabajo_social():
        return render_template('trabajo_social_dashboard.html')

    # =========================
    # CREAR TABLAS
    # =========================
    with app.app_context():
        db.create_all()
        print("✅ Tablas creadas en la base de datos")

    return app