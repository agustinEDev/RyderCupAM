# 🤖 Guía de Implementación RAG - Asistente de Reglamento de Golf

> **⚠️ DOCUMENTO TEMPORAL:** Este archivo debe **ELIMINARSE** una vez completada la implementación de v1.11.0.
>
> **Estado:** ❌ Pendiente de implementación
>
> **Progreso:** 0/3 semanas completadas

---

## 📋 Checklist de Implementación

### Semana 1: Domain Layer
- [ ] Configurar Pinecone (crear índice, API keys)
- [ ] Configurar Redis Cloud Free Tier
- [ ] Entities: `Document`, `QueryResult`
- [ ] Value Objects: `DocumentId`, `EmbeddingVector`
- [ ] Repository interfaces: `VectorRepository`, `CacheRepository`
- [ ] Tests unitarios domain (20-30 tests)

### Semana 2: Application + Infrastructure
- [ ] Use Case: `QueryGolfRulesUseCase` con validaciones
- [ ] DTOs: `QueryRequestDTO`, `QueryResponseDTO`
- [ ] Ports: `EmbeddingsServiceInterface`, `LLMServiceInterface`, `CacheServiceInterface`, `DailyQuotaServiceInterface`
- [ ] Adapters: `PineconeRepository`, `RedisCacheRepository`
- [ ] Services: `OpenAIEmbeddingsService`, `OpenAILLMService`
- [ ] `RedisDailyQuotaService` (dual-layer rate limiting)
- [ ] Pre-FAQs hardcodeadas (20-30 preguntas)
- [ ] Excepciones custom (4 excepciones)
- [ ] Tests application + infrastructure (50-60 tests)

### Semana 3: API + Deploy
- [ ] Endpoints FastAPI (3 endpoints)
- [ ] SlowAPI rate limiting (10 queries/min)
- [ ] Script ingestión documentos (50 docs)
- [ ] Dependency injection en routes
- [ ] Tests integración API (15-20 tests)
- [ ] Documentación: actualizar CLAUDE.md, Swagger
- [ ] Deploy a Render con variables de entorno
- [ ] Ingestión inicial knowledge base
- [ ] **ELIMINAR ESTE DOCUMENTO**

---

## 🔧 Configuración Inicial

### Variables de Entorno

```env
# Redis Cloud (Free Tier - 30MB)
REDIS_URL=redis://default:password@redis-xxxxx.c123.us-east-1-1.ec2.cloud.redislabs.com:12345

# Pinecone
PINECONE_API_KEY=xxxxx
PINECONE_ENVIRONMENT=us-west1-gcp
PINECONE_INDEX_NAME=rydercup-golf-rules

# OpenAI (ya configurado)
OPENAI_API_KEY=sk-xxxxx

# RAG Settings
RAG_CACHE_TTL=604800  # 7 días
RAG_ENABLE_CACHE=true
RAG_MAX_TOKENS=500
RAG_TEMPERATURE=0.3  # Respuestas consistentes
```

### Dependencias (requirements.txt)

```txt
langchain>=0.1.0
openai>=1.0.0
pinecone-client>=3.0.0
tiktoken>=0.5.0
redis>=4.5.0
```

### Registro de Servicios Externos

#### Redis Cloud (Free)
1. https://redis.com/try-free/ → Crear cuenta
2. Crear BD (Free: 30MB, 30 conexiones)
3. Copiar Redis URL (incluye password)
4. Añadir a variables de entorno

#### Pinecone (Free)
1. https://www.pinecone.io/ → Crear cuenta
2. Crear índice "rydercup-golf-rules":
   - Dimensión: 1536 (OpenAI embeddings)
   - Metric: cosine
   - Pod type: Starter (free)
3. Copiar API key y environment
4. Añadir a variables de entorno

---

## 📦 Semana 1: Domain Layer

### Estructura de Archivos

```
src/modules/ai/
├── domain/
│   ├── entities/
│   │   ├── document.py
│   │   └── query_result.py
│   ├── value_objects/
│   │   ├── document_id.py
│   │   └── embedding_vector.py
│   └── repositories/
│       ├── vector_repository.py
│       └── cache_repository.py
```

### Entities

**Document:** Documento embebido en knowledge base
- Campos: `id`, `content`, `source`, `metadata`, `embedding`
- Método: `embed(vector: List[float])`

**QueryResult:** Resultado de consulta RAG
- Campos: `answer`, `sources`, `confidence`, `cached`, `related_questions`

### Value Objects

**DocumentId:** UUID validado
- Validación: `uuid.UUID(value)` válido
- Método factory: `DocumentId.generate()`

**EmbeddingVector:** Vector 1536 dimensiones (OpenAI)
- Validación: Exactamente 1536 dimensiones
- Tipo: `List[float]`

### Repository Interfaces

**VectorRepositoryInterface:**
- `add_document(document)` - Añadir a knowledge base
- `search(query, top_k, language)` - Buscar relevantes
- `delete_document(document_id)` - Eliminar

**CacheRepositoryInterface:**
- `get(key)` - Obtener respuesta cacheada
- `set(key, value, ttl)` - Guardar en caché
- `delete(key)` - Eliminar del caché

---

## 📦 Semana 2: Application + Infrastructure

### DTOs

**QueryRequestDTO:**
```python
question: str (5-500 chars, validación anti-XSS)
competition_id: str (UUID)
language: str (default="es", pattern="^(es|en)$")
```

**QueryResponseDTO:**
```python
answer: str
sources: List[SourceDTO]
confidence: float
cached: bool
global_queries_remaining: int
competition_queries_remaining: int
is_competition_creator: bool
related_questions: Optional[List[str]]
```

### Ports (Interfaces)

**DailyQuotaServiceInterface:**
- `check_global_quota(user_id)` → QuotaCheck (10 consultas/día)
- `check_competition_quota(user_id, competition_id, daily_limit)` → QuotaCheck (3 o 6)
- `increment_global_quota(user_id)` → None
- `increment_competition_quota(user_id, competition_id)` → None

**LLMServiceInterface:**
- `generate_answer(question, context, language)` → str

**EmbeddingsServiceInterface:**
- `embed_text(text)` → List[float] (1536 dims)

### Use Case Principal: QueryGolfRulesUseCase

**Validaciones (en orden):**
1. Competición existe
2. Competición en estado IN_PROGRESS
3. Usuario inscrito o creador
4. Límite global (10 queries/día)
5. Límite por competición (3 user, 6 creator)
6. Intentar caché
7. Incrementar contadores
8. Buscar en knowledge base (top 3 documentos)
9. Generar respuesta con LLM
10. Cachear respuesta (7 días TTL)
11. Retornar QueryResponseDTO

### Infrastructure: RedisDailyQuotaService

**Estrategia de almacenamiento:**
- **Global:** `rag:daily:{user_id}:global` (límite 10)
- **Por competición:** `rag:daily:{user_id}:{competition_id}` (límite 3 o 6)
- **TTL:** Expira a medianoche UTC
- **Reset:** Automático diario

**QuotaCheck:** Retorna `can_query`, `queries_used`, `queries_remaining`

### Pre-FAQs Hardcodeadas

Ejemplos de FAQs para caché instantáneo:
- "cómo calcular handicap de juego"
- "reglas foursome"
- "qué es slope rating"
- "diferencia foursome fourball"
- "qué es match play"
- ... (15-25 preguntas más)

**Formato:**
```python
COMMON_GOLF_FAQS = {
    "pregunta": {
        "answer": "respuesta detallada",
        "sources": [{"document": "...", "page": X}]
    }
}
```

### Excepciones Custom

- `CompetitionNotFoundError` - Competición no encontrada
- `CompetitionNotInProgressError` - No está IN_PROGRESS
- `UserNotEnrolledError` - Usuario no inscrito
- `GlobalDailyLimitExceededError` - Límite global excedido (10)
- `CompetitionDailyLimitExceededError` - Límite por competición excedido

---

## 📦 Semana 3: API + Deploy

### API Endpoints

**POST `/api/v1/ai/assistant/query`**
- **Rate Limit:** 10/minuto (SlowAPI)
- **Auth:** Required (JWT)
- **Request:** QueryRequestDTO
- **Response:** QueryResponseDTO

**Códigos de Error:**
- `429 GLOBAL_DAILY_LIMIT_EXCEEDED` - 10 consultas globales alcanzadas
- `429 COMPETITION_DAILY_LIMIT_EXCEEDED` - Límite por competición alcanzado
- `403 COMPETITION_NOT_IN_PROGRESS` - Competición no activa
- `403 USER_NOT_ENROLLED` - Usuario no inscrito

### Script de Ingestión

**Ubicación:** `scripts/ingest_golf_rules.py`

**Documentos a ingerir (50 inicial):**
- R&A Rules 2023 (ES/EN)
- WHS Manual 2020 (ES)
- Ryder Cup Format Guide
- Local Rules Spain
- ... (más PDFs y Markdown)

**Proceso:**
1. Leer documentos desde `data/golf_rules/`
2. Chunking (500 tokens overlapping)
3. Generar embeddings (OpenAI)
4. Upload a Pinecone

### Dependency Injection

**Configurar en `src/config/dependencies.py`:**
```python
def get_query_golf_rules_use_case():
    redis_url = settings.REDIS_URL
    quota_service = RedisDailyQuotaService(redis_url)
    cache_repo = RedisCacheRepository(redis_url)
    vector_repo = PineconeRepository(...)
    llm_service = OpenAILLMService(...)

    return QueryGolfRulesUseCase(
        competition_repository=get_competition_repo(),
        enrollment_repository=get_enrollment_repo(),
        daily_quota_service=quota_service,
        cache_repository=cache_repo,
        vector_repository=vector_repo,
        llm_service=llm_service
    )
```

---

## ✅ Criterios de Completitud

Este documento puede **ELIMINARSE** cuando:

- [ ] Todas las 3 semanas estén completadas
- [ ] Tests pasando al 100% (85-110 tests totales)
- [ ] 50 documentos ingresados en Pinecone
- [ ] Deploy en Render realizado y funcionando
- [ ] Variables de entorno configuradas en producción
- [ ] Monitoreo activo (métricas de uso primeros 7 días)
- [ ] Documentación técnica actualizada en CLAUDE.md
- [ ] ADR-022 revisado y confirmado

---

## 📊 Métricas a Monitorear (primeros 30 días)

| Métrica | Objetivo |
|---------|----------|
| Cache hit rate | >80% |
| Latencia promedio | <2 seg |
| Queries/día por usuario | Validar límites (10 global, 3-6 comp) |
| Costo mensual OpenAI | <$5 |
| Feedback positivo | >90% |
| Memoria RAM Render | <400MB |

---

## 🔗 Referencias

### Documentación
- **ADR-022:** RAG Assistant Architecture (pendiente de crear)
- **CLAUDE.md:** Actualizar con RAG module
- **API.md:** Actualizar con endpoints de AI

### Stack Tecnológico
- **Pinecone:** https://docs.pinecone.io/
- **LangChain:** https://python.langchain.com/docs/
- **OpenAI API:** https://platform.openai.com/docs/
- **Redis:** https://redis.io/docs/

---

**Last Updated:** 8 January 2026
**Responsible:** Backend Team
**Status:** Temporary - Delete upon completing v1.11.0
