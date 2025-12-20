# ADR-022: RAG Chatbot para Asistente de Reglamento de Golf

**Fecha**: 6 de diciembre de 2025
**Estado**: Aceptado
**Decisores**: Equipo de desarrollo

## Contexto y Problema

Los usuarios tienen dudas frecuentes sobre reglas de golf durante competiciones. Responder manualmente es ineficiente y escala mal. Se necesita un asistente automatizado que:

- Responda preguntas sobre reglas oficiales (R&A/USGA)
- Explique formatos de juego (match play, foursome, fourball)
- Aclare conceptos de hándicap (WHS)
- Solo esté disponible durante competiciones activas (`IN_PROGRESS`)
- Tenga costo operacional mínimo (~$1-2/mes)

## Opciones Consideradas

1. **FAQ estático** - Documento con preguntas frecuentes
2. **Chatbot basado en reglas** - Árbol de decisiones predefinido
3. **RAG (Retrieval-Augmented Generation)** - LLM + vector database
4. **Fine-tuning de modelo** - Modelo especializado en reglas de golf

## Decisión

**Adoptamos RAG (Retrieval-Augmented Generation)** con el siguiente stack:

- **Vector DB**: Pinecone Free (100K vectores)
- **Embeddings**: OpenAI text-embedding-3-small
- **LLM**: OpenAI GPT-4o-mini
- **Cache**: Redis Cloud Free (30MB)
- **Integración**: Mismo backend FastAPI (no servicio separado)

## Justificación

### Ventajas de RAG:

1. **Costo mínimo**: $1-2/mes vs fine-tuning ($100-500/mes)
2. **Respuestas contextuales**: Cita fuentes exactas del reglamento
3. **Actualizable**: Añadir documentos sin reentrenar modelo
4. **Arquitectura simple**: 3 capas (Domain, Application, Infrastructure)
5. **Escalable**: Migrar a servicio separado si crece uso

### Limitaciones controladas:

- **Rate limiting de 3 niveles**:
  - Por minuto: 10 queries/min (anti-spam)
  - Global: 10 queries/día por usuario
  - Por competición: 3 (participante) / 6 (creador)

- **Caché agresivo**: 80% de queries cacheadas (TTL 7 días)
- **Pre-FAQs**: 20-30 preguntas hardcodeadas (0 costo)

## Consecuencias

### Positivas

- ✅ Reduce carga de soporte manual
- ✅ Disponible 24/7 durante competiciones
- ✅ Respuestas consistentes y verificables
- ✅ Costo predecible y controlado ($1/mes garantizado)
- ✅ Clean Architecture (testeable, mantenible)

### Negativas

- ⚠️ Depende de servicios externos (Pinecone, OpenAI)
- ⚠️ Latencia 1-2 seg (vs FAQ instantáneo)
- ⚠️ Requiere knowledge base bien curada (50 docs iniciales)

### Riesgos mitigados

- **Costo desbordado**: Límites diarios garantizan máximo $1/mes
- **Baja calidad**: Temperatura 0.3 + caché → respuestas consistentes
- **Abuso del sistema**: Rate limiting multi-nivel + requiere enrollment
- **Memoria Render**: No modelos locales (todo vía API, <200MB RAM)

## Detalles de Implementación

### Reglas de negocio

- Solo disponible si `competition.status == IN_PROGRESS`
- Usuario debe estar `APPROVED` o ser creador
- Respuestas cacheadas **SÍ** consumen cuota (previene abuso)

### Arquitectura

```
src/modules/ai/
├── domain/           # Entities, VOs, Interfaces
├── application/      # Use Cases, DTOs, Ports
└── infrastructure/   # Pinecone, Redis, OpenAI, API
```

### Ports principales

- `VectorRepositoryInterface` - Búsqueda en knowledge base
- `CacheServiceInterface` - Caché Redis (7 días TTL)
- `DailyQuotaServiceInterface` - Rate limiting dual-layer
- `LLMServiceInterface` - Generación de respuestas

### Proyección de costos

- 10 competiciones × 20 participantes × 50% uso = 345 queries/día
- Con caché 80% → 69 queries/día a OpenAI
- **Costo real: ~$0.50/mes**

## Alternativas rechazadas

### FAQ estático
- ❌ No contextual (no entiende intención del usuario)
- ❌ Difícil encontrar respuesta específica
- ✅ Gratis pero mala UX

### Chatbot basado en reglas
- ❌ Mantenimiento complejo (árbol de decisiones crece)
- ❌ No entiende lenguaje natural
- ✅ Costo $0 pero inflexible

### Fine-tuning
- ❌ Costo alto ($100-500/mes)
- ❌ Requiere reentrenar para actualizar
- ✅ Mayor precisión pero innecesario para MVP

## Referencias

- [OpenAI Embeddings Pricing](https://openai.com/pricing)
- [Pinecone Free Tier](https://www.pinecone.io/pricing/)
- [Redis Cloud Free Tier](https://redis.com/try-free/)
- ROADMAP.md - Sección "🤖 IA & RAG"

---

**Próxima revisión**: Después de v1.11.0 (evaluación de métricas reales)
