# ADR-022: RAG Chatbot for Golf Rules Assistant

**Date**: December 6, 2025
**Status**: Accepted
**Decision Makers**: Development Team

## Context and Problem

Users have frequent questions about golf rules during competitions. Answering manually is inefficient and scales poorly. We need an automated assistant that:

- Answers questions about official rules (R&A/USGA)
- Explains game formats (match play, foursome, fourball)
- Clarifies handicap concepts (WHS)
- Only available during active competitions (`IN_PROGRESS`)
- Has minimal operational cost (~$1-2/month)

## Options Considered

1. **Static FAQ** - Document with frequent questions
2. **Rule-based chatbot** - Predefined decision tree
3. **RAG (Retrieval-Augmented Generation)** - LLM + vector database
4. **Model fine-tuning** - Model specialized in golf rules

## Decision

**We adopt RAG (Retrieval-Augmented Generation)** with the following stack:

- **Vector DB**: Pinecone Free (100K vectors)
- **Embeddings**: OpenAI text-embedding-3-small
- **LLM**: OpenAI GPT-4o-mini
- **Cache**: Redis Cloud Free (30MB)
- **Integration**: Same FastAPI backend (not separate service)

## Justification

### RAG Advantages:

1. **Minimal cost**: $1-2/month vs fine-tuning ($100-500/month)
2. **Contextual answers**: Cites exact sources from regulations
3. **Updatable**: Add documents without retraining model
4. **Simple architecture**: 3 layers (Domain, Application, Infrastructure)
5. **Scalable**: Migrate to separate service if usage grows

### Controlled limitations:

- **3-tier rate limiting**:
  - Per minute: 10 queries/min (anti-spam)
  - Global: 10 queries/day per user
  - Per competition: 3 (participant) / 6 (creator)

- **Aggressive cache**: 80% of queries cached (TTL 7 days)
- **Pre-FAQs**: 20-30 hardcoded questions (0 cost)

## Consequences

### Positive

- ✅ Reduces manual support load
- ✅ Available 24/7 during competitions
- ✅ Consistent and verifiable answers
- ✅ Predictable and controlled cost ($1/month guaranteed)
- ✅ Clean Architecture (testable, maintainable)

### Negative

- ⚠️ Depends on external services (Pinecone, OpenAI)
- ⚠️ Latency 1-2 sec (vs instant FAQ)
- ⚠️ Requires well-curated knowledge base (50 initial docs)

### Mitigated risks

- **Runaway cost**: Daily limits guarantee maximum $1/month
- **Low quality**: Temperature 0.3 + cache → consistent answers
- **System abuse**: Multi-level rate limiting + requires enrollment
- **Render memory**: No local models (all via API, <200MB RAM)

## Implementation Details

### Business Rules

- Only available if `competition.status == IN_PROGRESS`
- User must be `APPROVED` or be creator
- Cached responses **DO** consume quota (prevents abuse)

### Architecture

Clean Architecture with 3 layers (domain/application/infrastructure) implementing ports: `VectorRepositoryInterface` (knowledge base), `CacheServiceInterface` (Redis 7-day TTL), `DailyQuotaServiceInterface` (rate limiting), `LLMServiceInterface` (generation).

### Cost projection

- 10 competitions × 20 participants × 50% usage = 345 queries/day
- With 80% cache → 69 queries/day to OpenAI
- **Real cost: ~$0.50/month**

## Rejected Alternatives

- **Static FAQ**: Free but not contextual, poor UX
- **Rule-based chatbot**: $0 cost but inflexible, complex maintenance
- **Fine-tuning**: Higher accuracy but costly ($100-500/month), requires retraining

## References

- [OpenAI Embeddings Pricing](https://openai.com/pricing)
- [Pinecone Free Tier](https://www.pinecone.io/pricing/)
- [Redis Cloud Free Tier](https://redis.com/try-free/)
- ROADMAP.md - Section "🤖 AI & RAG"

---

**Next review**: After v1.11.0 (evaluation of real metrics)
