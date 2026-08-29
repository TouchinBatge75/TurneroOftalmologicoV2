# app/models.py
from datetime import datetime
from app import db

class Doctor(db.Model):
    __tablename__ = 'doctores'
    
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    especialidad = db.Column(db.String(100))
    
    # Estado CORREGIDO (esto SÍ funcionará)
    activo = db.Column(db.Boolean, default=True)
    disponible = db.Column(db.Boolean, default=True)
    estado = db.Column(db.String(30), default='DISPONIBLE')
    
    # Asignaciones
    consultorio = db.Column(db.String(50))
    enfermero_asignado = db.Column(db.String(100))
    
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'nombre': self.nombre,
            'especialidad': self.especialidad,
            'activo': self.activo,
            'disponible': self.disponible,
            'estado': self.estado,
            'consultorio': self.consultorio,
            'enfermero_asignado': self.enfermero_asignado,
            'fecha_creacion': self.fecha_creacion.isoformat() if self.fecha_creacion else None
        }
    
    def __repr__(self):
        return f'<Doctor {self.nombre}>'

class Turno(db.Model):
    __tablename__ = 'turnos'
    
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(20), nullable=False, unique=True)
    paciente_nombre = db.Column(db.String(100), nullable=False)
    paciente_edad = db.Column(db.Integer, nullable=False)
    
    # Tipo y estado
    tipo = db.Column(db.String(20), default='SIN_CITA')
    estado = db.Column(db.String(30), default='PENDIENTE')
    estacion_actual = db.Column(db.Integer, default=1)
    
    # Tiempos
    hora_llegada = db.Column(db.DateTime, default=datetime.utcnow)
    hora_atencion = db.Column(db.DateTime)
    hora_salida = db.Column(db.DateTime)
    
    # Información adicional
    notas = db.Column(db.Text)
    
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'numero': self.numero,
            'paciente_nombre': self.paciente_nombre,
            'paciente_edad': self.paciente_edad,
            'tipo': self.tipo,
            'estado': self.estado,
            'estacion_actual': self.estacion_actual,
            'hora_llegada': self.hora_llegada.isoformat() if self.hora_llegada else None,
            'notas': self.notas,
            'fecha_creacion': self.fecha_creacion.isoformat() if self.fecha_creacion else None
        }
    
    def __repr__(self):
        return f'<Turno {self.numero}>'