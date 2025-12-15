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

### 1. Variables de Entorno

```bash
# .env y Render Environment Variables

# Redis Cloud (Free Tier - 30MB)
REDIS_URL=redis://default:password@redis-xxxxx.c123.us-east-1-1.ec2.cloud.redislabs.com:12345

# Pinecone
PINECONE_API_KEY=xxxxx
PINECONE_ENVIRONMENT=us-west1-gcp
PINECONE_INDEX_NAME=rydercup-golf-rules

# OpenAI
OPENAI_API_KEY=sk-xxxxx

# RAG Settings
RAG_CACHE_TTL=604800  # 7 días
RAG_ENABLE_CACHE=true
RAG_MAX_TOKENS=500
RAG_TEMPERATURE=0.3  # Respuestas consistentes
```

### 2. Dependencias (requirements.txt)

```txt
# RAG Module
langchain>=0.1.0
openai>=1.0.0
pinecone-client>=3.0.0
tiktoken>=0.5.0
redis>=4.5.0
```

### 3. Registro de Servicios Externos

#### Redis Cloud (Free)
1. Ir a https://redis.com/try-free/
2. Crear cuenta gratuita
3. Crear base de datos (Free Tier: 30MB, 30 conexiones)
4. Copiar Redis URL (incluye password)
5. Añadir a variables de entorno

#### Pinecone (Free)
1. Ir a https://www.pinecone.io/
2. Crear cuenta gratuita
3. Crear índice "rydercup-golf-rules":
   - Dimensión: 1536 (OpenAI embeddings)
   - Metric: cosine
   - Pod type: Starter (free)
4. Copiar API key y environment
5. Añadir a variables de entorno

#### OpenAI (ya configurado)
- Usar misma API key existente del proyecto
- Monitorear uso en dashboard

---

## 📦 Semana 1: Domain Layer

### Estructura de Archivos

```
src/modules/ai/
├── __init__.py
├── domain/
│   ├── __init__.py
│   ├── entities/
│   │   ├── __init__.py
│   │   ├── document.py
│   │   └── query_result.py
│   ├── value_objects/
│   │   ├── __init__.py
│   │   ├── document_id.py
│   │   └── embedding_vector.py
│   └── repositories/
│       ├── __init__.py
│       ├── vector_repository.py
│       └── cache_repository.py
```

### 1. Entities

```python
# src/modules/ai/domain/entities/document.py
from dataclasses import dataclass
from typing import List
from ..value_objects.document_id import DocumentId
from ..value_objects.embedding_vector import EmbeddingVector

@dataclass
class Document:
    """Documento embebido en el knowledge base"""
    id: DocumentId
    content: str
    source: str  # Nombre del archivo fuente
    metadata: dict  # page, section, language, etc.
    embedding: EmbeddingVector | None = None

    def embed(self, vector: List[float]) -> None:
        """Asigna embedding al documento"""
        self.embedding = EmbeddingVector(vector)
```

```python
# src/modules/ai/domain/entities/query_result.py
from dataclasses import dataclass
from typing import List

@dataclass
class Source:
    document: str
    page: int | None
    section: str | None
    relevance: float

@dataclass
class QueryResult:
    """Resultado de una consulta RAG"""
    answer: str
    sources: List[Source]
    confidence: float
    cached: bool
    related_questions: List[str] | None = None
```

### 2. Value Objects

```python
# src/modules/ai/domain/value_objects/document_id.py
from dataclasses import dataclass
import uuid

@dataclass(frozen=True)
class DocumentId:
    value: str

    def __post_init__(self):
        try:
            uuid.UUID(self.value)
        except ValueError:
            raise ValueError(f"Invalid DocumentId: {self.value}")

    @classmethod
    def generate(cls) -> 'DocumentId':
        return cls(str(uuid.uuid4()))
```

```python
# src/modules/ai/domain/value_objects/embedding_vector.py
from dataclasses import dataclass
from typing import List

@dataclass(frozen=True)
class EmbeddingVector:
    """Vector de embeddings (1536 dimensiones para OpenAI)"""
    values: List[float]

    def __post_init__(self):
        if len(self.values) != 1536:
            raise ValueError(f"Expected 1536 dimensions, got {len(self.values)}")
```

### 3. Repository Interfaces

```python
# src/modules/ai/domain/repositories/vector_repository.py
from abc import ABC, abstractmethod
from typing import List
from ..entities.document import Document
from ..entities.query_result import Source

class VectorRepositoryInterface(ABC):
    @abstractmethod
    async def add_document(self, document: Document) -> None:
        """Añade documento al knowledge base"""
        pass

    @abstractmethod
    async def search(
        self,
        query: str,
        top_k: int = 3,
        language: str = "es"
    ) -> List[Source]:
        """Busca documentos relevantes para la query"""
        pass

    @abstractmethod
    async def delete_document(self, document_id: str) -> None:
        """Elimina documento del knowledge base"""
        pass
```

```python
# src/modules/ai/domain/repositories/cache_repository.py
from abc import ABC, abstractmethod
from typing import Dict, Any

class CacheRepositoryInterface(ABC):
    @abstractmethod
    async def get(self, key: str) -> Dict[str, Any] | None:
        """Obtiene respuesta cacheada"""
        pass

    @abstractmethod
    async def set(self, key: str, value: Dict[str, Any], ttl: int) -> None:
        """Guarda respuesta en caché"""
        pass

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Elimina del caché"""
        pass
```

---

## 📦 Semana 2: Application + Infrastructure

### Application Layer - DTOs

```python
# src/modules/ai/application/dto/query_request_dto.py
from pydantic import BaseModel, Field, validator

class QueryRequestDTO(BaseModel):
    question: str = Field(..., min_length=5, max_length=500)
    competition_id: str = Field(..., description="UUID de la competición")
    language: str = Field(default="es", pattern="^(es|en)$")

    @validator('question')
    def sanitize_question(cls, v):
        if '<' in v or '>' in v:
            raise ValueError('Question cannot contain HTML tags')
        return v.strip()
```

```python
# src/modules/ai/application/dto/query_response_dto.py
from pydantic import BaseModel
from typing import List, Optional

class SourceDTO(BaseModel):
    document: str
    page: Optional[int]
    section: Optional[str]

class QueryResponseDTO(BaseModel):
    answer: str
    sources: List[SourceDTO]
    confidence: float
    cached: bool
    global_queries_remaining: int
    competition_queries_remaining: int
    is_competition_creator: bool
    related_questions: Optional[List[str]] = None
```

### Application Layer - Ports

```python
# src/modules/ai/application/ports/daily_quota_service_interface.py
from dataclasses import dataclass
from abc import ABC, abstractmethod

@dataclass
class QuotaCheck:
    can_query: bool
    queries_used: int
    queries_remaining: int

class DailyQuotaServiceInterface(ABC):
    @abstractmethod
    async def check_global_quota(self, user_id: str) -> QuotaCheck:
        """Verifica límite global de 10 consultas/día"""
        pass

    @abstractmethod
    async def check_competition_quota(
        self, user_id: str, competition_id: str, daily_limit: int
    ) -> QuotaCheck:
        """Verifica límite por competición (3 o 6)"""
        pass

    @abstractmethod
    async def increment_global_quota(self, user_id: str) -> None:
        """Incrementa contador global"""
        pass

    @abstractmethod
    async def increment_competition_quota(
        self, user_id: str, competition_id: str
    ) -> None:
        """Incrementa contador por competición"""
        pass
```

```python
# src/modules/ai/application/ports/llm_service_interface.py
from abc import ABC, abstractmethod
from typing import List
from ..dto.query_response_dto import SourceDTO

class LLMServiceInterface(ABC):
    @abstractmethod
    async def generate_answer(
        self,
        question: str,
        context: List[SourceDTO],
        language: str = "es"
    ) -> str:
        """Genera respuesta usando LLM"""
        pass
```

### Application Layer - Use Case Principal

```python
# src/modules/ai/application/use_cases/query_golf_rules_use_case.py
from ..dto.query_request_dto import QueryRequestDTO
from ..dto.query_response_dto import QueryResponseDTO
from ...domain.repositories.vector_repository import VectorRepositoryInterface
from ...domain.repositories.cache_repository import CacheRepositoryInterface
from ..ports.daily_quota_service_interface import DailyQuotaServiceInterface
from ..ports.llm_service_interface import LLMServiceInterface

class QueryGolfRulesUseCase:
    def __init__(
        self,
        competition_repository,  # From competition module
        enrollment_repository,   # From enrollment module
        daily_quota_service: DailyQuotaServiceInterface,
        cache_repository: CacheRepositoryInterface,
        vector_repository: VectorRepositoryInterface,
        llm_service: LLMServiceInterface,
    ):
        self._competitions = competition_repository
        self._enrollments = enrollment_repository
        self._quota = daily_quota_service
        self._cache = cache_repository
        self._vector = vector_repository
        self._llm = llm_service

    async def execute(
        self,
        request: QueryRequestDTO,
        current_user_id: str
    ) -> QueryResponseDTO:
        # 1. Validar competición existe y está IN_PROGRESS
        competition = await self._competitions.find_by_id(request.competition_id)
        if not competition:
            raise CompetitionNotFoundError()

        if competition.status != CompetitionStatus.IN_PROGRESS:
            raise CompetitionNotInProgressError()

        # 2. Validar usuario inscrito o creador
        is_creator = competition.creator_id.value == current_user_id
        if not is_creator:
            enrollment = await self._enrollments.exists_for_user_in_competition(
                user_id=current_user_id,
                competition_id=request.competition_id
            )
            if not enrollment or enrollment.status != EnrollmentStatus.APPROVED:
                raise UserNotEnrolledError()

        # 3. Verificar límite global (10 queries/día)
        global_quota = await self._quota.check_global_quota(current_user_id)
        if not global_quota.can_query:
            raise GlobalDailyLimitExceededError()

        # 4. Verificar límite por competición (3 o 6)
        daily_limit = 6 if is_creator else 3
        competition_quota = await self._quota.check_competition_quota(
            user_id=current_user_id,
            competition_id=request.competition_id,
            daily_limit=daily_limit
        )
        if not competition_quota.can_query:
            raise CompetitionDailyLimitExceededError()

        # 5. Intentar responder desde caché
        cached_response = await self._cache.get(request.question)
        if cached_response:
            return QueryResponseDTO(
                **cached_response,
                cached=True,
                global_queries_remaining=global_quota.queries_remaining,
                competition_queries_remaining=competition_quota.queries_remaining,
                is_competition_creator=is_creator
            )

        # 6. Incrementar contadores (cuenta incluso si hay cache miss)
        await self._quota.increment_global_quota(current_user_id)
        await self._quota.increment_competition_quota(
            current_user_id, request.competition_id
        )

        # 7. Buscar en knowledge base
        relevant_sources = await self._vector.search(
            query=request.question,
            top_k=3,
            language=request.language
        )

        # 8. Generar respuesta con LLM
        answer = await self._llm.generate_answer(
            question=request.question,
            context=relevant_sources,
            language=request.language
        )

        # 9. Cachear respuesta
        response_dict = {
            "answer": answer,
            "sources": [s.dict() for s in relevant_sources],
            "confidence": 0.9,  # Calculado por LLM
        }
        await self._cache.set(request.question, response_dict, ttl=604800)

        # 10. Retornar respuesta
        return QueryResponseDTO(
            answer=answer,
            sources=relevant_sources,
            confidence=0.9,
            cached=False,
            global_queries_remaining=global_quota.queries_remaining - 1,
            competition_queries_remaining=competition_quota.queries_remaining - 1,
            is_competition_creator=is_creator
        )
```

### Infrastructure Layer - DailyQuotaService

```python
# src/modules/ai/infrastructure/quota/redis_daily_quota_service.py
from datetime import datetime, timezone, timedelta
from redis import Redis
from ...application.ports.daily_quota_service_interface import (
    DailyQuotaServiceInterface,
    QuotaCheck
)

class RedisDailyQuotaService(DailyQuotaServiceInterface):
    GLOBAL_LIMIT = 10

    def __init__(self, redis_url: str):
        self.client = Redis.from_url(redis_url, decode_responses=True)

    async def check_global_quota(self, user_id: str) -> QuotaCheck:
        key = f"rag:daily:{user_id}:global"
        queries_used = int(self.client.get(key) or 0)

        return QuotaCheck(
            can_query=queries_used < self.GLOBAL_LIMIT,
            queries_used=queries_used,
            queries_remaining=max(0, self.GLOBAL_LIMIT - queries_used)
        )

    async def check_competition_quota(
        self, user_id: str, competition_id: str, daily_limit: int
    ) -> QuotaCheck:
        key = f"rag:daily:{user_id}:{competition_id}"
        queries_used = int(self.client.get(key) or 0)

        return QuotaCheck(
            can_query=queries_used < daily_limit,
            queries_used=queries_used,
            queries_remaining=max(0, daily_limit - queries_used)
        )

    async def increment_global_quota(self, user_id: str) -> None:
        key = f"rag:daily:{user_id}:global"
        self.client.incr(key)

        if self.client.ttl(key) == -1:
            seconds_until_midnight = self._seconds_until_midnight()
            self.client.expire(key, seconds_until_midnight)

    async def increment_competition_quota(
        self, user_id: str, competition_id: str
    ) -> None:
        key = f"rag:daily:{user_id}:{competition_id}"
        self.client.incr(key)

        if self.client.ttl(key) == -1:
            seconds_until_midnight = self._seconds_until_midnight()
            self.client.expire(key, seconds_until_midnight)

    def _seconds_until_midnight(self) -> int:
        now = datetime.now(timezone.utc)
        tomorrow = now.replace(
            hour=0, minute=0, second=0, microsecond=0
        ) + timedelta(days=1)
        return int((tomorrow - now).total_seconds())
```

### Pre-FAQs Hardcodeadas

```python
# src/modules/ai/domain/common_faqs.py
COMMON_GOLF_FAQS = {
    "cómo calcular handicap de juego": {
        "answer": "El hándicap de juego se calcula aplicando un porcentaje de allowance al hándicap de curso según el formato. Stroke play: 100%, match play: 100%, foursome: 50% combinado, fourball: 85-90%.",
        "sources": [{"document": "WHS_2020", "page": 10, "section": "Playing Handicap"}]
    },
    "reglas foursome": {
        "answer": "En foursome (alternate shot), dos jugadores de un equipo juegan una sola bola alternándose. Un jugador hace el drive en hoyos impares, el otro en pares, luego se alternan hasta embocar.",
        "sources": [{"document": "Ryder_Cup_Format", "section": "Formats"}]
    },
    "qué es slope rating": {
        "answer": "El Slope Rating mide la dificultad de un campo para jugadores no scratch (hándicap 0). Va de 55 a 155, siendo 113 el estándar. Mayor slope = más difícil para jugadores con hándicap alto.",
        "sources": [{"document": "WHS_2020", "page": 5}]
    },
    "diferencia foursome fourball": {
        "answer": "Foursome: 2 jugadores, 1 bola, se alternan golpes. Fourball: 2 jugadores, 2 bolas, cuenta la mejor puntuación del equipo.",
        "sources": [{"document": "Ryder_Cup_Format", "section": "Formats"}]
    },
    "qué es match play": {
        "answer": "Match play es un formato donde ganas hoyos, no cuentas golpes totales. Ganas un hoyo si completas en menos golpes que tu oponente. Gana quien gana más hoyos.",
        "sources": [{"document": "R&A_Rules", "page": 45}]
    },
    # ... 15-25 preguntas más
}
```

### Excepciones Custom

```python
# src/modules/ai/domain/exceptions.py
class CompetitionNotFoundError(Exception):
    """Competición no encontrada"""
    pass

class CompetitionNotInProgressError(Exception):
    """Competición no está en estado IN_PROGRESS"""
    def __init__(self, current_status: str):
        self.current_status = current_status
        super().__init__(f"Competition is {current_status}, not IN_PROGRESS")

class UserNotEnrolledError(Exception):
    """Usuario no inscrito en la competición"""
    pass

class GlobalDailyLimitExceededError(Exception):
    """Límite global de 10 consultas/día excedido"""
    pass

class CompetitionDailyLimitExceededError(Exception):
    """Límite de consultas por competición excedido"""
    def __init__(self, queries_used: int, daily_limit: int):
        self.queries_used = queries_used
        self.daily_limit = daily_limit
        super().__init__(f"Exceeded {daily_limit} daily queries")
```

---

## 📦 Semana 3: API + Deploy

### API Routes

```python
# src/modules/ai/infrastructure/api/routes.py
from fastapi import APIRouter, Depends, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from ...application.use_cases.query_golf_rules_use_case import QueryGolfRulesUseCase
from ...application.dto.query_request_dto import QueryRequestDTO

router = APIRouter(prefix="/api/v1/ai", tags=["AI Assistant"])
limiter = Limiter(key_func=get_remote_address)

@router.post("/assistant/query")
@limiter.limit("10/minute")
async def query_assistant(
    request: Request,
    query: QueryRequestDTO,
    current_user: dict = Depends(get_current_user),
    use_case: QueryGolfRulesUseCase = Depends(get_query_golf_rules_use_case)
):
    try:
        result = await use_case.execute(query, current_user["id"])
        return result
    except GlobalDailyLimitExceededError as e:
        raise HTTPException(status_code=429, detail={
            "code": "GLOBAL_DAILY_LIMIT_EXCEEDED",
            "message": "Has alcanzado el límite global de 10 consultas diarias"
        })
    except CompetitionDailyLimitExceededError as e:
        raise HTTPException(status_code=429, detail={
            "code": "COMPETITION_DAILY_LIMIT_EXCEEDED",
            "message": f"Has alcanzado el límite de {e.daily_limit} consultas para esta competición"
        })
    except CompetitionNotInProgressError as e:
        raise HTTPException(status_code=403, detail={
            "code": "COMPETITION_NOT_IN_PROGRESS",
            "message": "Las consultas solo están disponibles durante la competición",
            "current_status": e.current_status
        })
    except UserNotEnrolledError:
        raise HTTPException(status_code=403, detail={
            "code": "USER_NOT_ENROLLED",
            "message": "Debes estar inscrito en la competición"
        })
```

### Script de Ingestión de Documentos

```python
# scripts/ingest_golf_rules.py
import asyncio
from pathlib import Path
from src.modules.ai.infrastructure.vector_db.pinecone_repository import PineconeRepository
from src.modules.ai.infrastructure.embeddings.openai_embeddings import OpenAIEmbeddings

async def ingest_documents():
    """Carga documentos iniciales al knowledge base"""

    docs_path = Path("data/golf_rules")

    # Lista de documentos a ingerir
    documents = [
        "R&A_Rules_2023_ES.pdf",
        "R&A_Rules_2023_EN.pdf",
        "WHS_Manual_2020_ES.pdf",
        "Ryder_Cup_Format.md",
        "Local_Rules_Spain.md",
        # ... más documentos
    ]

    embeddings_service = OpenAIEmbeddings()
    vector_repo = PineconeRepository()

    for doc_file in documents:
        print(f"Processing {doc_file}...")
        # Leer, chunking, embeddings, upload
        # ...

    print(f"✅ Ingested {len(documents)} documents")

if __name__ == "__main__":
    asyncio.run(ingest_documents())
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

- Cache hit rate (objetivo: >80%)
- Latencia promedio (objetivo: <2 seg)
- Queries/día por usuario (validar límites)
- Costo mensual OpenAI (objetivo: <$5)
- Feedback positivo (objetivo: >90%)
- Memoria RAM Render (objetivo: <400MB)

---

**Última actualización:** 6 Dic 2025
**Responsable:** Backend Team
