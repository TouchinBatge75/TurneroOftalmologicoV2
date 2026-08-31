from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from config import Config

db = SQLAlchemy()
migrate = Migrate()


def create_app():
    """Factory de Flask"""

    app = Flask(
        __name__,
        template_folder='../templates'
    )

    # =========================
    # CONFIGURACIÓN
    # =========================
    app.config.from_object(Config)

    # =========================
    # INICIALIZAR EXTENSIONES
    # =========================
    db.init_app(app)
    migrate.init_app(app, db)

    # Importar modelos después de inicializar db
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

    return app