BEGIN;

-- =====================================================
-- SEDES
-- =====================================================

INSERT INTO sedes (
    codigo,
    nombre,
    direccion,
    activo,
    fecha_creacion,
    id_ubicacion_fundacion
)
VALUES
    ('ORIZABA', 'Orizaba', NULL, TRUE, NOW(), NULL),
    ('CORDOBA', 'Córdoba', NULL, TRUE, NOW(), NULL)
ON CONFLICT (codigo) DO NOTHING;


-- =====================================================
-- ÁREAS
-- =====================================================

INSERT INTO areas (
    codigo,
    nombre,
    descripcion,
    genera_cola,
    activo,
    orden_visual
)
VALUES
    ('CONTROL', 'Recepción Inicial / Control', NULL, FALSE, TRUE, 1),
    ('TRABAJO_SOCIAL', 'Trabajo Social', NULL, TRUE, TRUE, 2),
    ('CAJA', 'Recepción / Caja', NULL, TRUE, TRUE, 3),
    ('CONSULTA', 'Consulta Médica', NULL, TRUE, TRUE, 4),
    ('GABINETE', 'Gabinete', NULL, TRUE, TRUE, 5),
    ('FARMACIA', 'Farmacia', NULL, TRUE, TRUE, 6),
    ('OPTICA', 'Asesoría Visual', NULL, TRUE, TRUE, 7),
    ('SALIDA', 'Salida', NULL, FALSE, TRUE, 8)
ON CONFLICT (codigo) DO NOTHING;


-- =====================================================
-- ÁREAS HABILITADAS EN CADA SEDE
-- =====================================================

INSERT INTO sede_areas (
    sede_id,
    area_id,
    activo,
    orden_visual,
    fecha_creacion
)
SELECT
    s.id,
    a.id,
    TRUE,
    COALESCE(a.orden_visual, 0),
    NOW()
FROM sedes s
CROSS JOIN areas a
WHERE s.codigo IN ('ORIZABA', 'CORDOBA')
ON CONFLICT (sede_id, area_id) DO NOTHING;


-- =====================================================
-- SERVICIOS
-- El Turnero no manejará dinero:
-- precio_base = NULL
-- requiere_pago = FALSE
-- =====================================================

INSERT INTO servicios (
    area_id,
    codigo,
    nombre,
    descripcion,
    precio_base,
    requiere_pago,
    activo
)
VALUES

(
    (SELECT id FROM areas WHERE codigo = 'TRABAJO_SOCIAL'),
    'AFILIACION',
    'Afiliación',
    NULL,
    NULL,
    FALSE,
    TRUE
),

(
    (SELECT id FROM areas WHERE codigo = 'GABINETE'),
    'AGUDEZA_VISUAL',
    'Agudeza Visual',
    NULL,
    NULL,
    FALSE,
    TRUE
),

(
    (SELECT id FROM areas WHERE codigo = 'OPTICA'),
    'ASESORIA_VISUAL',
    'Asesoría Visual',
    NULL,
    NULL,
    FALSE,
    TRUE
),

(
    (SELECT id FROM areas WHERE codigo = 'GABINETE'),
    'CALCULO_LIO',
    'Cálculo de LIO',
    NULL,
    NULL,
    FALSE,
    TRUE
),

(
    (SELECT id FROM areas WHERE codigo = 'CONSULTA'),
    'CONSULTA_GENERAL',
    'Consulta Oftalmológica',
    NULL,
    NULL,
    FALSE,
    TRUE
),

(
    (SELECT id FROM areas WHERE codigo = 'OPTICA'),
    'COTIZACION_LENTES',
    'Cotización de Lentes',
    NULL,
    NULL,
    FALSE,
    TRUE
),

(
    (SELECT id FROM areas WHERE codigo = 'OPTICA'),
    'ENTREGA_LENTES',
    'Entrega de Lentes',
    NULL,
    NULL,
    FALSE,
    TRUE
),

(
    (SELECT id FROM areas WHERE codigo = 'TRABAJO_SOCIAL'),
    'ESTUDIO_SOCIOECONOMICO',
    'Estudio Socioeconómico',
    NULL,
    NULL,
    FALSE,
    TRUE
),

(
    (SELECT id FROM areas WHERE codigo = 'TRABAJO_SOCIAL'),
    'ORIENTACION_CIRUGIA',
    'Orientación / Programación de Cirugía',
    NULL,
    NULL,
    FALSE,
    TRUE
),

(
    (SELECT id FROM areas WHERE codigo = 'OPTICA'),
    'PEDIDO_LENTES',
    'Pedido de Lentes',
    NULL,
    NULL,
    FALSE,
    TRUE
),

(
    (SELECT id FROM areas WHERE codigo = 'GABINETE'),
    'PRESION_INTRAOCULAR',
    'Presión Intraocular',
    NULL,
    NULL,
    FALSE,
    TRUE
),

(
    (SELECT id FROM areas WHERE codigo = 'GABINETE'),
    'QUERATOMETRIA',
    'Queratrometría',
    NULL,
    NULL,
    FALSE,
    TRUE
),

(
    (SELECT id FROM areas WHERE codigo = 'GABINETE'),
    'REFRACCION',
    'Refracción',
    NULL,
    NULL,
    FALSE,
    TRUE
),

(
    (SELECT id FROM areas WHERE codigo = 'FARMACIA'),
    'SURTIR_RECETA',
    'Surtir Receta',
    NULL,
    NULL,
    FALSE,
    TRUE
),

(
    (SELECT id FROM areas WHERE codigo = 'GABINETE'),
    'TONOMETRIA',
    'Tonometría',
    NULL,
    NULL,
    FALSE,
    TRUE
)

ON CONFLICT (codigo) DO NOTHING;


-- =====================================================
-- SERVICIOS POR SEDE
-- Todos internos inicialmente.
-- Córdoba: Cálculo LIO se maneja como EXTERNO.
-- =====================================================

INSERT INTO servicio_sedes (
    sede_id,
    servicio_id,
    disponible,
    modalidad,
    fecha_creacion
)
SELECT
    s.id,
    sv.id,
    TRUE,
    CASE
        WHEN s.codigo = 'CORDOBA'
             AND sv.codigo = 'CALCULO_LIO'
            THEN 'EXTERNO'
        ELSE 'INTERNO'
    END,
    NOW()
FROM sedes s
CROSS JOIN servicios sv
WHERE s.codigo IN ('ORIZABA', 'CORDOBA')
ON CONFLICT (sede_id, servicio_id) DO NOTHING;


-- =====================================================
-- DESTINO INICIAL - ORIZABA
-- =====================================================

INSERT INTO reglas_destino_inicial (
    sede_id,
    condicion,
    area_id,
    servicio_id,
    prioridad,
    activo,
    fecha_creacion
)
SELECT
    s.id,
    'AFILIADO',
    a.id,
    NULL,
    100,
    TRUE,
    NOW()
FROM sedes s
JOIN areas a
    ON a.codigo = 'CAJA'
WHERE
    s.codigo = 'ORIZABA'
    AND NOT EXISTS (
        SELECT 1
        FROM reglas_destino_inicial r
        WHERE r.sede_id = s.id
          AND r.condicion = 'AFILIADO'
          AND r.area_id = a.id
          AND r.servicio_id IS NULL
          AND r.activo = TRUE
    );


INSERT INTO reglas_destino_inicial (
    sede_id,
    condicion,
    area_id,
    servicio_id,
    prioridad,
    activo,
    fecha_creacion
)
SELECT
    s.id,
    'NO_AFILIADO',
    a.id,
    sv.id,
    100,
    TRUE,
    NOW()
FROM sedes s
JOIN areas a
    ON a.codigo = 'TRABAJO_SOCIAL'
JOIN servicios sv
    ON sv.codigo = 'AFILIACION'
WHERE
    s.codigo = 'ORIZABA'
    AND NOT EXISTS (
        SELECT 1
        FROM reglas_destino_inicial r
        WHERE r.sede_id = s.id
          AND r.condicion = 'NO_AFILIADO'
          AND r.area_id = a.id
          AND r.servicio_id = sv.id
          AND r.activo = TRUE
    );


-- =====================================================
-- DESTINO INICIAL - CÓRDOBA
-- =====================================================

INSERT INTO reglas_destino_inicial (
    sede_id,
    condicion,
    area_id,
    servicio_id,
    prioridad,
    activo,
    fecha_creacion
)
SELECT
    s.id,
    'AFILIADO',
    a.id,
    NULL,
    100,
    TRUE,
    NOW()
FROM sedes s
JOIN areas a
    ON a.codigo = 'CAJA'
WHERE
    s.codigo = 'CORDOBA'
    AND NOT EXISTS (
        SELECT 1
        FROM reglas_destino_inicial r
        WHERE r.sede_id = s.id
          AND r.condicion = 'AFILIADO'
          AND r.area_id = a.id
          AND r.servicio_id IS NULL
          AND r.activo = TRUE
    );


INSERT INTO reglas_destino_inicial (
    sede_id,
    condicion,
    area_id,
    servicio_id,
    prioridad,
    activo,
    fecha_creacion
)
SELECT
    s.id,
    'NO_AFILIADO',
    a.id,
    sv.id,
    100,
    TRUE,
    NOW()
FROM sedes s
JOIN areas a
    ON a.codigo = 'TRABAJO_SOCIAL'
JOIN servicios sv
    ON sv.codigo = 'AFILIACION'
WHERE
    s.codigo = 'CORDOBA'
    AND NOT EXISTS (
        SELECT 1
        FROM reglas_destino_inicial r
        WHERE r.sede_id = s.id
          AND r.condicion = 'NO_AFILIADO'
          AND r.area_id = a.id
          AND r.servicio_id = sv.id
          AND r.activo = TRUE
    );


-- =====================================================
-- TRANSICIONES BASE
-- =====================================================

-- Orizaba: Trabajo Social -> Recepción/Caja
INSERT INTO reglas_transicion (
    sede_id,
    area_origen_id,
    evento,
    area_destino_id,
    servicio_id,
    prioridad,
    activo,
    fecha_creacion
)
SELECT
    s.id,
    ao.id,
    'AFILIACION_COMPLETADA',
    ad.id,
    NULL,
    100,
    TRUE,
    NOW()
FROM sedes s
JOIN areas ao
    ON ao.codigo = 'TRABAJO_SOCIAL'
JOIN areas ad
    ON ad.codigo = 'CAJA'
WHERE
    s.codigo = 'ORIZABA'
    AND NOT EXISTS (
        SELECT 1
        FROM reglas_transicion r
        WHERE r.sede_id = s.id
          AND r.area_origen_id = ao.id
          AND r.evento = 'AFILIACION_COMPLETADA'
          AND r.area_destino_id = ad.id
          AND r.servicio_id IS NULL
          AND r.activo = TRUE
    );


-- Córdoba: Trabajo Social -> Recepción/Caja
INSERT INTO reglas_transicion (
    sede_id,
    area_origen_id,
    evento,
    area_destino_id,
    servicio_id,
    prioridad,
    activo,
    fecha_creacion
)
SELECT
    s.id,
    ao.id,
    'AFILIACION_COMPLETADA',
    ad.id,
    NULL,
    100,
    TRUE,
    NOW()
FROM sedes s
JOIN areas ao
    ON ao.codigo = 'TRABAJO_SOCIAL'
JOIN areas ad
    ON ad.codigo = 'CAJA'
WHERE
    s.codigo = 'CORDOBA'
    AND NOT EXISTS (
        SELECT 1
        FROM reglas_transicion r
        WHERE r.sede_id = s.id
          AND r.area_origen_id = ao.id
          AND r.evento = 'AFILIACION_COMPLETADA'
          AND r.area_destino_id = ad.id
          AND r.servicio_id IS NULL
          AND r.activo = TRUE
    );


-- Córdoba: Recepción/Caja -> Consulta
INSERT INTO reglas_transicion (
    sede_id,
    area_origen_id,
    evento,
    area_destino_id,
    servicio_id,
    prioridad,
    activo,
    fecha_creacion
)
SELECT
    s.id,
    ao.id,
    'RECEPCION_COMPLETADA',
    ad.id,
    NULL,
    100,
    TRUE,
    NOW()
FROM sedes s
JOIN areas ao
    ON ao.codigo = 'CAJA'
JOIN areas ad
    ON ad.codigo = 'CONSULTA'
WHERE
    s.codigo = 'CORDOBA'
    AND NOT EXISTS (
        SELECT 1
        FROM reglas_transicion r
        WHERE r.sede_id = s.id
          AND r.area_origen_id = ao.id
          AND r.evento = 'RECEPCION_COMPLETADA'
          AND r.area_destino_id = ad.id
          AND r.servicio_id IS NULL
          AND r.activo = TRUE
    );


-- Córdoba: Consulta -> Gabinete
INSERT INTO reglas_transicion (
    sede_id,
    area_origen_id,
    evento,
    area_destino_id,
    servicio_id,
    prioridad,
    activo,
    fecha_creacion
)
SELECT
    s.id,
    ao.id,
    'REQUIERE_GABINETE',
    ad.id,
    NULL,
    100,
    TRUE,
    NOW()
FROM sedes s
JOIN areas ao
    ON ao.codigo = 'CONSULTA'
JOIN areas ad
    ON ad.codigo = 'GABINETE'
WHERE
    s.codigo = 'CORDOBA'
    AND NOT EXISTS (
        SELECT 1
        FROM reglas_transicion r
        WHERE r.sede_id = s.id
          AND r.area_origen_id = ao.id
          AND r.evento = 'REQUIERE_GABINETE'
          AND r.area_destino_id = ad.id
          AND r.servicio_id IS NULL
          AND r.activo = TRUE
    );


-- Córdoba: Gabinete -> Consulta
INSERT INTO reglas_transicion (
    sede_id,
    area_origen_id,
    evento,
    area_destino_id,
    servicio_id,
    prioridad,
    activo,
    fecha_creacion
)
SELECT
    s.id,
    ao.id,
    'ESTUDIO_COMPLETADO',
    ad.id,
    NULL,
    100,
    TRUE,
    NOW()
FROM sedes s
JOIN areas ao
    ON ao.codigo = 'GABINETE'
JOIN areas ad
    ON ad.codigo = 'CONSULTA'
WHERE
    s.codigo = 'CORDOBA'
    AND NOT EXISTS (
        SELECT 1
        FROM reglas_transicion r
        WHERE r.sede_id = s.id
          AND r.area_origen_id = ao.id
          AND r.evento = 'ESTUDIO_COMPLETADO'
          AND r.area_destino_id = ad.id
          AND r.servicio_id IS NULL
          AND r.activo = TRUE
    );


COMMIT;