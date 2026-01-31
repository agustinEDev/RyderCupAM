# 🌍 Multi-Environment Setup - RyderCup AM

## 📋 Environment Overview

| Environment | Description | Frontend URL | Usage |
|-------------|-------------|--------------|-------|
| **Local (Docker)** | Local development with Docker Compose | `http://localhost:5173` | Daily development |
| **Local (Kubernetes)** | Local Kind cluster | `http://localhost:8080` | K8s testing before deploy |
| **Production** | Production deployment | `https://rydercupfriends.com` | Live application |

---

## 🐳 Environment 1: Local (Docker)

### Setup

**.env file:**
```bash
FRONTEND_URL=http://localhost:5173
MAILGUN_API_KEY=your-api-key
MAILGUN_DOMAIN=rydercupfriends.com
MAILGUN_FROM_EMAIL="Ryder Cup Friends <noreply@rydercupfriends.com>"
MAILGUN_API_URL=https://api.eu.mailgun.net/v3
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/rydercup
SECRET_KEY=your-local-secret-key
```

### Commands

```bash
# Start services
docker-compose up -d

# Apply migrations
docker-compose exec app alembic upgrade head

# View logs
docker-compose logs -f app

# Stop services
docker-compose down
```

### Verification
- Backend: http://localhost:8000/docs
- Frontend: http://localhost:5173
- Email links: `http://localhost:5173/verify-email?token=xxx`

---

## ☸️ Environment 2: Local (Kubernetes)

### Requirements
- Docker Desktop
- kubectl
- Kind

### Configuration

**k8s/api-configmap.yaml:**
```yaml
FRONTEND_URL: "http://localhost:8080"
```

**k8s/api-secret.yaml:**
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: api-secret
  namespace: rydercupfriends
type: Opaque
data:
  MAILGUN_API_KEY: <base64-encoded>
  SECRET_KEY: <base64-encoded>
  POSTGRES_PASSWORD: <base64-encoded>
```

### Deployment

```bash
# Deploy complete cluster
./k8s/scripts/deploy-cluster.sh

# Check status
./k8s/scripts/cluster-status.sh

# Port forward (in separate terminals)
kubectl port-forward -n rydercupfriends svc/frontend-service 8080:80
kubectl port-forward -n rydercupfriends svc/api-service 8000:8000

# Update only backend
./k8s/scripts/deploy-api.sh

# Update only frontend
./k8s/scripts/deploy-front.sh
```

### Verification
- Frontend: http://localhost:8080
- Backend: http://localhost:8000/docs
- Email links: `http://localhost:8080/verify-email?token=xxx`

### Troubleshooting

```bash
# Check ConfigMap
kubectl get configmap api-configmap -n rydercupfriends -o yaml | grep FRONTEND_URL

# Edit ConfigMap
kubectl edit configmap api-configmap -n rydercupfriends

# Restart deployment
kubectl rollout restart deployment/api-deployment -n rydercupfriends

# View logs
kubectl logs -f -n rydercupfriends deployment/api-deployment
```

---

## 🚀 Environment 3: Production

### Render.com Configuration

**Backend (Web Service) - Environment Variables:**
```bash
FRONTEND_URL=https://rydercupfriends.com
DATABASE_URL=<provided-by-render>
MAILGUN_API_KEY=<production-key>
MAILGUN_DOMAIN=rydercupfriends.com
MAILGUN_FROM_EMAIL="Ryder Cup Friends <noreply@rydercupfriends.com>"
MAILGUN_API_URL=https://api.eu.mailgun.net/v3
SECRET_KEY=<production-secret>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
ENVIRONMENT=production
PORT=8000
DOCS_USERNAME=admin
DOCS_PASSWORD=<secure-password>
```

**Frontend (Static Site):**
```bash
VITE_API_BASE_URL=https://rydercup-api.onrender.com
```

### Deployment

Automatic on push to `main`:
```bash
git push origin main
# Monitor at: https://dashboard.render.com
```

### Verification
- Frontend: https://rydercupfriends.com
- Backend: https://rydercup-api.onrender.com/docs
- Email links: `https://rydercupfriends.com/verify-email?token=xxx`

---

## 🔍 Configuration Verification

```bash
# Check config script
python k8s/scripts/check_config.py

# Manual check
python -c "from src.config.settings import settings; print(f'FRONTEND_URL: {settings.FRONTEND_URL}')"
```

---

## 🐛 Common Issues

### Issue 1: Wrong Email Links

**Symptoms**: Email links point to wrong URL

**Solution**:
1. Check `FRONTEND_URL` in your environment
2. Restart application
3. For K8s: `kubectl rollout restart deployment/api-deployment -n rydercupfriends`

### Issue 2: Emails Not Sending

**Solution**:
```bash
# Verify Mailgun config
python -c "from src.config.settings import settings; print('Mailgun:', bool(settings.MAILGUN_API_KEY))"

# Check logs
docker-compose logs app | grep -i mailgun
kubectl logs -n rydercupfriends deployment/api-deployment | grep -i mailgun
```

### Issue 3: Port Already in Use

```bash
# Find process
lsof -i :8000

# Kill process
kill -9 <PID>

# Or use different port
uvicorn main:app --reload --port 8001
```

---

## 📊 Port Summary

| Service | Docker | K8s (localhost) | Production |
|---------|--------|-----------------|------------|
| Backend | 8000 | 8000 | 443 (HTTPS) |
| Frontend | 5173 | 8080 | 443 (HTTPS) |
| PostgreSQL | 5432 | 5434 | 5432 (Render) |

---

## 🔗 References

- **Render Dashboard**: https://dashboard.render.com
- **Mailgun Dashboard**: https://app.mailgun.com
- **K8s Scripts**: `k8s/scripts/`
- **Full Docs**: See `docs/` directory

---

**Last Updated**: 28 January 2026
