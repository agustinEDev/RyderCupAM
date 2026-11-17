# ADR-051: Standard Python Logging plus a Durable JSON Security Log

**Status:** Accepted (replaces ADR-008, removed)
**Date:** November 17, 2026
**Context:** Architecture - observability; Security - OWASP A09
**Author:** Agustín Estévez

---

## Context

ADR-008 introduced a logging framework of its own: a `Logger` interface, a
`LoggerFactory`, a `PythonLogger` implementation, text and structured formatters and a
handler for domain events. Most of it was never used beyond its own tests. It was removed
on 11-12 November 2026 (phase 5 of the quality plan), and ADR-047 later defined how the
security log is written. ADR-008 no longer described the code, so it was deleted.

## Decision

1. **Application logs use the standard library.** Every module takes its logger with
   `logging.getLogger(__name__)`. There is no custom logger interface or factory.
2. **The security log is the audit trail.** `security_logger` writes each security
   event (`src/shared/domain/events/security_events.py`) as one JSON line
   (`JsonFormatter`, the only class exported by `src/shared/infrastructure/logging`), to
   stdout and to its file. How it reaches Sentry, how emails are masked and which admin
   actions are audited is ADR-047.
3. **Unexpected errors** are logged once, with their trace, by the shared middleware that
   turns them into a 500 (ADR-049); Sentry's logging integration sends them.

## Consequences

- One way to log; nothing to inject.
- The audit trail has a stable format that can be searched and kept apart from the noise.
- Correlation across services is not provided; it would need a new decision.
