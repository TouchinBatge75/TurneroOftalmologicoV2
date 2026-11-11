# Turnero Oftalmológico V2 — Roles configurables V1

## Qué hace

- Añade la tabla PostgreSQL `roles` con código único, nombre, descripción, estado y fecha de creación.
- Conserva `operadores.rol` y `rol_permisos.rol` como cadenas, pero las valida con claves foráneas a `roles.codigo`.
- Importa automáticamente todos los roles ya utilizados por operadores o permisos; añade `ADMIN`, `RECEPCION`, `TRABAJO_SOCIAL`, `MEDICO` y `AREA`.
- Agrega interfaz `/admin/roles` y API CRUD básica. Permite configurar permisos y cambiar el rol de operadores existentes.
- Mantiene intactas las tablas `permisos`, `operador_permisos` y `operador_areas`.
- Los roles inactivos impiden utilizar el sistema a operadores de ese rol.
- No altera el motor de recorridos ni las pantallas de Recepción y Doctores.

## Antes de empezar

1. Ten una copia de seguridad de la base de datos PostgreSQL (por ejemplo, DBeaver -> Tools -> Backup). Usa el entorno de desarrollo primero.
2. Asegúrate de que los archivos actuales de Turnero funcionan y que `python -m flask routes` inicia sin errores.
3. Consulta `python -m flask db current` y `python -m flask db heads`: idealmente deben coincidir. Si hay migraciones pendientes, revísalas antes de añadir otra.
4. El rol `ADMIN` debe tener los permisos `admin_acceder` y `permisos_gestionar` (las pruebas anteriores lo confirmaron).

## Instalación en Windows PowerShell

En `C:\Users\elmem\Desktop\Turnero` con `(venv)` activo:

```powershell
Expand-Archive -LiteralPath "$env:USERPROFILE\Downloads\turnero_roles_configurables_v1.zip" -DestinationPath . -Force
```

El ZIP agrega, sin reemplazar módulos existentes:

- `app/admin_roles.py`
- `templates/admin_roles.html`
- `tools/preparar_roles.py`
- `plantillas/migracion_roles.py.txt`

Ejecuta:

```powershell
python .\tools\preparar_roles.py
```

**El script realiza** respaldos `app/models.pre_roles.bak` y `app/__init__.pre_roles.bak`; modifica únicamente esos dos archivos, y usa `python -m flask db revision -m roles_configurables_v1` para generar una nueva migración con el `down_revision` correcto. **Todavía no cambia PostgreSQL.**

Revisa el nuevo archivo bajo `migrations/versions/` y, cuando tengas respaldo, ejecuta:

```powershell
python -m flask db upgrade
python -m compileall -q app
python -m flask routes | Select-String 'admin_roles'
```

Si ocurre un error durante `db upgrade`, **no ejecutes SQL a mano para continuar**; comparte el traceback. Alembic no debe marcar la revisión como aplicada si la operación falló.

Finalmente reinicia Flask:

```powershell
python -m flask run
```

Inicia sesión con `admin` en `http://127.0.0.1:5000/`; el flujo `/mi-panel` lo llevará a `/admin/roles`. Alternativamente abre `http://127.0.0.1:5000/admin/roles`.

## Endpoints

| Método | URL | Acción |
|---|---|---|
| GET | `/admin/roles` | Panel visual |
| GET | `/api/admin/roles` | Lista roles, asignaciones y estado |
| GET | `/api/admin/roles/permisos` | Lista permisos activos |
| GET | `/api/admin/roles/operadores` | Lista operadores |
| POST | `/api/admin/roles` | Crea un rol (sin permisos iniciales) |
| PATCH | `/api/admin/roles/<id>` | Edita nombre, descripción, estado |
| PUT | `/api/admin/roles/<id>/permisos` | Reemplaza permisos del rol |
| PUT | `/api/admin/roles/operadores/<id>/rol` | Asigna un rol existente a un operador |

Todos los endpoints requieren sesión de `ADMIN`, permiso `permisos_gestionar` y CSRF para peticiones con cambios.

## Restricciones de seguridad

- No permite renombrar el `codigo` de un rol: se mantiene estable para no romper referencias.
- No permite borrar roles; se desactivan, siempre que no tengan operadores activos.
- No permite desactivar `ADMIN`, quitarle `admin_acceder`/`permisos_gestionar` ni cambiar tu propio rol.
- No permite quitar el último ADMIN activo.
- Los permisos de cada rol y de cada operador se siguen evaluando mediante `verificar_permiso`.
- Cambiar rol no cambia sede/área ni limpia las excepciones de `operador_permisos`.
- Las mutaciones generan un registro `warning` en los logs de Flask; se recomienda añadir auditoría persistente antes de producción.

## Prueba breve

1. Abrir como admin `/admin/roles` y confirmar los roles existentes.
2. Crear `OPTOMETRISTA`, asignar `turnos_ver`, guardar y recargar. Debe mantenerse.
3. Desactivarlo (sin operadores asignados) y confirmar que no se pueda otorgar a operadores.
4. Probar como `recepcion_prueba`: `/api/admin/roles` debe responder HTTP 403.
5. Confirmar que Recepción `/recepcion` y Doctor `/medicos` conservan permisos previos.

## Precaución por compatibilidad

El script aplica un parche sobre los puntos identificados en el `models.py` que ya compartiste (`Operador`, `RolPermiso`). Si esos fragmentos han cambiado, el instalador detendrá la ejecución con un error en lugar de editar código equivocado. En tal caso, no fuerces las sustituciones: comparte el error y la sección afectada.
