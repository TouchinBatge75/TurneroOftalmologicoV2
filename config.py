# config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///turnero.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Estaciones 
    ESTACIONES = {
        1: 'Recepción',
        2: 'Trabajo Social',      # Solo para NO afiliados
        3: 'Gabinete',            # Incluye: Toma de Cálculos + Estudios
        4: 'Consulta Médica',     # Doctores
        5: 'Farmacia',            # Recetas
        6: 'Asesoría Visual',     # Lentes/armazones
        7: 'Salida'               # Final
    }
    
    # Sub-estaciones dentro de Gabinete
    SUBESTACIONES_GABINETE = {
        'TOMA_CALCULOS': 'Toma de Cálculos',
        'AGUDEZA_VISUAL': 'Agudeza Visual',
        'PRESION_INTRAOCULAR': 'Presión Intraocular',
        'QUERATOMETRIA': 'Queratometría',
        'REFRACCION': 'Refracción',
        'CALCULO_LIO': 'Cálculo de LIO'
    }