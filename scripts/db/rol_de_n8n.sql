-- n8n solo lee las columnas del informe de los lunes (auditoría del 16 nov 2026, DB-01).
--
-- n8n_lectura tenía SELECT directo en 42 de las 43 tablas: users (con los hashes de las
-- contraseñas, columna `password`), refresh_tokens, password_history, user_devices... rol_de_la_api.sql solo
-- le quitó los permisos POR DEFECTO (tablas futuras); los de las tablas que ya existían
-- seguían ahí. El único uso de n8n es el informe semanal (~/n8n-cbg/workflows/
-- informe-semanal.json, nodo «Datos de la app (solo lectura)»), y su consulta solo lee:
--
--   users          is_active, created_at, first_name, last_name
--   competitions   created_at, name, status
--   enrollments    created_at
--   quick_matches  created_at, status, updated_at
--
-- Si el informe cambia y lee otra columna, hay que añadirla aquí (y en la comprobación
-- del paso 5) y volver a ejecutarlo; si no, el informe falla con «permission denied».
--
-- Lo ejecuta el DUEÑO de la base, conectado a la base de la app, en psql y con
-- `\set ON_ERROR_STOP on` antes del `\i`. Se puede repetir: deja siempre el mismo estado.
-- Va en una transacción y comprueba el resultado antes del COMMIT: si algo no cuadra, no
-- cambia nada. Guía: docs/RUNBOOK.md, «n8n solo lee lo del informe».

BEGIN;

-- 0. El rol tiene que existir, y no heredar permisos de otro rol (la auditoría no le vio
--    ninguno; si los tuviera, quitar sus permisos directos no bastaría)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'n8n_lectura') THEN
        RAISE EXCEPTION 'No existe el rol n8n_lectura';
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_auth_members m JOIN pg_roles r ON r.oid = m.member
        WHERE r.rolname = 'n8n_lectura'
    ) THEN
        RAISE EXCEPTION 'n8n_lectura es miembro de otro rol: revisar antes (\du n8n_lectura)';
    END IF;
END
$$;

-- 1. Fuera todo lo que tiene en tablas, vistas y secuencias. Quitar un permiso de una
--    tabla quita también los de sus columnas: así se puede repetir sin acumular
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM n8n_lectura;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM n8n_lectura;

-- 2. Y nada en las tablas futuras (ya lo hacía rol_de_la_api.sql, paso 6; aquí por si
--    este se ejecuta solo)
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM n8n_lectura;
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM n8n_lectura;

-- 3. Solo las columnas del informe
GRANT SELECT (is_active, created_at, first_name, last_name) ON public.users TO n8n_lectura;
GRANT SELECT (created_at, name, status) ON public.competitions TO n8n_lectura;
GRANT SELECT (created_at) ON public.enrollments TO n8n_lectura;
GRANT SELECT (created_at, status, updated_at) ON public.quick_matches TO n8n_lectura;

-- 4. Solo lectura y con tope: una consulta que se atasque no se queda horas en la base.
--    El informe tarda milisegundos (la base pesa unos 23 MB). Valen desde la siguiente
--    conexión de n8n
ALTER ROLE n8n_lectura SET default_transaction_read_only = on;
ALTER ROLE n8n_lectura SET statement_timeout = '30s';
ALTER ROLE n8n_lectura SET idle_in_transaction_session_timeout = '60s';
ALTER ROLE n8n_lectura SET lock_timeout = '5s';

-- 5. Comprobación antes del COMMIT: lee exactamente esas 11 columnas y ninguna tabla
--    entera (también por PUBLIC). Si no, se para y no cambia nada
DO $$
DECLARE
    esperadas text[] := ARRAY[
        'competitions.created_at', 'competitions.name', 'competitions.status',
        'enrollments.created_at',
        'quick_matches.created_at', 'quick_matches.status', 'quick_matches.updated_at',
        'users.created_at', 'users.first_name', 'users.is_active', 'users.last_name'
    ];
    legibles text[];
    tablas text[];
BEGIN
    SELECT coalesce(array_agg(c.relname || '.' || a.attname ORDER BY c.relname, a.attname), '{}')
      INTO legibles
      FROM pg_class c
      JOIN pg_namespace n ON n.oid = c.relnamespace
      JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped
     WHERE n.nspname = 'public'
       AND c.relkind IN ('r', 'p', 'v', 'm', 'f')
       AND has_column_privilege('n8n_lectura', c.oid, a.attnum, 'SELECT');

    IF legibles IS DISTINCT FROM (SELECT array_agg(e ORDER BY e) FROM unnest(esperadas) e) THEN
        RAISE EXCEPTION 'n8n_lectura lee % y tenía que leer %', legibles, esperadas;
    END IF;

    SELECT coalesce(array_agg(c.relname ORDER BY c.relname), '{}')
      INTO tablas
      FROM pg_class c
      JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname = 'public'
       AND c.relkind IN ('r', 'p', 'v', 'm', 'f', 'S')
       AND (has_table_privilege('n8n_lectura', c.oid, 'SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER')
            OR (c.relkind = 'S' AND has_sequence_privilege('n8n_lectura', c.oid, 'USAGE, SELECT, UPDATE')));

    IF tablas <> '{}' THEN
        RAISE EXCEPTION 'n8n_lectura conserva permisos de tabla entera en %', tablas;
    END IF;

    -- Redundante con lo de arriba, pero es lo que importa: ni el hash ni el correo
    IF has_column_privilege('n8n_lectura', 'public.users', 'password', 'SELECT')
       OR has_column_privilege('n8n_lectura', 'public.users', 'email', 'SELECT')
       OR has_column_privilege('n8n_lectura', 'public.users', 'password_reset_token', 'SELECT') THEN
        RAISE EXCEPTION 'n8n_lectura todavía lee el hash, el correo o el token de users';
    END IF;
END
$$;

COMMIT;

-- 6. Para verlo con los ojos (fuera de la transacción, solo lectura). Tiene que salir:
--    - permisos de tabla entera: 0 filas
--    - columnas: las 11 de arriba
--    - lee_hashes, lee_correos, lee_refresh_tokens, lee_password_history: false
--    - ajustes del rol: los 4 del paso 4
SELECT c.relname AS tabla_entera_legible
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p', 'v', 'm', 'f')
   AND has_table_privilege('n8n_lectura', c.oid, 'SELECT');

SELECT c.relname AS tabla, a.attname AS columna
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace
  JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped
 WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p', 'v', 'm', 'f')
   AND has_column_privilege('n8n_lectura', c.oid, a.attnum, 'SELECT')
 ORDER BY 1, 2;

SELECT has_column_privilege('n8n_lectura', 'public.users', 'password', 'SELECT') AS lee_hashes,
       has_column_privilege('n8n_lectura', 'public.users', 'email', 'SELECT') AS lee_correos,
       has_table_privilege('n8n_lectura', 'public.refresh_tokens', 'SELECT') AS lee_refresh_tokens,
       has_table_privilege('n8n_lectura', 'public.password_history', 'SELECT') AS lee_password_history;

SELECT unnest(rolconfig) AS ajuste_del_rol FROM pg_roles WHERE rolname = 'n8n_lectura';
