# ADR-049: Domain Errors Translated to HTTP in One Place

**Status:** Accepted
**Date:** November 12, 2026
**Context:** Architecture - Clean Architecture, code quality plan (phase 5); Security - OWASP A05
**Author:** Agustín Estévez

---

## Context

Every route translated its domain errors by hand:
`except X as e: raise HTTPException(status_code=..., detail=str(e))`. There were 349 of
these clauses in 25 route files. The same error was repeated in each endpoint (for
example `QuickMatchNotFoundError → 404` in every quick match route). A new endpoint
could forget one and answer 500 for an ordinary "not found".

## Decision

1. **One map per module.** Each module declares `CODIGOS: dict[type[Exception], int]` in
   `infrastructure/api/codigos_de_error.py` (shared errors in
   `src/shared/infrastructure/http/codigos_de_error_compartidos.py`). The composition root
   (`src/config/codigos_de_error.py`) joins them, and `main.py` registers one exception
   handler per error with `registra_los_codigos`. A class in two maps fails at startup.
2. **Same response as before.** The handler answers the mapped code and
   `{"detail": str(e)}`, exactly what `HTTPException` gave. Starlette picks the handler by
   the exception's MRO, so a subclass without its own code gets its closest parent's.
3. **What stays in the route.** An error is still translated in its route when that
   route gives it another code (`GolfCourseNotApprovedError`, `InvalidAvatarPresetError`),
   its own text, a `ValueError`, or more than a status (logging, `error_code`, headers),
   and when a later `except Exception` in the same `try` would otherwise turn it into 500.
4. **Guarded.** `tests/unit/shared/infrastructure/http/test_codigos_de_error_centrales.py`
   pins every error to the code it had in the routes, and fails if a route translates by
   hand an error the map already translates.

The 292 clauses that only repeated the map were removed with a script that simulated,
for each `try`, the code every caught class (and its subclasses) got before and after,
and removed a clause only when nothing changed.

## Consequences

- An error in the map that escapes a route which did not catch it now answers its 4xx
  instead of 500. This only fixes responses; no route that caught it changes.
- Adding a domain error that the client must see means adding it to its module's map,
  not a new `except` in each route.
- Errors read by text in `golf_course_routes` (`"not found" in str(e)`) are not covered
  here: they need typed errors first (phase 5, next PR).
