"""Instalador puntual del selector de médico para Recepción V5 (Turnero).

Ejecutar desde la raíz del proyecto Turnero:
    python instalar_selector_medico.py

NO altera la base de datos. Crea respaldos de ambos archivos antes de escribir.
Valida anclas de código y se detiene si la versión local no coincide.
"""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import sys
import tempfile
from datetime import datetime

MARCA_BACKEND = "# RECEPCION_MEDICOS_V1: catálogo y propagación de médico solicitado"
MARCA_FRONT = "<!-- RECEPCION_MEDICOS_V1: selector de médico en ingreso -->"


def reemplazar_unico(contenido: str, antes: str, despues: str, nombre: str) -> str:
    apariciones = contenido.count(antes)
    if apariciones != 1:
        raise RuntimeError(f"No se pudo aplicar '{nombre}': esperaba 1 coincidencia, encontré {apariciones}. No se modificará ningún archivo.")
    return contenido.replace(antes, despues, 1)


def parchear_backend(contenido: str) -> str:
    if MARCA_BACKEND in contenido:
        return contenido

    contenido = reemplazar_unico(
        contenido,
        "    Doctor,\n    Paciente,",
        "    Doctor,\n    Consultorio,\n    AsignacionDoctor,\n    Paciente,",
        "importar catálogo de médicos y consultorios",
    )

    contenido = reemplazar_unico(
        contenido,
        "    'buscar_paciente_control': ('area_caja', 'recepcion_ver'),",
        "    'buscar_paciente_control': ('area_caja', 'recepcion_ver'),\n"
        "    'doctores_recepcion': ('area_caja', 'recepcion_ver'),",
        "política de acceso al selector",
    )

    helpers = '''# RECEPCION_MEDICOS_V1: catálogo y propagación de médico solicitado

def _filas_doctores_habilitados(sede_id, doctor_id=None, area_id=None):
    """Médicos activos con consultorio y asignación activa en la sede.

    La validación es por sede y área, NO por fecha/hora: aún no está
    confirmada la convención de dia_semana de asignaciones_doctores.
    """
    consulta = (
        db.session.query(Doctor, Consultorio)
        .join(AsignacionDoctor, AsignacionDoctor.doctor_id == Doctor.id)
        .join(Consultorio, Consultorio.id == AsignacionDoctor.consultorio_id)
        .join(Area, Area.id == Consultorio.area_id)
        .join(SedeArea, and_(
            SedeArea.sede_id == Consultorio.sede_id,
            SedeArea.area_id == Consultorio.area_id,
        ))
        .filter(
            Consultorio.sede_id == sede_id,
            Doctor.activo.is_(True),
            AsignacionDoctor.activo.is_(True),
            Consultorio.activo.is_(True),
            Area.activo.is_(True),
            SedeArea.activo.is_(True),
        )
    )
    if doctor_id is not None:
        consulta = consulta.filter(Doctor.id == doctor_id)
    if area_id is not None:
        consulta = consulta.filter(Consultorio.area_id == area_id)
    return consulta.order_by(Doctor.nombre.asc(), Consultorio.codigo.asc()).all()


def _doctor_habilitado_en_sede(doctor_id, sede_id, area_id=None):
    filas = _filas_doctores_habilitados(sede_id, doctor_id, area_id)
    return filas[0][0] if filas else None


def _doctor_solicitado_para_destino(atencion, area_destino):
    """Asigna al médico solo al entrar al área donde tiene consultorio.

    En CAJA y otras áreas NO se escribe doctor_id en el turno.
    La atención conserva el médico solicitado durante el recorrido.
    """
    solicitado_id = getattr(atencion, 'doctor_solicitado_id', None)
    if not solicitado_id or area_destino is None:
        return None

    # Un área con consultorios es el destino médico. El propio catálogo
    # define el área (no se inventan destinos ni se salta Caja).
    tiene_consultorio = (
        db.session.query(Consultorio.id)
        .join(SedeArea, and_(
            SedeArea.sede_id == Consultorio.sede_id,
            SedeArea.area_id == Consultorio.area_id,
        ))
        .filter(
            Consultorio.sede_id == atencion.sede_id,
            Consultorio.area_id == area_destino.id,
            Consultorio.activo.is_(True),
            SedeArea.activo.is_(True),
        )
        .first()
    )
    if not tiene_consultorio:
        return None

    doctor = _doctor_habilitado_en_sede(
        solicitado_id, atencion.sede_id, area_destino.id
    )
    if doctor is None:
        raise ValueError(
            'El médico solicitado ya no tiene asignación activa en el área '
            'de Consulta Médica. Corrige la asignación antes de avanzar.'
        )
    return doctor.id


@bp.get('/recepcion/doctores')
def doctores_recepcion():
    """Catálogo acotado a la sede de Recepción/Caja autenticada."""
    filas = _filas_doctores_habilitados(current_user.sede_id)
    resultado = {}
    for doctor, consultorio in filas:
        item = resultado.setdefault(doctor.id, {
            'id': doctor.id,
            'nombre': doctor.nombre,
            'especialidad': doctor.especialidad,
            'consultorios': [],
        })
        if not any(c['id'] == consultorio.id for c in item['consultorios']):
            item['consultorios'].append({
                'id': consultorio.id,
                'codigo': consultorio.codigo,
                'nombre': consultorio.nombre,
                'area_id': consultorio.area_id,
            })
    return jsonify(success=True, doctores=list(resultado.values()),
                   total=len(resultado))


'''
    contenido = reemplazar_unico(
        contenido,
        "def mover_turno_a_area(\n",
        helpers + "def mover_turno_a_area(\n",
        "catálogo restringido y propagación",
    )

    contenido = reemplazar_unico(
        contenido,
        "    # =============================================\n"
        "    # 1. DATOS DEL TURNO ACTUAL\n"
        "    # =============================================\n\n"
        "    ahora = datetime.utcnow()",
        "    # Mantener el médico elegido al llegar a su consultorio, sin alterar\n"
        "    # la cola de CAJA ni los recorridos previamente publicados.\n"
        "    if doctor_id is None and turno_actual.atencion is not None:\n"
        "        doctor_id = _doctor_solicitado_para_destino(\n"
        "            turno_actual.atencion, area_destino\n"
        "        )\n\n"
        "    # =============================================\n"
        "    # 1. DATOS DEL TURNO ACTUAL\n"
        "    # =============================================\n\n"
        "    ahora = datetime.utcnow()",
        "propagar al mover entre áreas",
    )

    contenido = reemplazar_unico(
        contenido,
        "            if not doctor:\n"
        "                return jsonify({\n"
        "                    'success': False,\n"
        "                    'error': (\n"
        "                        'Doctor no encontrado'\n"
        "                    )\n"
        "                }), 404\n\n"
        "        # =================================================\n"
        "        # VALIDAR CITA",
        "            if not doctor:\n"
        "                return jsonify({\n"
        "                    'success': False,\n"
        "                    'error': (\n"
        "                        'Doctor no encontrado'\n"
        "                    )\n"
        "                }), 404\n\n"
        "            if not _doctor_habilitado_en_sede(doctor.id, sede.id):\n"
        "                return jsonify({\n"
        "                    'success': False,\n"
        "                    'error': (\n"
        "                        'El médico no está activo o no tiene una '\n"
        "                        'asignación de consultorio activa en esta sede'\n"
        "                    )\n"
        "                }), 409\n\n"
        "        # =================================================\n"
        "        # VALIDAR CITA",
        "validar médico al registrar atención",
    )

    # Este ancla aparece únicamente en registrar_control: se busca en el segmento
    # posterior a la definición de la función, no en otras APIs.
    inicio = contenido.index('def registrar_control():')
    fin = contenido.index("# =====================================================\n# DOCTORES", inicio)
    segmento = contenido[inicio:fin]
    segmento = reemplazar_unico(
        segmento,
        "            doctor_id=None,\n\n            numero_turno=(",
        "            doctor_id=_doctor_solicitado_para_destino(\n"
        "                atencion, area_destino\n"
        "            ),\n\n            numero_turno=(",
        "asignar médico si destino inicial ya es consulta",
    )
    contenido = contenido[:inicio] + segmento + contenido[fin:]
    return contenido


def parchear_frontend(contenido: str) -> str:
    if MARCA_FRONT in contenido:
        return contenido

    campo = '''              <!-- RECEPCION_MEDICOS_V1: selector de médico en ingreso -->
              <div class="form-field span2">
                <label for="fDoctor">Médico solicitado para Consulta Médica</label>
                <select class="input" id="fDoctor" aria-describedby="doctorAyuda" disabled>
                  <option value="">Cargando médicos de la sede…</option>
                </select>
                <div class="sub" id="doctorAyuda" style="margin-top:6px">Selecciona al médico para servicios de Consulta Médica. No cambia el destino inicial ni omite Caja.</div>
              </div>
'''
    contenido = reemplazar_unico(
        contenido,
        '              <div class="form-field span2"><label for="fObservaciones">',
        campo + '              <div class="form-field span2"><label for="fObservaciones">',
        'campo de selección de doctor',
    )

    contenido = reemplazar_unico(
        contenido,
        "        option.value=String(servicio.servicio_id);\n"
        "        option.textContent=`${servicio.servicio} — ${servicio.area||'Área por definir'}`;",
        "        option.value=String(servicio.servicio_id);\n"
        "        option.dataset.area=String(servicio.area||'');\n"
        "        option.textContent=`${servicio.servicio} — ${servicio.area||'Área por definir'}`;",
        'identificar servicios médicos en el frontend',
    )

    funciones = '''  // RECEPCION_MEDICOS_V1: los médicos vienen de la sede autenticada.
  async function loadDoctoresRegistro(){
    const select=$('#fDoctor');
    select.disabled=true;
    select.replaceChildren();
    select.add(new Option('Cargando médicos de esta sede…',''));
    try{
      const data=state.demo?{doctores:[{
        id:1,nombre:'Dr. Prueba Retorno',especialidad:'Oftalmología',
        consultorios:[{codigo:'CONS-PRUEBA-01'}]
      }]}:await api('/api/recepcion/doctores');
      const doctores=Array.isArray(data.doctores)?data.doctores:[];
      select.replaceChildren();
      select.add(new Option('Sin médico asignado / No aplica',''));
      for(const medico of doctores){
        const consultorios=(medico.consultorios||[]).map(c=>c.codigo).filter(Boolean).join(', ');
        const descripcion=[medico.nombre,medico.especialidad,consultorios].filter(Boolean).join(' · ');
        select.add(new Option(descripcion,String(medico.id)));
      }
      select.disabled=doctores.length===0;
      $('#doctorAyuda').textContent=doctores.length
        ? 'Para una consulta médica, elige el médico que atenderá. No cambia el destino inicial ni omite Caja.'
        : 'No hay médicos activos con consultorio asignado en esta sede.';
    }catch(err){
      select.replaceChildren();
      select.add(new Option('No fue posible consultar médicos',''));
      $('#doctorAyuda').textContent='Error al cargar médicos: '+err.message;
      showToast('No se pudieron cargar los médicos: '+err.message);
    }
  }

  function servicioMedicoSeleccionado(){
    return [...$('#fServicios').selectedOptions].some(option=>{
      const area=String(option.dataset.area||'')
        .normalize('NFD').replace(/[\\u0300-\\u036f]/g,'').toUpperCase();
      return area.includes('CONSULTA')||area.includes('CONSULTORIO')||area.includes('MEDICINA');
    });
  }
'''

    contenido = reemplazar_unico(
        contenido,
        "  function navigate(target){",
        funciones + "  function navigate(target){",
        'carga dinámica de médicos por sede',
    )
    contenido = reemplazar_unico(
        contenido,
        "if(target==='registro')loadServiciosRegistro();",
        "if(target==='registro'){loadServiciosRegistro();loadDoctoresRegistro();}",
        'cargar médicos al entrar al registro',
    )
    inicio = contenido.index("  $('#registerForm').addEventListener('submit',async e=>{")
    fin = contenido.index('  async function boot(){', inicio)
    form = contenido[inicio:fin]
    form = reemplazar_unico(
        form,
        "    if(payload.servicios_ids.length===0){showToast('Selecciona al menos un servicio para registrar la atención.');return;}",
        "    if(payload.servicios_ids.length===0){showToast('Selecciona al menos un servicio para registrar la atención.');return;}\n"
        "    const doctorId=Number($('#fDoctor').value)||null;\n"
        "    if(servicioMedicoSeleccionado()&&!doctorId){\n"
        "      showToast('Selecciona un médico para el servicio de Consulta Médica.');\n"
        "      $('#fDoctor').focus();return;\n"
        "    }\n"
        "    if(doctorId)payload.doctor_id=doctorId;",
        'validar y enviar doctor_id al backend',
    )
    contenido = contenido[:inicio]+form+contenido[fin:]
    return contenido


def escribir_atomico(ruta: Path, contenido: str) -> None:
    fd, temporal = tempfile.mkstemp(dir=str(ruta.parent), prefix='.tmp_turnero_', suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as f:
            f.write(contenido)
        os.replace(temporal, ruta)
    finally:
        if os.path.exists(temporal):
            os.unlink(temporal)


def instalar(raiz: Path) -> list[str]:
    rutas = [raiz / 'app' / 'routes.py', raiz / 'templates' / 'recepcion.html']
    faltantes = [str(p) for p in rutas if not p.is_file()]
    if faltantes:
        raise RuntimeError('No se encontraron archivos del proyecto: ' + ', '.join(faltantes))

    textos = [p.read_text(encoding='utf-8-sig') for p in rutas]
    # Preparar ambos archivos antes de guardar cualquiera.
    nuevos = [parchear_backend(textos[0]), parchear_frontend(textos[1])]

    cambios = [i for i,(anterior,nuevo) in enumerate(zip(textos,nuevos)) if anterior!=nuevo]
    if not cambios:
        return ['El selector ya está instalado; no se modificó ningún archivo.']

    marca = datetime.now().strftime('%Y%m%d_%H%M%S')
    informes = []
    for i in cambios:
        backup = rutas[i].with_name(rutas[i].name + f'.antes_selector_medico_{marca}.bak')
        shutil.copy2(rutas[i], backup)
        informes.append(f'Respaldo: {backup}')
    for i in cambios:
        escribir_atomico(rutas[i], nuevos[i])
        informes.append(f'Actualizado: {rutas[i]}')
    return informes


if __name__ == '__main__':
    raiz = Path(__file__).resolve().parent
    try:
        for linea in instalar(raiz):
            print(linea)
        print('Listo. Ejecuta: python -m compileall -q app')
        print('Reinicia Flask y entra en Recepción > Registrar ingreso.')
    except Exception as e:
        print(f'ERROR: {e}', file=sys.stderr)
        sys.exit(1)
