
from flask import Flask, render_template, jsonify
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

from config import Config


# =====================================================
# EXTENSIONES
# =====================================================

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()


# =====================================================
# FACTORY DE FLASK
# =====================================================

def create_app():

    app = Flask(
        __name__,
        template_folder='../templates'
    )

    # =============================================
    # CONFIGURACIÓN
    # =============================================

    app.config.from_object(Config)

    # =============================================
    # INICIALIZAR EXTENSIONES
    # =============================================

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    # =============================================
    # IMPORTAR MODELOS
    # =============================================

    from app import models

    # =============================================
    # CARGAR OPERADOR AUTENTICADO
    # =============================================

    @login_manager.user_loader
    def cargar_operador(operador_id):

        try:
            return db.session.get(
                models.Operador,
                int(operador_id)
            )

        except (TypeError, ValueError):
            return None

    # =============================================
    # ACCESO NO AUTORIZADO
    # =============================================

    @login_manager.unauthorized_handler
    def acceso_no_autorizado():

        return jsonify({
            'success': False,
            'error': 'Debe iniciar sesión'
        }), 401

    # =============================================
    # REGISTRAR BLUEPRINTS
    # =============================================

    from app import routes
    app.register_blueprint(routes.bp)

    from app import auth
    app.register_blueprint(auth.bp)

    from app import admin_consultorios
    app.register_blueprint(
        admin_consultorios.bp_admin_consultorios
    )

    from app import admin_asignaciones

    app.register_blueprint(
        admin_asignaciones.bp_admin_asignaciones
    )

    from app import notificaciones

    app.register_blueprint(
        notificaciones.bp_notificaciones
    )

    # =============================================
    # RUTAS DE INTERFAZ
    # =============================================

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
        return render_template(
            'toma_calculos_dashboard.html'
        )

    @app.route('/trabajo-social')
    def trabajo_social():
        return render_template(
            'trabajo_social_dashboard.html'
        )

    return app
