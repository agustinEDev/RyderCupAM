# 🔄 Cómo Reiniciar el Servidor con el Código Actualizado

## Paso 1: Detener el servidor actual

Si tienes uvicorn corriendo, presiona **Ctrl + C** en esa terminal.

## Paso 2: Iniciar el servidor de nuevo

```bash
cd /path/to/RyderCupAm
source .venv/bin/activate  # Activar entorno virtual
uvicorn main:app --reload --log-level info
```

## Paso 3: Verificar que inició correctamente

Deberías ver:

```
INFO:     Started server process [xxxxx]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000
```

## Paso 4: Probar el registro

1. Ve al frontend
2. Regístrate con un email nuevo (o elimina el usuario actual primero)
3. **Observa los logs del servidor**

Deberías ver:

```
INFO:     127.0.0.1:xxxxx - "POST /api/v1/auth/register HTTP/1.1" 201 Created
INFO:root:Email enviado correctamente a tu-email@gmail.com
```

## Paso 5: Revisar tu email

Busca un email con:
- **Asunto**: "Bienvenido a Ryder Cup Friends, [Tu Nombre]!"
- **Remitente**: Ryder Cup Friends <noreply@rydercupfriends.com>
- **Contenido**: Email bilingüe (español/inglés) con botón de verificación

---

## Si NO ves logs sobre el email:

El servidor no cargó el código nuevo. Asegúrate de:
1. Detener completamente el servidor anterior
2. Activar el entorno virtual correcto
3. Estar en el directorio correcto
4. Usar `--reload` para auto-recarga

## Si ves un error en los logs:

Copia el error completo y analízalo.
