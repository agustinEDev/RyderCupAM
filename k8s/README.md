# 🚀 Gestión del Entorno de Pruebas con Kubernetes

Este documento centraliza toda la información necesaria para desplegar, gestionar y mantener el entorno de pruebas de **RyderCupAm** utilizando Kubernetes.

## 🧐 ¿Qué es Kubernetes y por qué lo usamos?

**Kubernetes (K8s)** es un sistema de orquestación de contenedores que automatiza el despliegue, escalado y gestión de aplicaciones. Para este proyecto, utilizamos **Kind (Kubernetes in Docker)**, que permite ejecutar un clúster de Kubernetes localmente usando contenedores de Docker.

**Beneficios en nuestro entorno de pruebas:**
- **Consistencia:** Asegura que todos los desarrolladores trabajen en un entorno idéntico al de producción.
- **Aislamiento:** Todos los servicios (backend, frontend, base de datos) se ejecutan de forma aislada pero comunicada.
- **Automatización:** Los scripts proporcionados simplifican tareas complejas como el despliegue o la restauración de la base de datos.
- **Escalabilidad:** Permite simular un entorno con múltiples réplicas de los servicios.

---

## ✅ Prerrequisitos

Antes de empezar, asegúrate de tener instalado el siguiente software:

| Software       | Versión Mínima | Comando de Verificación      |
|----------------|----------------|------------------------------|
| Docker Desktop | 24.0+          | `docker --version`           |
| kubectl        | 1.28+          | `kubectl version --client`   |
| Kind           | 0.20+          | `kind version`               |

Puedes verificar todas las versiones con un solo comando:
```bash
docker --version && kubectl version --client && kind version
```

---

## 🚀 Scripts de Gestión

Todos los scripts se encuentran en el directorio `k8s/scripts/` y deben ejecutarse desde el directorio `k8s`.

### Flujo de Trabajo Típico

1.  **Primer Despliegue:**
    ```bash
    cd k8s
    ./scripts/deploy-cluster.sh
    ```
2.  **Acceder a la aplicación:**
    Una vez desplegado el clúster, los servicios son accesibles directamente:
    - Frontend: `http://localhost:8080`
    - Backend API: `http://localhost:8000/docs`

3.  **Verificar el estado:**
    ```bash
    ./scripts/cluster-status.sh
    ```
4.  **Al terminar de trabajar:**
    ```bash
    ./scripts/destroy-cluster.sh
    ```

### Resumen de Scripts

| Script                    | Descripción                                                                          |
|---------------------------|--------------------------------------------------------------------------------------|
| `deploy-cluster.sh`       | **(Principal)** Despliega el clúster completo desde cero (DB, API, Frontend).        |
| `deploy-db.sh`            | Actualiza la base de datos y aplica migraciones de Alembic.                          |
| `deploy-api.sh [tag]`     | Recompila y despliega una nueva versión del backend (API).                           |
| `deploy-front.sh [tag]`   | Recompila y despliega una nueva versión del frontend.                                |
| `destroy-cluster.sh`      | **(Peligroso)** Elimina completamente el clúster y todos sus datos.                  |
| `cluster-status.sh`       | Muestra un informe detallado del estado de todos los componentes del clúster.        |
| `restore-db.sh`           | Restaura la base de datos desde un archivo de backup ubicado en `k8s/backups/`.      |
| `check_config.py`         | Script de Python para validar la configuración de los manifiestos.                   |

### `deploy-cluster.sh`
Despliega la aplicación completa. Es ideal para la configuración inicial.
- **Qué hace:**
    1. Verifica prerrequisitos.
    2. Crea un clúster de Kind si no existe, aplicando el mapeo de puertos.
    3. Aplica todos los manifiestos de Kubernetes (`.yaml`).
    4. Despliega PostgreSQL, el backend y el frontend en orden.
    5. Espera a que todos los servicios estén operativos.
- **Uso:** `./scripts/deploy-cluster.sh`

### `deploy-db.sh`
Despliega o actualiza el esquema de la base de datos.
- **Qué hace:**
    1. Crea un backup automático de la base de datos en `k8s/backups/`.
    2. Reinicia el pod de PostgreSQL.
    3. Aplica las migraciones pendientes de Alembic.
- **Uso:** `./scripts/deploy-db.sh`

### `deploy-api.sh` & `deploy-front.sh`
Actualizan el backend o el frontend con los últimos cambios del código.
- **Qué hacen:**
    1. Construyen una nueva imagen de Docker con la versión especificada (o `latest`).
    2. Suben la imagen al registro (Docker Hub).
    3. Realizan una actualización gradual (rolling update) en Kubernetes para no interrumpir el servicio.
- **Uso:**
    ```bash
    ./scripts/deploy-api.sh v1.2.0
    ./scripts/deploy-front.sh v1.5.1
    ```

### `destroy-cluster.sh`
Elimina por completo el entorno de Kubernetes. **Esta acción es irreversible y borrará todos los datos de la base de datos.**
- **Qué hace:**
    1. Pide una confirmación explícita para evitar accidentes.
    2. Elimina el clúster de Kind.
- **Uso:** `./scripts/destroy-cluster.sh`

---

## 🔐 Secrets

`k8s/api-secret.yaml` está **versionado en git** y debe contener únicamente placeholders de ejemplo — nunca valores reales (el repo es público).

Para tener credenciales reales en local (p. ej. para que Mailgun envíe correos de verdad en desarrollo):

1. Crea `k8s/api-secret.local.yaml` (ya está en `.gitignore`, nunca se commitea) copiando la estructura de `api-secret.yaml`.
2. Rellena ahí los valores reales (p. ej. `MAILGUN_API_KEY`, copiada directamente del dashboard de Render → Environment, sin pasar por ningún fichero versionado ni por el chat).
3. `deploy-cluster.sh` y `restart-cluster.sh` aplican automáticamente `api-secret.local.yaml` si existe, en lugar de `api-secret.yaml`.

⚠️ Si algún valor real llega a `api-secret.yaml` por error, rótalo de inmediato en el proveedor correspondiente (Mailgun, etc.) — el fichero es público en cuanto se commitea.

---

## 🗃️ Gestión de la Base de Datos

### Backups
- **Automáticos:** El script `deploy-db.sh` crea un backup en `k8s/backups/` antes de realizar cualquier cambio.
- **Manuales:** Puedes crear un backup manual ejecutando el comando `pg_dump` directamente sobre el pod de PostgreSQL.

### Restauración
El script `restore-db.sh` facilita la restauración de la base de datos desde un backup.
- **Qué hace:**
    1. Muestra una lista de los backups disponibles en `k8s/backups/`.
    2. Pide que selecciones el archivo a restaurar.
    3. **Advertencia:** Confirma la operación, ya que **borrará todos los datos actuales**.
    4. Restaura los datos y aplica las migraciones necesarias.
- **Uso:** `./scripts/restore-db.sh`

---

## 🌐 Acceso a los Servicios

El acceso a los servicios es **automático** gracias a la configuración del clúster de Kind (`kind-config.yaml`), que mapea los puertos del clúster a tu `localhost`.

**No necesitas ejecutar ningún script de `port-forward`.**

Una vez que el clúster esté desplegado con `deploy-cluster.sh`, puedes acceder directamente a:

- **Frontend:** [http://localhost:8080](http://localhost:8080)
- **Backend (Swagger UI):** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Base de Datos (externa):** `localhost:5434`

Este método es más estable y simula de forma más realista un entorno de producción.

---

## 🛠️ Troubleshooting

- **Permisos denegados en scripts:** Si recibes un error de `Permission denied`, asegúrate de que los scripts sean ejecutables:
  ```bash
  chmod +x k8s/scripts/*.sh
  ```
- **Pods en estado `CrashLoopBackOff` o `Error`:**
  Usa `cluster-status.sh` para obtener una visión general. Para más detalles, revisa los logs del pod con problemas:
  ```bash
  # Reemplaza <nombre-del-pod> por el pod que falla
  kubectl logs <nombre-del-pod>
  ```
- **El puerto `8080` o `8000` ya está en uso:**
  Asegúrate de no tener otro servicio (o un `port-forward` manual antiguo) ocupando esos puertos en tu máquina. Puedes usar `lsof -i :8080` para ver qué proceso lo está usando.
