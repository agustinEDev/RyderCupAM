# 🛠️ Kubernetes Scripts - Ryder Cup Friends

Automation scripts to manage the Kubernetes cluster.

---

## 📜 Available Scripts



### 1. `deploy-cluster.sh` - Full Cluster Deployment



Deploys the complete application to Kubernetes with a single command.



**Usage:**

```bash

./scripts/deploy-cluster.sh

```



**What it does:**

- ✅ Verifies prerequisites (Docker, kubectl, Kind)

- ✅ Creates Kind cluster (or uses existing one)

- ✅ Applies ConfigMaps and Secrets

- ✅ Creates persistent storage (PVC)

- ✅ Deploys PostgreSQL

- ✅ Deploys Backend (FastAPI)

- ✅ Deploys Frontend (React + nginx)

- ✅ Waits for all pods to be ready

- ✅ Shows access instructions



**Estimated time:** ~3-5 minutes



---



### 2. `deploy-api.sh` - Update Backend API



Updates only the backend (API) with latest code changes, rebuilding and deploying the Docker image.



**Usage:**

```bash

# Update with "latest" tag

./scripts/deploy-api.sh



# Update with specific version

./scripts/deploy-api.sh v1.0.1

```



**What it does:**

- ✅ Verifies prerequisites (Docker, kubectl, cluster)

- ✅ Builds new Docker image for backend

- ✅ Pushes image to Docker Hub

- ✅ Updates deployment in Kubernetes

- ✅ Performs rolling update with zero downtime

- ✅ Waits for all pods to be ready

- ✅ Shows logs and final status



**Features:**

- 🔄 **Rolling update:** Maintains high availability (zero downtime)

- 🎨 **Colorized output:** Easy to follow the process

- ✅ **Validations:** Verifies each step before continuing

- 📊 **Post-deployment verification:** Shows pod status and logs

- ↩️ **Easy rollback:** Includes command to undo changes



**When to use:**

- After making backend code changes

- To deploy bug fixes

- To update Python dependencies

- To deploy new API features



**Estimated time:** ~2-4 minutes (depends on Docker Hub connection)



---



### 3. `deploy-front.sh` - Update Frontend



Updates only the frontend with latest code changes.



**Usage:**

```bash

./scripts/deploy-front.sh [version]

```



**What it does:**

- ✅ Builds new frontend Docker image

- ✅ Pushes image to Docker Hub

- ✅ Updates frontend deployment

- ✅ Performs rolling update



**Estimated time:** ~2-4 minutes



---



### 4. `deploy-db.sh` - Deploy Database with Migrations



Restarts PostgreSQL database and applies pending Alembic migrations.



**Usage:**

```bash

# Interactive mode (asks for confirmation)

./scripts/deploy-db.sh



# Force mode (skips confirmation)

./scripts/deploy-db.sh --force

```



**What it does:**

- ✅ Creates automatic backup before restart (saved in `k8s/backups/`)

- ✅ Restarts PostgreSQL deployment (scale 0→1)

- ✅ Applies all pending Alembic migrations

- ✅ Verifies deployment and database connection

- ⚠️ API connections reconnect automatically (no restart needed)



**Features:**

- 💾 **Automatic backup:** Uses `pg_dump` before any changes

- 🔐 **Safe confirmation:** Requires explicit `y` to proceed (default: N)

- ⚡ **Quick downtime:** ~30-60 seconds

- 🔄 **Auto-reconnect:** API connections restore automatically



**When to use:**

- After creating new Alembic migrations

- To apply pending database schema changes

- To restart PostgreSQL for maintenance



**Estimated time:** ~1-2 minutes



---



### 5. `restore-db.sh` - Restore Database from Backup



Restores PostgreSQL database from a backup file.



**Usage:**

```bash

./scripts/restore-db.sh

```



**What it does:**

- 📋 Lists all available backups in `k8s/backups/`

- ✍️ Prompts for backup filename

- ✅ Validates backup file exists and is not empty

- ⚠️ Shows clear warning: **ALL CURRENT DATA WILL BE LOST**

- 🗄️ Drops current database and recreates it

- 📥 Restores data from backup using `psql`

- 🔧 Applies Alembic migrations

- 🔄 Restarts API pods



**Features:**

- 🔒 **Safe confirmation:** Requires explicit `y` to proceed

- 📋 **Interactive selection:** Shows backup list with size and date

- ✅ **Validation:** Checks file exists and is not empty

- 🔧 **Migration sync:** Applies migrations after restore



**When to use:**

- To restore from a previous backup

- To revert database to known good state

- To recover from data corruption



**Estimated time:** ~2-3 minutes



---



### 6. `cluster-status.sh` - Complete Diagnostics



Shows complete cluster status visually.



**Usage:**

```bash

./scripts/cluster-status.sh

```



**What it shows:**

- 📊 Cluster information

- 🖥️ Node status

- 📦 All pods status

- 🌐 Services and endpoints

- 🚀 Deployments and replicas

- ⚙️ ConfigMaps and Secrets

- 💾 Persistent storage

- 📋 Recent events

- ❤️ Health checks (backend + frontend)

- 📊 General summary



**When to use:**

- To verify everything is running

- To diagnose problems

- To check status before/after changes



---



### 7. `destroy-cluster.sh` - Delete Cluster



Completely deletes the Kubernetes cluster.



**Usage:**

```bash

./scripts/destroy-cluster.sh

```



**What it does:**

- ⚠️ Asks for confirmation

- 🗑️ Deletes the complete cluster

- 🐳 Optionally deletes Kind Docker images



**⚠️ WARNING:** This action will delete:

- All pods

- All PostgreSQL data

- All configurations

- The complete cluster



---



## 🚀 Typical Workflows



### First Time Setup



```bash

# 1. Deploy complete cluster

./scripts/deploy-cluster.sh



# 2. Verify everything is running

./scripts/cluster-status.sh



# 3. Access the application directly (port-forwards are automatic)

#    Frontend: http://localhost:8080

#    Backend: http://localhost:8000

```



### Update Backend (After Code Changes)



```bash

# 1. Make your backend code changes

vim main.py  # or any file



# 2. Deploy the update

./scripts/deploy-api.sh



# 3. Verify the update worked

./scripts/cluster-status.sh



# 4. Check logs if needed

kubectl logs deployment/rydercup-api -f

```



### Apply Database Migrations



```bash

# 1. Create your Alembic migration

alembic revision --autogenerate -m "Add new field"



# 2. Deploy database changes

./scripts/deploy-db.sh



# 3. Verify migrations applied

kubectl exec -it deployment/rydercup-api -- alembic current



# 4. Backup is automatically saved in k8s/backups/

```



### Restore from Backup



```bash

# 1. Run restore script

./scripts/restore-db.sh



# 2. Select backup from list

# Enter backup filename: db_backup_20260109_160929.sql



# 3. Confirm restore (type 'y')

# ⚠️  ALL CURRENT DATA WILL BE LOST



# 4. Verify restore succeeded

./scripts/cluster-status.sh

```



### Daily Verification



```bash

# View quick status

./scripts/cluster-status.sh



# View logs in real-time

kubectl logs -f deployment/rydercup-frontend

kubectl logs -f deployment/rydercup-api



# Check endpoints

curl http://localhost:8000/

curl http://localhost:8080/health

```



### Rollback if Something Goes Wrong



```bash

# View deployment history

kubectl rollout history deployment/rydercup-api



# Return to previous version

kubectl rollout undo deployment/rydercup-api



# Verify rollback worked

./scripts/cluster-status.sh

```



### Cleanup



```bash

# Delete complete cluster

./scripts/destroy-cluster.sh

```



---



## 💾 Database Backup Management



### Backup Location



All backups are stored in `k8s/backups/` directory:

```

k8s/

  backups/

    db_backup_20260109_160929.sql

    db_backup_20260109_143052.sql

    ...

```



### Automatic Backups



`deploy-db.sh` automatically creates a backup before applying migrations:

- Filename format: `db_backup_YYYYMMDD_HHMMSS.sql`

- Location: `k8s/backups/`

- Uses `pg_dump` with correct credentials from Kubernetes secrets



### Manual Backup



```bash

# Get database pod

DB_POD=$(kubectl get pods -n rydercupfriends -l component=database -o jsonpath='{.items[0].metadata.name}')



# Get credentials

POSTGRES_USER=$(kubectl get secret rydercup-api-secret -n rydercupfriends -o jsonpath='{.data.POSTGRES_USER}' | base64 -d)



# Create backup

kubectl exec -n rydercupfriends $DB_POD -- pg_dump -U $POSTGRES_USER rcfdevdb > k8s/backups/manual_backup_$(date +%Y%m%d_%H%M%S).sql

```



---



## 📚 Additional Documentation



- **Guía Principal de Kubernetes:** `k8s/README.md`



---



## 🛠️ Customization



### Modify Cluster Name



Edit the `CLUSTER_NAME` variable in each script:



```bash

CLUSTER_NAME="my-custom-cluster"

```



### Add More Checks to cluster-status.sh



The `cluster-status.sh` script is modular, you can add additional sections:



```bash

# ==========================================

# X. New Section

# ==========================================

print_header "🆕 MY NEW SECTION"



# Your code here

```



---



## 🐛 Troubleshooting



### Script fails with "Permission denied"



```bash

# Make scripts executable

chmod +x k8s/scripts/*.sh

```



### Script fails with "docker: command not found"



Make sure Docker Desktop is installed and running:



```bash

docker --version

docker info

```



### Script fails with "cluster already exists"



The `deploy-cluster.sh` script detects existing clusters and asks if you want to delete it.



To force recreation:



```bash

kind delete cluster --name rydercupam-cluster

./scripts/deploy-cluster.sh

```



### Backup fails with "role does not exist"



The scripts automatically get the correct PostgreSQL user from Kubernetes secrets. If you see this error, verify your secrets:



```bash

kubectl get secret rydercup-api-secret -n rydercupfriends -o yaml

```



### Database restore fails



1. Verify backup file exists and is not empty:

```bash

ls -lh k8s/backups/

```



2. Check database pod is running:

```bash

kubectl get pods -n rydercupfriends -l component=database

```



3. Check logs:

```bash

kubectl logs -n rydercupfriends -l component=database --tail=50

```



---



## 📝 Notes



- All scripts use `set -e` to stop on first error

- Scripts colorize output for better readability

- Scripts are idempotent (can be executed multiple times)

- Database backups are never committed to Git (in `.gitignore`)

- Confirmation prompts default to `N` for safety



---



**Last updated:** January 9, 2026

**Version:** v1.13.0


