-- TURNERO V2 - permisos para un rol de operación de Consulta Médica.
-- Ejecutar SOLO si se decide utilizar el rol 'MEDICO' o 'DOCTOR'.
-- No crea operadores ni los vincula con la tabla doctores.
-- No asigna áreas automáticamente.
BEGIN;

INSERT INTO permisos (codigo, nombre, descripcion, activo) VALUES
    ('turnos_ver', 'Ver turnos', 'Consultar turnos del área autorizada', TRUE),
    ('turnos_llamar', 'Llamar turnos', 'Llamar turnos del área autorizada', TRUE),
    ('turnos_iniciar', 'Iniciar turnos', 'Comenzar atención en el área autorizada', TRUE),
    ('turnos_omitir', 'Omitir llamados', 'Reponer en espera un turno llamado', TRUE),
    ('turnos_pausar', 'Pausar turnos', 'Pausar turnos en atención', TRUE),
    ('turnos_reanudar', 'Reanudar turnos', 'Reanudar turnos pausados', TRUE)
ON CONFLICT (codigo) DO NOTHING;

INSERT INTO rol_permisos (rol, permiso_id)
SELECT roles.rol, p.id
FROM (VALUES ('MEDICO'), ('DOCTOR')) AS roles(rol)
CROSS JOIN permisos p
WHERE p.codigo IN (
    'turnos_ver', 'turnos_llamar', 'turnos_iniciar',
    'turnos_omitir', 'turnos_pausar', 'turnos_reanudar'
) AND p.activo IS TRUE
ON CONFLICT (rol, permiso_id) DO NOTHING;

COMMIT;

-- Consultas de diagnóstico (sólo lectura):
SELECT id, codigo, nombre FROM areas
WHERE UPPER(codigo) LIKE 'CONSULTA%' OR LOWER(nombre) LIKE '%consulta%';
SELECT id, usuario, nombre, rol, sede_id, activo FROM operadores ORDER BY id;
SELECT o.usuario, s.nombre AS sede, a.codigo AS area, oa.activo
FROM operador_areas oa
JOIN operadores o ON o.id = oa.operador_id
JOIN sedes s ON s.id = oa.sede_id
JOIN areas a ON a.id = oa.area_id
ORDER BY o.usuario, a.codigo;
