# -*- coding: utf-8 -*-
'Repara instalación parcial de Recepción V6 sin reemplazar módulos enteros.'
from pathlib import Path
from datetime import datetime
import sys

BACKEND_BLOCK = "\n# RECEPCION_OPERACION_V6: consulta de opciones, sin modificar turnos.\n@bp.route('/recepcion/turnos/<int:turno_id>/opciones-avance', methods=['GET'])\ndef opciones_avance_recepcion(turno_id):\n    turno = db.session.get(TurnoArea, turno_id)\n    if turno is None or turno.atencion is None:\n        return jsonify({'success': False, 'error': 'Turno no encontrado'}), 404\n\n    if not turno.area or turno.area.codigo != 'CAJA':\n        return jsonify({'success': False, 'error': 'El turno no corresponde a Caja'}), 409\n\n    if turno.estado != 'EN_ATENCION':\n        return jsonify({\n            'success': False,\n            'error': 'Primero debes llamar e iniciar la atención en Caja'\n        }), 409\n\n    atencion = turno.atencion\n    if atencion.estado != 'ACTIVA':\n        return jsonify({'success': False, 'error': 'La atención no está activa'}), 409\n\n    # Solo se presentan opciones del motor. El POST existente vuelve a\n    # validar estado, sede, permisos, pagos y requisitos del recorrido.\n    opciones = []\n    solicitudes = (\n        SolicitudArea.query\n        .filter(\n            SolicitudArea.atencion_id == atencion.id,\n            SolicitudArea.estado == 'PENDIENTE',\n            SolicitudArea.fecha_inicio.isnot(None)\n        )\n        .order_by(SolicitudArea.id.asc())\n        .all()\n    )\n    if solicitudes:\n        for solicitud in solicitudes:\n            recorrido_info = resolver_recorrido_area_sede(\n                atencion.sede_id, solicitud.area_destino_id\n            )\n            if not recorrido_info.get('valido'):\n                continue\n            ids = [paso['area_id'] for paso in recorrido_info['recorrido']]\n            if turno.area_id not in ids[:-1]:\n                continue\n            siguiente = db.session.get(Area, ids[ids.index(turno.area_id) + 1])\n            if siguiente:\n                opciones.append({\n                    'tipo': 'SOLICITUD',\n                    'id': solicitud.id,\n                    'etiqueta': 'Continuar solicitud #' + str(solicitud.id)\n                                + ' hacia ' + siguiente.nombre,\n                    'destino': siguiente.nombre,\n                    'requiere_confirmar_requisito': True\n                })\n    else:\n        reglas = (\n            ReglaTransicion.query\n            .filter(\n                ReglaTransicion.sede_id == atencion.sede_id,\n                ReglaTransicion.area_origen_id == turno.area_id,\n                ReglaTransicion.activo.is_(True)\n            )\n            .order_by(ReglaTransicion.prioridad.desc(), ReglaTransicion.id.asc())\n            .all()\n        )\n        vistos = set()\n        for regla in reglas:\n            if regla.evento in vistos:\n                continue\n            vistos.add(regla.evento)\n            transicion = resolver_transicion(\n                atencion.sede_id, turno.area_id, regla.evento\n            )\n            if not transicion.get('success'):\n                continue\n            destino = transicion['area_destino']\n            # El endpoint de transición no admite destinos con requisitos previos.\n            camino = resolver_recorrido_area_sede(atencion.sede_id, destino.id)\n            if not camino.get('valido') or len(camino['recorrido']) > 1:\n                continue\n            opciones.append({\n                'tipo': 'TRANSICION',\n                'evento': regla.evento,\n                'etiqueta': regla.evento.replace('_', ' ').capitalize()\n                            + ' → ' + destino.nombre,\n                'destino': destino.nombre,\n                'requiere_confirmar_requisito': False\n            })\n\n    return jsonify({\n        'success': True,\n        'turno': {'id': turno.id, 'numero': turno.numero_turno, 'estado': turno.estado},\n        'opciones': opciones,\n        'mensaje': ('Selecciona el siguiente paso autorizado.' if opciones\n                    else 'No existe un avance directo habilitado por el motor. '\n                         'Revisa servicios, solicitudes y recorridos en Seguimiento.')\n    })\n\n"

def main():
    root=Path(__file__).resolve().parent
    routes=root/'app'/'routes.py'
    html=root/'templates'/'recepcion.html'
    if not routes.is_file() or not html.is_file():
        raise RuntimeError('Coloca el script en la raíz de Turnero.')
    r=routes.read_text(encoding='utf-8-sig')
    h=html.read_text(encoding='utf-8-sig')
    if 'RECEPCION_OPERACION_V6' not in h:
        raise RuntimeError('El HTML no tiene la V6; este reparador es solo para la instalación parcial detectada.')
    if 'def doctores_recepcion():' not in r:
        raise RuntimeError('No se encontró el catálogo médico V1 en routes.py.')
    if 'RECEPCION_OPERACION_V6' in r and 'def opciones_avance_recepcion(' not in r:
        raise RuntimeError('Backend V6 inconsistente. No se modificó ningún archivo.')
    changes=[]
    if 'def opciones_avance_recepcion(' not in r:
        policy="    'caja_turnos': ('area_query_caja', 'turnos_ver'),"
        anchor="@bp.route('/caja/turnos', methods=['GET'])"
        if r.count(policy)!=1 or r.count(anchor)!=1:
            raise RuntimeError('No se encontraron las anclas exactas del backend; no se realizó ningún cambio.')
        r=r.replace(policy,policy+"\n    'opciones_avance_recepcion': ('turno', 'turnos_ver'),",1)
        r=r.replace(anchor,BACKEND_BLOCK+anchor,1)
        changes.append('app/routes.py: endpoint opciones-avance y política')
    else:
        if "'opciones_avance_recepcion': ('turno', 'turnos_ver')" not in r:
            raise RuntimeError('La ruta ya existe pero falta su política de permisos: requiere revisión manual.')

    # Seguridad: la confirmación del requisito debe ser una acción EXPLÍCITA.
    if 'id="avanceRequisito"' not in h:
        key='    <div class="form-actions">\n      <button type="button" class="btn" id="avanceCancel">'
        if h.count(key)!=1:
            raise RuntimeError('No se encontró la ubicación del control de requisito en el HTML.')
        checkbox='''    <label class="avance-help" style="display:flex;gap:9px;align-items:flex-start">
      <input id="avanceRequisito" type="checkbox" style="margin-top:4px">
      Confirmo que he verificado los requisitos necesarios de esta solicitud antes de avanzar.
    </label>
'''
        h=h.replace(key,checkbox+key,1)
        changes.append('templates/recepcion.html: confirmación explícita de requisitos')
    if '{requisito_confirmado:true}' in h:
        h=h.replace('{requisito_confirmado:true}',"{requisito_confirmado:$('#avanceRequisito').checked}",1)
        changes.append('templates/recepcion.html: elimina confirmación automática')
    if "if(!confirm(`¿Confirmar el avance del turno" in h and "if(opcion.tipo==='SOLICITUD' && !$('#avanceRequisito').checked)" not in h:
        key='    const turnoId=avanceTurnoId;'
        if h.count(key)!=1: raise RuntimeError('No se encontró el manejador de confirmación.')
        h=h.replace(key,"    if(opcion.tipo==='SOLICITUD' && !$('#avanceRequisito').checked){showToast('Debes comprobar y confirmar los requisitos de la solicitud.');return;}\n"+key,1)
        changes.append('templates/recepcion.html: validación de requisito obligatorio')
    if "avanceTurnoId=Number(turno.id);" in h and "$('#avanceRequisito').checked=false;" not in h:
        h=h.replace('    avanceTurnoId=Number(turno.id);',"    $('#avanceRequisito').checked=false;\n    avanceTurnoId=Number(turno.id);",1)
        changes.append('templates/recepcion.html: reiniciar confirmación al abrir')
    # Nunca habilitar el botón para el placeholder sin opción seleccionada.
    old="$('#avanceConfirm').disabled= !avanceOpciones[Number($('#avanceOpcion').value)];"
    new="$('#avanceConfirm').disabled= $('#avanceOpcion').value==='' || !avanceOpciones[Number($('#avanceOpcion').value)];"
    if old in h:
        h=h.replace(old,new,1)
        changes.append('templates/recepcion.html: validación selector de opción')
    compile(r,str(routes),'exec')
    if not changes:
        print('La reparación ya está aplicada. No se modificó ningún archivo.')
        return
    stamp=datetime.now().strftime('%Y%m%d_%H%M%S')
    files=[(routes,r),(html,h)]
    originals=[]
    try:
        for path,updated in files:
            raw=path.read_bytes()
            if updated==path.read_text(encoding='utf-8-sig'): continue
            backup=path.with_name(path.name+f'.antes_reparar_v6_{stamp}.bak')
            backup.write_bytes(raw)
            originals.append((path,raw,backup))
            path.write_text(updated,encoding='utf-8')
    except Exception:
        for path,raw,_ in originals: path.write_bytes(raw)
        raise
    print('Reparación aplicada:')
    for c in changes: print(' -',c)
    for path,_,backup in originals: print(' Respaldo:',backup)
    print('Comprueba: python -m compileall -q app')
    print('Comprueba: python -m flask routes | Select-String opciones_avance_recepcion')

if __name__=='__main__':
    try: main()
    except Exception as exc:
        print('ERROR:',exc,file=sys.stderr)
        sys.exit(1)
