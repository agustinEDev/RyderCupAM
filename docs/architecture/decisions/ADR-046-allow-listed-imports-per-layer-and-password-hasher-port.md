# ADR-046: Allow-Listed Imports per Layer and a PasswordHasher Port

**Status:** Accepted
**Date:** November 9, 2026
**Context:** Architecture - Clean Architecture dependency rule; Security - OWASP A02, A05
**Author:** Agustín Estévez
**Amends:** ADR-002 (bcrypt cost), ADR-003 (fast hashing in tests)

---

## Context

The architecture audit of 9 Nov 2026 found three leaks that `lint-imports` did not
report: a use case importing SQLAlchemy and matching an index name, the `Password`
value object importing `bcrypt` and reading `TESTING` to pick its cost, and the
domain depending on `src/shared/security`, a package outside every layer contract.
The contracts only forbade a fixed list of frameworks, so anything not on the list
passed, and packages outside `domain/application/infrastructure` were never checked.

## Decision

1. **Allow-list, not deny-list.** `tests/unit/architecture/test_imports_permitidos_por_capa.py`
   lists what `domain` and `application` may import:
   - side-effect free standard library (data, time, text, numbers, pure crypto);
   - `logging` in both layers: diagnostic warnings stay where they are detected;
   - `email_validator` in the domain (pure, no network);
   - Pydantic and `geojson_pydantic` in application: DTOs are Pydantic by project
     decision, and this ADR records it;
   - asyncio and friends in application, to coordinate, never to do I/O.
   Anything else, including `__import__`, `eval` and `exec`, fails the unit suite.
   Adding to the list is an architecture decision, made in review.
2. **Every package is a layer.** Each sub-package of a module or of `src/shared` must be
   `domain`, `application` or `infrastructure`, so no code escapes the contracts.
3. **Frameworks out of application.** A new import-linter contract forbids SQLAlchemy,
   FastAPI, Starlette, asyncpg, bcrypt, jwt, httpx, PIL, sentry_sdk and alembic in every
   application layer, including indirect imports; the domain contract forbids the same.
4. **Passwords go through a port.** The domain defines `PasswordHasher`; the bcrypt
   adapter lives in `user/infrastructure/security` and the composition root installs one
   per process (`src/config/contrasenas.py`), also from scripts that create users.
   Without an installed hasher, creating or checking a password raises: it fails closed.
5. **The cost is configuration.** `BCRYPT_ROUNDS` sets the bcrypt cost: 12 when unset,
   mistyped or outside 4-15. Fewer than 12 is accepted only with
   `ENVIRONMENT=development` (local, Kind, tests, which set 4); anywhere else, including
   an unset or unknown `ENVIRONMENT`, the app refuses to start. `TESTING` no longer
   changes the cost.
6. **Database errors are translated in infrastructure.** A unique violation that means
   something in the domain (the alias index) becomes the domain error in the unit of
   work, on commit, flush or an autoflush inside the block, as the social module
   already did for friendships.

## Consequences

- The three leaks are fixed, and the same kind of leak now fails CI.
- One process-wide hasher instead of injecting it in every call: `Password` is built in
  many places and the algorithm does not change between requests. Tests that swap it
  restore the previous one and clear the dummy-hash cache.
- A stray `TESTING` in a deploy can no longer make new hashes 256 times cheaper.
- Pending, outside this ADR: application code still reads some `src.config` modules
  (CSRF settings, password-reset settings); deciding whether to inject those values
  instead is tracked separately.
