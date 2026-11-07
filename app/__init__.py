
from flask import (
    Flask,
    render_template,
    jsonify,
    redirect,
    url_for,
    abort
)

from flask_login import LoginManager, current_user
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect, generate_csrf

from config import Config


# =====================================================
# EXTENSIONES
# =====================================================

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()


# =====================================================
# FACTORY DE FLASK
# =====================================================

def create_app():

    app = Flask(
        __name__,
        template_folder='../templates'
    )

    app.config.from_object(Config)

    # =================================================
    # INICIALIZAR EXTENSIONES
    # =================================================

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

  
    # =================================================
    # MODELOS
    # =================================================

    from app import models

    # =================================================
    # PROTECCIÓN DE RECORRIDOS
    # =================================================

    from app import proteccion_recorridos


    # =================================================
    # AUTENTICACION
    # =================================================

    @login_manager.user_loader
    def cargar_operador(operador_id):

        try:
            return db.session.get(
                models.Operador,
                int(operador_id)
            )

        except (TypeError, ValueError):
            return None

    @login_manager.unauthorized_handler
    def acceso_no_autorizado():

        return jsonify({
            'success': False,
            'error': 'Debe iniciar sesión'
        }), 401

    # =================================================
    # BLUEPRINTS
    # =================================================

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

    from app import recepcion_kpis
    app.register_blueprint(
        recepcion_kpis.bp_recepcion_kpis
    )

    # =================================================
    # SEGUIMIENTO DE PACIENTES - RECEPCION V5
    # =================================================

    from app import seguimiento_recepcion

    app.register_blueprint(
        seguimiento_recepcion.bp_seguimiento_recepcion
    )

    from app.admin_operador_areas import bp_admin_operador_areas
    app.register_blueprint(bp_admin_operador_areas)

    # =================================================
    # INTERFACES V2
    # =================================================
    from app.permisos import verificar_permiso, verificar_area

    def operador_puede_recepcion():
        return (
            current_user.is_authenticated
            and current_user.is_active
            and bool(current_user.activo)
            and current_user.sede_id is not None
            and verificar_permiso('recepcion_ver')
            and verificar_area(current_user, current_user.sede_id, 'CAJA')
        )

    @app.route('/')
    def home():
        if not current_user.is_authenticated:
            return redirect(url_for('login_page'))
        return redirect(url_for('mi_panel'))

    @app.route('/login')
    def login_page():
        if current_user.is_authenticated:
            return redirect(url_for('mi_panel'))
        return render_template('login.html')

    @app.route('/mi-panel')
    def mi_panel():
        if not current_user.is_authenticated:
            return redirect(url_for('login_page'))
        if operador_puede_recepcion():
            return redirect(url_for('recepcion'))
        # Aun no existen las interfaces de medicos, areas ni administracion.
        # No permitir acceso a Recepcion como solucion provisional.
        return (
            '<!doctype html><html lang="es"><meta charset="utf-8">'
            '<title>Turnero | Sin panel</title>'
            '<body style="font-family:system-ui;margin:10vh auto;max-width:540px;padding:20px">'
            '<h1>Tu panel aún no está disponible</h1>'
            '<p>Tu sesión está activa, pero todavía no existe una pantalla operativa '
            'habilitada para tus permisos y área.</p>'
            '<p>Comunícate con Administración.</p>'
            '</body></html>', 200
        )

    @app.route('/recepcion')
    def recepcion():
        if not current_user.is_authenticated:
            return redirect(url_for('login_page'))
        if not operador_puede_recepcion():
            return jsonify({
                'success': False,
                'error': 'No tiene acceso a Recepción / Caja'
            }), 403
        return render_template('recepcion.html')


    # =================================================
    # INTERFACES V1 DESHABILITADAS TEMPORALMENTE
    # =================================================

    @app.route('/doctor/login')
    def doctor_login():
        abort(404)

    @app.route('/doctor/dashboard')
    def doctor_dashboard():
        abort(404)

    @app.route('/toma-calculos')
    def toma_calculos():
        abort(404)

    @app.route('/trabajo-social')
    def trabajo_social():
        abort(404)

    # =================================================
    # CSRF CENTRALIZADO
    # =================================================

    @app.route('/csrf-token', methods=['GET'])
    def obtener_csrf_token():

        return jsonify({
            'success': True,
            'csrf_token': generate_csrf()
        })
    
    return app
