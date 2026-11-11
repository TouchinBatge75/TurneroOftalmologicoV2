# -*- coding: utf-8 -*-
"""Turnero V6: parche de Recepcion/Caja sobre el selector de medicos V1.
No altera SQL ni reemplaza rutas. Realiza respaldos y aplica anclas exactas.
"""
from pathlib import Path
from datetime import datetime
import sys

MARK = 'RECEPCION_OPERACION_V6'

def replace_once(text, old, new, label):
    n=text.count(old)
    if n!=1: raise RuntimeError(f'{label}: se esperaban 1 coincidencia, encontradas {n}. No se cambió nada.')
    return text.replace(old,new,1)

def main():
    root=Path(__file__).resolve().parent
    routes=root/'app'/'routes.py'
    html=root/'templates'/'recepcion.html'
    if not routes.is_file() or not html.is_file():
        raise RuntimeError('Coloca este instalador en la raiz del proyecto Turnero.')
    original_routes=routes.read_text(encoding='utf-8-sig')
    original_html=html.read_text(encoding='utf-8-sig')
    if MARK in original_routes and MARK in original_html:
        print('Recepcion V6 ya instalada. No se modificaron archivos.')
        return
    if MARK in original_routes or MARK in original_html:
        raise RuntimeError('Instalación V6 parcial detectada. Revisa respaldos antes de repetir.')
    if 'RECEPCION_MEDICOS_V1' not in original_html or 'def doctores_recepcion():' not in original_routes:
        raise RuntimeError('Se requiere primero el selector de medicos V1 instalado.')

    # Backend: política de autorización + GET solo lectura del motor.
    pol="    'caja_turnos': ('area_query_caja', 'turnos_ver'),"
    r=replace_once(original_routes,pol,pol+"\n    'opciones_avance_recepcion': ('turno', 'turnos_ver'),",'politica')
    anchor="@bp.route('/caja/turnos', methods=['GET'])"
    r=replace_once(r,anchor,BACKEND_BLOCK+anchor,'endpoint de opciones')

    # Frontend: conservamos todo el HTML de usuario; insertamos solamente
    # estilos, ventana de elección, botones por estado y manejadores.
    h=replace_once(original_html,'</style>',CSS+'</style>','CSS')
    h=replace_once(h,'<div id="toast" class="toast hidden" role="status"></div>',MODAL+'<div id="toast" class="toast hidden" role="status"></div>','modal')
    h=replace_once(h,OLD_CELL,NEW_CELL,'acciones tabla')
    h=replace_once(h,"  $('#refreshBtn').addEventListener('click',()=>{refresh();",JS+"  $('#refreshBtn').addEventListener('click',()=>{refresh();",'manejadores')

    # Verificar sintaxis Python antes de escribir.
    compile(r,str(routes),'exec')
    marca=datetime.now().strftime('%Y%m%d_%H%M%S')
    backups=[]
    try:
        for src in (routes,html):
            dst=src.with_name(src.name+f'.antes_v6_{marca}.bak')
            dst.write_bytes(src.read_bytes())
            backups.append((src,dst))
        routes.write_text(r,encoding='utf-8')
        html.write_text(h,encoding='utf-8')
    except Exception:
        for src,dst in backups:
            src.write_bytes(dst.read_bytes())
        raise
    print('Instalada Recepcion V6 con respaldos:')
    for src,dst in backups: print(' ',src,'->',dst.name)
    print('Ejecuta: python -m compileall -q app')
    print('Reinicia Flask y entra a /recepcion > Mesa operativa.')

BACKEND_BLOCK = "\n# RECEPCION_OPERACION_V6: consulta de opciones, sin modificar turnos.\n@bp.route('/recepcion/turnos/<int:turno_id>/opciones-avance', methods=['GET'])\ndef opciones_avance_recepcion(turno_id):\n    turno = db.session.get(TurnoArea, turno_id)\n    if turno is None or turno.atencion is None:\n        return jsonify({'success': False, 'error': 'Turno no encontrado'}), 404\n\n    if not turno.area or turno.area.codigo != 'CAJA':\n        return jsonify({'success': False, 'error': 'El turno no corresponde a Caja'}), 409\n\n    if turno.estado != 'EN_ATENCION':\n        return jsonify({\n            'success': False,\n            'error': 'Primero debes llamar e iniciar la atención en Caja'\n        }), 409\n\n    atencion = turno.atencion\n    if atencion.estado != 'ACTIVA':\n        return jsonify({'success': False, 'error': 'La atención no está activa'}), 409\n\n    # Solo se presentan opciones del motor. El POST existente vuelve a\n    # validar estado, sede, permisos, pagos y requisitos del recorrido.\n    opciones = []\n    solicitudes = (\n        SolicitudArea.query\n        .filter(\n            SolicitudArea.atencion_id == atencion.id,\n            SolicitudArea.estado == 'PENDIENTE',\n            SolicitudArea.fecha_inicio.isnot(None)\n        )\n        .order_by(SolicitudArea.id.asc())\n        .all()\n    )\n    if solicitudes:\n        for solicitud in solicitudes:\n            recorrido_info = resolver_recorrido_area_sede(\n                atencion.sede_id, solicitud.area_destino_id\n            )\n            if not recorrido_info.get('valido'):\n                continue\n            ids = [paso['area_id'] for paso in recorrido_info['recorrido']]\n            if turno.area_id not in ids[:-1]:\n                continue\n            siguiente = db.session.get(Area, ids[ids.index(turno.area_id) + 1])\n            if siguiente:\n                opciones.append({\n                    'tipo': 'SOLICITUD',\n                    'id': solicitud.id,\n                    'etiqueta': 'Continuar solicitud #' + str(solicitud.id)\n                                + ' hacia ' + siguiente.nombre,\n                    'destino': siguiente.nombre,\n                    'requiere_confirmar_requisito': True\n                })\n    else:\n        reglas = (\n            ReglaTransicion.query\n            .filter(\n                ReglaTransicion.sede_id == atencion.sede_id,\n                ReglaTransicion.area_origen_id == turno.area_id,\n                ReglaTransicion.activo.is_(True)\n            )\n            .order_by(ReglaTransicion.prioridad.desc(), ReglaTransicion.id.asc())\n            .all()\n        )\n        vistos = set()\n        for regla in reglas:\n            if regla.evento in vistos:\n                continue\n            vistos.add(regla.evento)\n            transicion = resolver_transicion(\n                atencion.sede_id, turno.area_id, regla.evento\n            )\n            if not transicion.get('success'):\n                continue\n            destino = transicion['area_destino']\n            # El endpoint de transición no admite destinos con requisitos previos.\n            camino = resolver_recorrido_area_sede(atencion.sede_id, destino.id)\n            if not camino.get('valido') or len(camino['recorrido']) > 1:\n                continue\n            opciones.append({\n                'tipo': 'TRANSICION',\n                'evento': regla.evento,\n                'etiqueta': regla.evento.replace('_', ' ').capitalize()\n                            + ' → ' + destino.nombre,\n                'destino': destino.nombre,\n                'requiere_confirmar_requisito': False\n            })\n\n    return jsonify({\n        'success': True,\n        'turno': {'id': turno.id, 'numero': turno.numero_turno, 'estado': turno.estado},\n        'opciones': opciones,\n        'mensaje': ('Selecciona el siguiente paso autorizado.' if opciones\n                    else 'No existe un avance directo habilitado por el motor. '\n                         'Revisa servicios, solicitudes y recorridos en Seguimiento.')\n    })\n\n"
CSS = '\n/* RECEPCION_OPERACION_V6 */\n.queue-actions{display:flex;flex-wrap:wrap;gap:6px;min-width:215px}\n.queue-actions .tiny-action{padding:6px 9px}\n.queue-actions .next-action{background:var(--accentlight);border-color:var(--accent);color:var(--accentdark)}\n.queue-actions button:disabled{opacity:.5}\n.avance-help{font-size:11px;color:var(--ink2);margin:10px 0 14px;line-height:1.7}\n'
MODAL = '\n<!-- RECEPCION_OPERACION_V6: acciones sujetas a permisos y al motor de recorridos -->\n<div id="avanceBackdrop" class="modal-backdrop hidden" role="presentation">\n  <section class="modal" role="dialog" aria-modal="true" aria-labelledby="avanceTitle">\n    <div class="modal-header">\n      <div><span class="kicker">Caja · Motor de recorridos</span><h2 id="avanceTitle">Continuar recorrido</h2></div>\n      <button type="button" class="close" id="avanceClose">Cerrar ×</button>\n    </div>\n    <div class="avance-help" id="avanceInfo">Consultando opciones...</div>\n    <div class="form-field">\n      <label for="avanceOpcion">Paso autorizado</label>\n      <select class="input" id="avanceOpcion" disabled><option value="">Consultando...</option></select>\n    </div>\n    <div class="form-actions">\n      <button type="button" class="btn" id="avanceCancel">Cancelar</button>\n      <button type="button" class="btn primary" id="avanceConfirm" disabled>Confirmar avance</button>\n    </div>\n  </section>\n</div>\n'
OLD_CELL = '<td><button class="tiny-action" data-detail-turno="${Number(t.id)}">Detalles</button></td>'
NEW_CELL = '<td><div class="queue-actions">\n          ${t.estado===\'ESPERA\'?`<button class="tiny-action" data-caja-accion="llamar" data-id="${Number(t.id)}">Llamar</button>`:\'\'}\n          ${t.estado===\'LLAMADO\'?`<button class="tiny-action" data-caja-accion="iniciar" data-id="${Number(t.id)}">Iniciar</button>`:\'\'}\n          ${t.estado===\'EN_ATENCION\'?`<button class="tiny-action next-action" data-caja-accion="avanzar" data-id="${Number(t.id)}">Continuar recorrido</button>`:\'\'}\n          <button class="tiny-action" data-detail-turno="${Number(t.id)}">Detalles</button>\n        </div></td>'
JS = "\n  // RECEPCION_OPERACION_V6: no calcula ni inventa destinos en el navegador.\n  let avanceTurnoId=null;\n  let avanceOpciones=[];\n  let accionCajaOcupada=false;\n  function cerrarAvance(){\n    avanceTurnoId=null;avanceOpciones=[];\n    $('#avanceBackdrop').classList.add('hidden');\n    $('#avanceOpcion').replaceChildren();\n    $('#avanceConfirm').disabled=true;\n  }\n  $('#avanceClose').addEventListener('click',cerrarAvance);\n  $('#avanceCancel').addEventListener('click',cerrarAvance);\n  $('#avanceBackdrop').addEventListener('click',e=>{\n    if(e.target.id==='avanceBackdrop')cerrarAvance();\n  });\n  document.addEventListener('keydown',e=>{if(e.key==='Escape')cerrarAvance();});\n  $('#avanceOpcion').addEventListener('change',()=>{\n    $('#avanceConfirm').disabled= !avanceOpciones[Number($('#avanceOpcion').value)];\n  });\n\n  async function abrirAvance(turno){\n    if(state.demo){showToast('Operaciones no disponibles en demostración.');return;}\n    avanceTurnoId=Number(turno.id);\n    avanceOpciones=[];\n    $('#avanceBackdrop').classList.remove('hidden');\n    setText('#avanceTitle',`Continuar · ${turno.numero_turno}`);\n    setText('#avanceInfo','Buscando próximos pasos autorizados...');\n    $('#avanceOpcion').disabled=true;\n    $('#avanceConfirm').disabled=true;\n    try{\n      const data=await api(`/api/recepcion/turnos/${avanceTurnoId}/opciones-avance`);\n      if(avanceTurnoId!==Number(turno.id))return;\n      avanceOpciones=Array.isArray(data.opciones)?data.opciones:[];\n      const lista=$('#avanceOpcion');lista.replaceChildren();\n      const placeholder=document.createElement('option');\n      placeholder.value='';placeholder.textContent='Seleccionar siguiente paso';\n      lista.appendChild(placeholder);\n      avanceOpciones.forEach((o,i)=>{\n        const opt=document.createElement('option');opt.value=String(i);\n        opt.textContent=o.etiqueta;lista.appendChild(opt);\n      });\n      lista.value='';lista.disabled=avanceOpciones.length===0;\n      setText('#avanceInfo',data.mensaje||'Selecciona la acción correspondiente al recorrido.');\n    }catch(err){setText('#avanceInfo',err.message);}\n  }\n\n  $('#avanceConfirm').addEventListener('click',async()=>{\n    if(accionCajaOcupada||avanceTurnoId==null)return;\n    const opcion=avanceOpciones[Number($('#avanceOpcion').value)];\n    if(!opcion)return;\n    const turnoId=avanceTurnoId;\n    if(!confirm(`¿Confirmar el avance del turno a ${opcion.destino}?\\n\\nVerifica antes que los pagos y requisitos estén realmente cumplidos.`))return;\n    const ruta=opcion.tipo==='SOLICITUD'\n      ? `/api/solicitudes-area/${opcion.id}/avanzar`\n      : `/api/turnos/${turnoId}/transicionar`;\n    const cuerpo=opcion.tipo==='SOLICITUD'\n      ? {requisito_confirmado:true}\n      : {evento:opcion.evento,motivo:'Continuidad del recorrido desde Recepción/Caja'};\n    accionCajaOcupada=true;$('#avanceConfirm').disabled=true;\n    try{\n      const resultado=await api(ruta,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(cuerpo)});\n      cerrarAvance();\n      showToast(resultado.message||'Avance registrado.');\n      await refresh();\n      if(state.view==='seguimiento')await loadSeguimiento();\n    }catch(err){showToast('No se pudo avanzar: '+err.message);}\n    finally{accionCajaOcupada=false;}\n  });\n\n  document.addEventListener('click',async e=>{\n    const boton=e.target.closest('[data-caja-accion]');\n    if(!boton||accionCajaOcupada)return;\n    const turno=state.caja.find(t=>Number(t.id)===Number(boton.dataset.id));\n    if(!turno)return;\n    if(boton.dataset.cajaAccion==='avanzar')return abrirAvance(turno);\n    if(state.demo){showToast('Operaciones no disponibles en demostración.');return;}\n    const accion=boton.dataset.cajaAccion;\n    if(!['llamar','iniciar'].includes(accion))return;\n    if(!confirm(`¿${accion==='llamar'?'Llamar':'Iniciar atención del'} turno ${turno.numero_turno}?`))return;\n    accionCajaOcupada=true;boton.disabled=true;\n    try{\n      const r=await api(`/api/turnos/${turno.id}/${accion}`,{\n        method:'POST',headers:{'Content-Type':'application/json'},\n        body:JSON.stringify({motivo:'Operación desde Recepción/Caja'})\n      });\n      showToast(r.message||'Turno actualizado.');\n      await refresh();\n    }catch(err){showToast(`No se pudo ${accion}: ${err.message}`);}\n    finally{accionCajaOcupada=false;boton.disabled=false;}\n  });\n\n"

if __name__=='__main__':
    try: main()
    except Exception as e:
        print('ERROR:',e,file=sys.stderr);sys.exit(1)
