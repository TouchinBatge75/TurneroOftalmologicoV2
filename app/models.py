from datetime import datetime
from app import db


# =====================================================
# PACIENTES
# =====================================================

class Paciente(db.Model):
    __tablename__ = 'pacientes'

    id = db.Column(db.Integer, primary_key=True)

    nombre = db.Column(db.String(100), nullable=False)
    apellido_paterno = db.Column(db.String(100))
    apellido_materno = db.Column(db.String(100))

    fecha_nacimiento = db.Column(db.Date)
    telefono = db.Column(db.String(20))

    numero_afiliacion = db.Column(db.String(50), unique=True)
    afiliado = db.Column(db.Boolean, default=False, nullable=False)

    activo = db.Column(db.Boolean, default=True, nullable=False)

    fecha_registro = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    atenciones = db.relationship(
        'Atencion',
        back_populates='paciente',
        lazy=True
    )

    citas = db.relationship(
        'Cita',
        back_populates='paciente',
        lazy=True
    )

    def __repr__(self):
        return f'<Paciente {self.nombre}>'

# =====================================================
# SEDES
# =====================================================

class Sede(db.Model):
    __tablename__ = 'sedes'

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    id_ubicacion_fundacion = db.Column(
        db.Integer,
        unique=True,
        nullable=True,
        index=True
    )

    codigo = db.Column(
        db.String(30),
        unique=True,
        nullable=False,
        index=True
    )

    nombre = db.Column(
        db.String(120),
        nullable=False
    )

    direccion = db.Column(
        db.String(255),
        nullable=True
    )

    activo = db.Column(
        db.Boolean,
        nullable=False,
        default=True
    )

    fecha_creacion = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow
    )

    atenciones = db.relationship(
        'Atencion',
        back_populates='sede',
        lazy=True
    )

    areas = db.relationship(
        'SedeArea',
        back_populates='sede',
        cascade='all, delete-orphan',
        lazy=True
    )

    def to_dict(self):
        return {
            'id': self.id,
            'id_ubicacion_fundacion': (
                self.id_ubicacion_fundacion
            ),
            'codigo': self.codigo,
            'nombre': self.nombre,
            'direccion': self.direccion,
            'activo': self.activo
        }

# =====================================================
# ÁREAS
# =====================================================

class Area(db.Model):
    __tablename__ = 'areas'

    id = db.Column(db.Integer, primary_key=True)

    codigo = db.Column(
        db.String(30),
        nullable=False,
        unique=True
    )

    nombre = db.Column(
        db.String(100),
        nullable=False
    )

    descripcion = db.Column(db.Text)

    genera_cola = db.Column(
        db.Boolean,
        default=True,
        nullable=False
    )

    activo = db.Column(
        db.Boolean,
        default=True,
        nullable=False
    )

    orden_visual = db.Column(
        db.Integer,
        default=0
    )

    servicios = db.relationship(
        'Servicio',
        back_populates='area',
        lazy=True
    )

    turnos = db.relationship(
        'TurnoArea',
        back_populates='area',
        lazy=True
    )

    sedes = db.relationship(
        'SedeArea',
        back_populates='area',
        cascade='all, delete-orphan',
        lazy=True
    )

    def __repr__(self):
        return f'<Area {self.codigo}>'

# =====================================================
# ÁREAS DISPONIBLES POR SEDE
# =====================================================

class SedeArea(db.Model):
    __tablename__ = 'sede_areas'

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    sede_id = db.Column(
        db.Integer,
        db.ForeignKey('sedes.id'),
        nullable=False,
        index=True
    )

    area_id = db.Column(
        db.Integer,
        db.ForeignKey('areas.id'),
        nullable=False,
        index=True
    )

    activo = db.Column(
        db.Boolean,
        nullable=False,
        default=True
    )

    orden_visual = db.Column(
        db.Integer,
        nullable=False,
        default=0
    )

    fecha_creacion = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow
    )

    sede = db.relationship(
        'Sede',
        back_populates='areas'
    )

    area = db.relationship(
        'Area',
        back_populates='sedes'
    )

    __table_args__ = (
        db.UniqueConstraint(
            'sede_id',
            'area_id',
            name='uq_sede_area'
        ),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'sede_id': self.sede_id,
            'area_id': self.area_id,

            'sede': (
                self.sede.nombre
                if self.sede
                else None
            ),

            'area': (
                self.area.nombre
                if self.area
                else None
            ),

            'codigo_area': (
                self.area.codigo
                if self.area
                else None
            ),

            'activo': self.activo,
            'orden_visual': self.orden_visual
        }

    def __repr__(self):
        return (
            f'<SedeArea '
            f'sede={self.sede_id} '
            f'area={self.area_id}>'
        )


# =====================================================
# SERVICIOS
# =====================================================

class Servicio(db.Model):
    __tablename__ = 'servicios'

    id = db.Column(db.Integer, primary_key=True)

    area_id = db.Column(
        db.Integer,
        db.ForeignKey('areas.id'),
        nullable=False
    )

    codigo = db.Column(
        db.String(50),
        nullable=False,
        unique=True
    )

    nombre = db.Column(
        db.String(150),
        nullable=False
    )

    descripcion = db.Column(db.Text)

    precio_base = db.Column(
        db.Numeric(10, 2)
    )

    requiere_pago = db.Column(
        db.Boolean,
        default=True,
        nullable=False
    )

    activo = db.Column(
        db.Boolean,
        default=True,
        nullable=False
    )

    area = db.relationship(
        'Area',
        back_populates='servicios'
    )

    def __repr__(self):
        return f'<Servicio {self.nombre}>'


# =====================================================
# DOCTORES
# =====================================================

class Doctor(db.Model):
    __tablename__ = 'doctores'

    id = db.Column(db.Integer, primary_key=True)

    nombre = db.Column(
        db.String(150),
        nullable=False
    )

    especialidad = db.Column(
        db.String(100)
    )

    consultorio = db.Column(
        db.String(50)
    )

    activo = db.Column(
        db.Boolean,
        default=True,
        nullable=False
    )

    disponible = db.Column(
        db.Boolean,
        default=True,
        nullable=False
    )

    estado = db.Column(
        db.String(30),
        default='DISPONIBLE',
        nullable=False
    )

    fecha_creacion = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    turnos_area = db.relationship(
        'TurnoArea',
        back_populates='doctor',
        lazy=True
    )

    citas = db.relationship(
        'Cita',
        back_populates='doctor',
        lazy=True
    )

    def to_dict(self):
        return {
            'id': self.id,
            'nombre': self.nombre,
            'especialidad': self.especialidad,
            'consultorio': self.consultorio,
            'activo': self.activo,
            'disponible': self.disponible,
            'estado': self.estado,
            'fecha_creacion': (
                self.fecha_creacion.isoformat()
                if self.fecha_creacion else None
            )
        }

    def __repr__(self):
        return f'<Doctor {self.nombre}>'


# =====================================================
# JORNADAS
# =====================================================

class Jornada(db.Model):
    __tablename__ = 'jornadas'

    id = db.Column(db.Integer, primary_key=True)

    nombre = db.Column(
        db.String(150),
        nullable=False
    )

    fecha = db.Column(
        db.Date,
        nullable=False
    )

    hora_inicio = db.Column(db.Time)
    hora_fin = db.Column(db.Time)

    estado = db.Column(
        db.String(30),
        default='PROGRAMADA',
        nullable=False
    )

    observaciones = db.Column(db.Text)

    fecha_creacion = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    citas = db.relationship(
        'Cita',
        back_populates='jornada',
        lazy=True
    )

    def __repr__(self):
        return f'<Jornada {self.nombre}>'


# =====================================================
# CITAS
# =====================================================

class Cita(db.Model):
    __tablename__ = 'citas'

    id = db.Column(db.Integer, primary_key=True)

    jornada_id = db.Column(
        db.Integer,
        db.ForeignKey('jornadas.id'),
        nullable=True
    )

    paciente_id = db.Column(
        db.Integer,
        db.ForeignKey('pacientes.id'),
        nullable=True
    )

    servicio_id = db.Column(
        db.Integer,
        db.ForeignKey('servicios.id'),
        nullable=False
    )

    doctor_id = db.Column(
        db.Integer,
        db.ForeignKey('doctores.id'),
        nullable=True
    )

    # Snapshot para citas de personas aún no registradas
    nombre_paciente = db.Column(
        db.String(200),
        nullable=False
    )

    fecha_cita = db.Column(
        db.Date,
        nullable=False
    )

    hora_programada = db.Column(
        db.Time
    )

    estado = db.Column(
        db.String(30),
        default='PROGRAMADA',
        nullable=False
    )

    observaciones = db.Column(db.Text)

    fecha_registro = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    jornada = db.relationship(
        'Jornada',
        back_populates='citas'
    )

    paciente = db.relationship(
        'Paciente',
        back_populates='citas'
    )

    servicio = db.relationship(
        'Servicio'
    )

    doctor = db.relationship(
        'Doctor',
        back_populates='citas'
    )

    atenciones = db.relationship(
        'Atencion',
        back_populates='cita',
        lazy=True
    )

    def __repr__(self):
        return f'<Cita {self.nombre_paciente}>'


# =====================================================
# ATENCIONES
# El "turno viajero"
# =====================================================

class Atencion(db.Model):
    __tablename__ = 'atenciones'

    id = db.Column(db.Integer, primary_key=True)

    folio = db.Column(
        db.String(30),
        nullable=False,
        unique=True,
        index=True
    )

    paciente_id = db.Column(
        db.Integer,
        db.ForeignKey('pacientes.id'),
        nullable=True
    )

    cita_id = db.Column(
        db.Integer,
        db.ForeignKey('citas.id'),
        nullable=True
    )

    sede_id = db.Column(
    db.Integer,
    db.ForeignKey('sedes.id'),
    nullable=True,
    index=True
)

    sede = db.relationship(
        'Sede',
        back_populates='atenciones'
    )

    # Snapshot del nombre del paciente
    nombre_paciente = db.Column(
        db.String(200),
        nullable=False
    )

    tipo_llegada = db.Column(
        db.String(20),
        nullable=False,
        default='SIN_CITA'
    )

    afiliado_al_llegar = db.Column(
        db.Boolean,
        default=False,
        nullable=False
    )

    servicio_inicial_id = db.Column(
        db.Integer,
        db.ForeignKey('servicios.id'),
        nullable=True
    )

    doctor_solicitado_id = db.Column(
        db.Integer,
        db.ForeignKey('doctores.id'),
        nullable=True
    )

    estado = db.Column(
        db.String(30),
        default='ACTIVA',
        nullable=False
    )

    fecha_hora_llegada = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    fecha_hora_fin = db.Column(
        db.DateTime
    )

    observaciones = db.Column(db.Text)

    creado_por = db.Column(
        db.String(100)
    )

    paciente = db.relationship(
        'Paciente',
        back_populates='atenciones'
    )

    cita = db.relationship(
        'Cita',
        back_populates='atenciones'
    )

    servicio_inicial = db.relationship(
        'Servicio',
        foreign_keys=[servicio_inicial_id]
    )

    doctor_solicitado = db.relationship(
        'Doctor',
        foreign_keys=[doctor_solicitado_id]
    )

    servicios = db.relationship(
        'AtencionServicio',
        back_populates='atencion',
        cascade='all, delete-orphan',
        lazy=True
    )

    turnos_area = db.relationship(
        'TurnoArea',
        back_populates='atencion',
        cascade='all, delete-orphan',
        lazy=True
    )

    historial = db.relationship(
        'HistorialTurno',
        back_populates='atencion',
        cascade='all, delete-orphan',
        lazy=True
    )

    pagos = db.relationship(
        'Pago',
        back_populates='atencion',
        lazy=True
    )

    def __repr__(self):
        return f'<Atencion {self.folio}>'


# =====================================================
# SERVICIOS SOLICITADOS DURANTE UNA ATENCIÓN
# =====================================================

class AtencionServicio(db.Model):
    __tablename__ = 'atencion_servicios'

    id = db.Column(db.Integer, primary_key=True)

    atencion_id = db.Column(
        db.Integer,
        db.ForeignKey('atenciones.id'),
        nullable=False
    )

    servicio_id = db.Column(
        db.Integer,
        db.ForeignKey('servicios.id'),
        nullable=False
    )

    origen = db.Column(
        db.String(50)
    )

    estado = db.Column(
        db.String(30),
        default='PENDIENTE',
        nullable=False
    )

    requiere_pago = db.Column(
        db.Boolean,
        default=True,
        nullable=False
    )

    pagado = db.Column(
        db.Boolean,
        default=False,
        nullable=False
    )

    orden = db.Column(
        db.Integer,
        default=0
    )

    fecha_creacion = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    atencion = db.relationship(
        'Atencion',
        back_populates='servicios'
    )

    servicio = db.relationship(
        'Servicio'
    )

    def __repr__(self):
        return f'<AtencionServicio {self.id}>'


# =====================================================
# TURNOS POR ÁREA
# Cada fila representa una cola real
# =====================================================

class TurnoArea(db.Model):
    __tablename__ = 'turnos_area'

    id = db.Column(db.Integer, primary_key=True)

    atencion_id = db.Column(
        db.Integer,
        db.ForeignKey('atenciones.id'),
        nullable=False,
        index=True
    )

    area_id = db.Column(
        db.Integer,
        db.ForeignKey('areas.id'),
        nullable=False,
        index=True
    )

    servicio_id = db.Column(
        db.Integer,
        db.ForeignKey('servicios.id'),
        nullable=True
    )

    doctor_id = db.Column(
        db.Integer,
        db.ForeignKey('doctores.id'),
        nullable=True
    )

    numero_turno = db.Column(
        db.String(30),
        nullable=False
    )

    tipo_prioridad = db.Column(
        db.String(30),
        default='NORMAL',
        nullable=False
    )

    estado = db.Column(
        db.String(30),
        default='ESPERA',
        nullable=False
    )

    fecha_entrada_cola = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    fecha_llamado = db.Column(db.DateTime)
    fecha_inicio = db.Column(db.DateTime)
    fecha_fin = db.Column(db.DateTime)

    veces_omitido = db.Column(
        db.Integer,
        default=0,
        nullable=False
    )

    ultima_omision = db.Column(db.DateTime)

    posicion_manual = db.Column(db.Integer)

    prioridad_manual = db.Column(
        db.Boolean,
        default=False,
        nullable=False
    )

    observaciones = db.Column(db.Text)

    atencion = db.relationship(
        'Atencion',
        back_populates='turnos_area'
    )

    area = db.relationship(
        'Area',
        back_populates='turnos'
    )

    servicio = db.relationship(
        'Servicio'
    )

    doctor = db.relationship(
        'Doctor',
        back_populates='turnos_area'
    )

    historial = db.relationship(
        'HistorialTurno',
        back_populates='turno_area',
        lazy=True
    )

    def __repr__(self):
        return f'<TurnoArea {self.numero_turno}>'


# =====================================================
# HISTORIAL / TRAZABILIDAD
# =====================================================

class HistorialTurno(db.Model):
    __tablename__ = 'historial_turnos'

    id = db.Column(db.Integer, primary_key=True)

    turno_area_id = db.Column(
        db.Integer,
        db.ForeignKey('turnos_area.id'),
        nullable=True
    )

    atencion_id = db.Column(
        db.Integer,
        db.ForeignKey('atenciones.id'),
        nullable=False,
        index=True
    )

    accion = db.Column(
        db.String(50),
        nullable=False
    )

    estado_anterior = db.Column(
        db.String(30)
    )

    estado_nuevo = db.Column(
        db.String(30)
    )

    motivo = db.Column(db.Text)

    usuario = db.Column(
        db.String(100)
    )

    fecha_hora = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    turno_area = db.relationship(
        'TurnoArea',
        back_populates='historial'
    )

    atencion = db.relationship(
        'Atencion',
        back_populates='historial'
    )

    def __repr__(self):
        return f'<HistorialTurno {self.accion}>'


# =====================================================
# PAGOS
# =====================================================

class Pago(db.Model):
    __tablename__ = 'pagos'

    id = db.Column(db.Integer, primary_key=True)

    atencion_id = db.Column(
        db.Integer,
        db.ForeignKey('atenciones.id'),
        nullable=False
    )

    total = db.Column(
        db.Numeric(10, 2),
        nullable=False,
        default=0
    )

    metodo_pago = db.Column(
        db.String(30)
    )

    estado = db.Column(
        db.String(30),
        default='PAGADO',
        nullable=False
    )

    fecha_hora = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    usuario = db.Column(
        db.String(100)
    )

    atencion = db.relationship(
        'Atencion',
        back_populates='pagos'
    )

    detalles = db.relationship(
        'PagoDetalle',
        back_populates='pago',
        cascade='all, delete-orphan',
        lazy=True
    )

    def __repr__(self):
        return f'<Pago {self.id}>'


# =====================================================
# DETALLE DE PAGOS
# =====================================================

class PagoDetalle(db.Model):
    __tablename__ = 'pago_detalle'

    id = db.Column(db.Integer, primary_key=True)

    pago_id = db.Column(
        db.Integer,
        db.ForeignKey('pagos.id'),
        nullable=False
    )

    servicio_id = db.Column(
        db.Integer,
        db.ForeignKey('servicios.id'),
        nullable=True
    )

    concepto = db.Column(
        db.String(200),
        nullable=False
    )

    cantidad = db.Column(
        db.Integer,
        default=1,
        nullable=False
    )

    precio_unitario = db.Column(
        db.Numeric(10, 2),
        nullable=False
    )

    subtotal = db.Column(
        db.Numeric(10, 2),
        nullable=False
    )

    pago = db.relationship(
        'Pago',
        back_populates='detalles'
    )

    servicio = db.relationship(
        'Servicio'
    )

    def __repr__(self):
        return f'<PagoDetalle {self.concepto}>'