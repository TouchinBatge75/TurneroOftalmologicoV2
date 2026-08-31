import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv(
        'SECRET_KEY',
        'clave-desarrollo-temporal'
    )

    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    ESTACIONES = {
        1: 'Recepción',
        2: 'Trabajo Social',
        3: 'Gabinete',
        4: 'Consulta Médica',
        5: 'Farmacia',
        6: 'Asesoría Visual',
        7: 'Salida'
    }

    SUBESTACIONES_GABINETE = {
        'TOMA_CALCULOS': 'Toma de Cálculos',
        'AGUDEZA_VISUAL': 'Agudeza Visual',
        'PRESION_INTRAOCULAR': 'Presión Intraocular',
        'QUERATOMETRIA': 'Queratometría',
        'REFRACCION': 'Refracción',
        'CALCULO_LIO': 'Cálculo de LIO'
    }