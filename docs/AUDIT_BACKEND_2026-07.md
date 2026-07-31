# Backend Security & Architecture Audit — July 2026

> Proactive full audit of the backend: dependency/security posture, Clean Architecture layering,
> and DDD compliance. No known incident triggered this review (see GitHub issue #106).

**Date**: 2026-07-26
**Scope**: `/Users/agustinestevezdominguez/Documents/RyderCupAm` @ `develop` (commit `cce8074`)
**Auditor**: Automated audit (Claude Code agent), manual verification of every finding below

---

## Executive Summary

No Critical or actively-exploitable findings were identified. The dependency surface is clean
(Snyk SCA: 92/92 dependencies, 0 vulnerable paths), secrets handling is correct, SQL injection
surface is effectively zero (ORM/Core `Table` + parametrized queries only, no raw/string-built
SQL), and the auth/authz stack (JWT + httpOnly cookies, CSRF triple-layer, rate limiting, RBAC
guards, bcrypt, account lockout, password history) is mature and consistently applied across
routes.

The Clean Architecture / DDD review found the codebase to be strong overall — Repository and
Unit-of-Work patterns are correctly split between `domain/` interfaces and
`infrastructure/persistence/` implementations across all four modules, and bounded contexts are
cleanly separated (cross-module references are limited to Value Object IDs, never full entity
imports). One **High** severity architecture finding stands out: the `User` aggregate (the
oldest module in the codebase, predating the DDD conventions later applied to `Competition` and
`GolfCourse`) uses fully public, mutable attributes instead of the private-attribute +
read-only-`@property` pattern used everywhere else. Three **Medium** findings and two **Low**
findings round out the report; none require urgent action, but the High and Mediums are tracked
as follow-up issues.

**Totals**: 0 Critical · 1 High · 3 Medium (issues opened) · 2 Low (documented only, no issue)

---

## Methodology

1. Read `CHANGELOG.md`, `ROADMAP.md`, `CLAUDE.md`, `README.md` (no `CONTRIBUTING.md` present) to
   learn documented conventions, architecture decisions (ADRs), and previously-known issues.
2. **Security pass**: Snyk SCA scan; manual review of auth/authz (JWT, cookies, CSRF, RBAC,
   rate limiting), secrets handling (`.env` tracking, hardcoded-secret grep), and input
   validation / SQL-injection surface (raw-query grep across `infrastructure/`).
3. **Architecture pass**: the 10 documented Clean Architecture rules were checked with targeted
   greps across `domain/`, `application/`, and `infrastructure/`, then verified by reading the
   actual source around every match before recording a finding.
4. **DDD pass**: reviewed aggregates/entities for anemic-model risk, Repository/UoW pattern
   placement, and bounded-context leakage.
5. Every finding below cites exact `file:line` and was confirmed by reading the referenced code,
   not by grep output alone.

---

## Findings

### High

#### H1 — `User` aggregate exposes fully public, mutable state (no encapsulation)

- **File**: `src/modules/user/domain/entities/user.py:100-117` (constructor) and throughout the
  class (e.g. `174-183`, `443-451`, `485-487`, `509-510`, `632-637`, `748-756`, `805`, `884-886`,
  `922-923`); also `src/modules/user/domain/entities/password_history.py:54-57`.
- **Description**: `User.__init__` assigns every field as a public attribute
  (`self.email = email`, `self.password = password`, `self.is_admin = is_admin`,
  `self.failed_login_attempts = failed_login_attempts`, …) with only one `@property`
  (`has_password`) in the entire class. This directly contradicts Clean Architecture rule #4
  ("Entity attributes are private (`_attr`) with read-only `@property` accessors — no public
  mutable state"). For contrast, `Competition` (15 `@property` accessors, 0 public attribute
  assignments) and `GolfCourse` (14 `@property` accessors) correctly follow the pattern, as do
  the other three entities in the same `user` module — `UserOAuthAccount` (6 properties),
  `RefreshToken` (8 properties), `UserDevice` (9 properties) — confirming `User` and
  `PasswordHistory` are legacy outliers, not the project norm.
- **Failure scenario**: because every field is a plain public attribute, any code with a
  reference to a `User` instance — a use case, an infrastructure mapper, a future contributor,
  a test helper — can do `user.is_admin = True`, `user.email = "attacker@x.com"`, or
  `user.failed_login_attempts = 0` directly, bypassing every domain invariant and every domain
  event the entity is supposed to emit (`UserPasswordChangedEvent`, `AccountUnlockedEvent`,
  etc.). **No such bypass currently exists** — a targeted search of `application/` and
  `infrastructure/` for direct assignment to these attributes outside `user.py` found none; all
  current call sites correctly go through the entity's own methods (`update_handicap()`,
  `change_password()`, …). The risk is entirely latent: the type system provides zero protection
  against a future regression.
- **Suggested fix**: refactor `User` and `PasswordHistory` to the private-attribute +
  `@property` pattern already used by every other entity in the codebase. The 501 existing User
  unit tests (per `CLAUDE.md`) provide strong regression coverage to do this safely; the
  SQLAlchemy mapper for `users` already relies on `composite()`/direct attribute mapping for
  `email`/`password` (`mappers.py:157-158`) and will need the property setters preserved for
  imperative mapping to keep working (same pattern `Competition` already uses successfully).

---

### Medium

#### M1 — WHS singles differential-handicap math lives in the use case, not the domain service

- **File**: `src/modules/competition/application/use_cases/generate_matches_use_case.py:746-758`
  (`_build_singles_match_players`).
- **Description**: the SINGLES match-generation path computes
  `diff = ph_a - ph_b` and branches (`if diff > 0 / elif diff < 0 / else`) to decide which
  player receives strokes, calling `calculator.compute_strokes_received()` directly from the use
  case. This is business logic (a WHS Match Play rule, already the subject of two production
  bugfixes — CHANGELOG `2.0.16`/`2.0.17`, "SINGLES WHS differential"), and it violates rule #2
  ("Business logic lives ONLY in domain entities/VOs/domain services — never in use cases"). The
  equivalent FOURBALL path in the same file (`_build_fourball_match_players`, lines 648-666)
  correctly delegates the analogous decision to a domain service method,
  `calculator.calculate_fourball_differential()`.
- **Risk**: the single most correctness-critical calculation in the scoring module (already
  fixed twice for bugs) is inconsistent across match formats and cannot be unit-tested in
  isolation from `GenerateMatchesUseCase`'s DTOs/mocks.
- **Suggested fix**: add `PlayingHandicapCalculator.calculate_singles_differential(ph_a, ph_b,
  holes_by_stroke_index) -> tuple[list[int], list[int]]`, mirroring the fourball method, and
  call it from the use case instead of the inline arithmetic.

#### M2 — `LocationBuilder` domain service instantiated inside use case constructors, not injected

- **File**: `src/modules/competition/application/use_cases/create_competition_use_case.py:62`
  and `update_competition_use_case.py:60` —
  `self._location_builder = LocationBuilder(self._uow.countries)`.
- **Description**: violates rule #5 ("Domain services are injected via DI, never instantiated
  inside use cases"). This is notable because `CLAUDE.md` documents a completed refactor (16 Nov
  2025, "Dependency Injection Refactoring… 100% Clean Architecture compliance") specifically to
  eliminate this pattern elsewhere in the codebase — these two call sites appear to predate or
  have been missed by that refactor.
- **Risk**: `LocationBuilder` cannot be mocked/substituted independently of the `UoW` in unit
  tests for these two use cases, and the inconsistency makes the DI convention harder to enforce
  by review/lint.
- **Suggested fix**: inject `LocationBuilder` as a constructor parameter wired from
  `dependencies.py`, same as every other domain service in the module.

#### M3 — `max_playing_handicap` cap duplicated between domain service and use case

- **File**: `src/modules/competition/application/use_cases/generate_matches_use_case.py:669-670`
  — `differential_phs = {k: min(v, max_playing_handicap) for k, v in differential_phs.items()}`.
- **Description**: per CHANGELOG `2.1.0`, `PlayingHandicapCalculator.calculate()` already applies
  the `max_playing_handicap` cap internally for the individual-handicap path. But the
  FOURBALL/FOURSOMES differential path calls `calculate_fourball_differential()` instead (which
  does not apply the cap), so the use case reimplements the same capping rule manually via a
  dict comprehension.
- **Risk**: two sources of truth for one business rule; a future change to capping behavior
  (e.g. rounding direction) can silently diverge between the singles/foursomes-individual path
  and the fourball-differential path.
- **Suggested fix**: move the cap into `calculate_fourball_differential()` (and the equivalent
  foursomes helper) so the use case never re-implements the rule.

---

### Low (documented only — no follow-up issue opened)

#### L1 — `Competition.status` / `Enrollment.status` mapped via `composite()` instead of `TypeDecorator`

- **File**: `src/modules/competition/infrastructure/persistence/sqlalchemy/mappers.py:703, 730,
  980-981, 1016-1017`.
- Both columns are plain `String(20)` at the `Table` level, converted to/from their
  `CompetitionStatus`/`EnrollmentStatus` enum VOs via SQLAlchemy `composite()` in the mapper
  properties. This is **not** a functional bug — type safety is preserved and rule #6 ("never
  plain string/int columns [for enum/VO fields] without a converter") is technically satisfied —
  but it contradicts the project's own documented convention in `CLAUDE.md`'s "Handicap Value
  Object Mapping" ADR ("TypeDecorator: VOs de una sola columna… Composite: VOs de múltiples
  columnas"), and is inconsistent with `RoundStatus`/`MatchStatus`/`InvitationStatus` in the same
  file, which correctly use dedicated `*StatusDecorator` `TypeDecorator` classes.
- Not filed as an issue: purely a style/consistency nitpick with no behavioral risk.

#### L2 — `bcrypt` imported directly in a domain Value Object

- **File**: `src/modules/user/domain/value_objects/password.py:24`.
- Technically violates the literal wording of rule #1 ("zero framework imports… no external
  libs beyond stdlib in `domain/`"), though hashing is arguably the entire responsibility of a
  `Password` VO and this is common, accepted practice in many DDD codebases. No behavioral risk
  identified.
- Not filed as an issue: if strict layer purity is desired later, this could be wrapped behind
  an `IPasswordHasher` port with an infrastructure adapter; otherwise worth an explicit note in
  `CLAUDE.md`'s architecture rules as an accepted exception.

---

## Checked — Preexisting / Already-Known Items (no new action needed)

- **5 accepted mypy errors in `golf_course_repository.py`** (tracked as issue #108, still open,
  P2/backlog): re-verified with `mypy src/ --ignore-missing-imports` from the project root —
  **0 errors reported** today, because `mypy.ini:66`
  (`[mypy-src.modules.*.infrastructure.persistence.*]`) already relaxes strictness for that
  glob. Consistent with the documented "accepted by config (exit 0)" state; issue #108 remains
  the correct tracking item for the underlying fix. No new issue opened.
- **`.snyk` permanent ignores for `setuptools`/`nltk`** (no `expires` field): confirmed present
  and unchanged in `.snyk` (reasons referencing CVE-2024-6345, CVE-2022-40897, CVE-2025-47273,
  CVE-2026-54293, CVE-2026-12243, CVE-2026-12252) — these are deliberate permanent pins
  (resolved via version upgrade, ignore kept only for historical CVE tracking), distinct from
  the 90-day-expiry Docker-base-image ignores added in `2.0.16`. No new action needed.
- **CVE-2024-23342 (`ecdsa` Minerva timing attack, transitive via `python-jose`)**: already
  documented and risk-accepted in `docs/KNOWN_SECURITY_ISSUES.md` — project uses HS256, not
  ECDSA algorithms, so the vulnerable code path is never exercised. Reviewed during this audit,
  still valid, no new action needed.

---

## Security Pass — Results (all clean)

- **Dependency audit**: `snyk test --file=requirements.txt --package-manager=pip
  --command=python3` → 92 dependencies tested, **0 vulnerable paths**.
- **Secrets handling**: `.env` confirmed untracked (`git ls-files` returns nothing for `.env`)
  and present in `.gitignore:20`; `git grep` for hardcoded secret/password/token literal
  assignments across tracked `.py` files returned no matches.
- **SQL injection surface**: no raw/string-formatted SQL found in `infrastructure/`; persistence
  is exclusively SQLAlchemy Core `Table` definitions + parametrized queries.
- **Auth/authz**: JWT (HS256) + httpOnly cookies, bcrypt (12 rounds prod / 4 rounds tests)
  password hashing, CSRF triple-layer protection (custom header + double-submit cookie +
  SameSite), rate limiting (SlowAPI), and RBAC guards (`require_admin`,
  `require_creator_or_admin`, `require_player_in_competition`) are used consistently across 13
  of 14 route files. The one route file without an auth dependency
  (`support_routes.py`) is intentionally public per its own module documentation (contact form,
  CSRF-exempt, rate-limited 3/h/IP) — not a gap.
- **Password policy**: 12-char minimum, complexity rules, common-password blacklist, 5-entry
  password history, account lockout after 10 failed attempts with 30-minute auto-unlock.

## DDD Pass — Results

- **Repository Pattern**: interfaces consistently defined under `domain/repositories/`, with
  SQLAlchemy + in-memory implementations under `infrastructure/persistence/`, for all four
  modules (`user`, `competition`, `golf_course`, `shared`/country) — no leaks found.
- **Unit of Work**: dedicated `*UnitOfWorkInterface` in `domain/`, concrete SQLAlchemy/in-memory
  implementations in `infrastructure/`, one per module — confirmed present for all four modules.
- **Anemic model check**: `Competition`, `GolfCourse`, `User`, `Round`, `Match`, `Enrollment` all
  carry real behavior (state machines, validation, calculators) — none are pure data holders.
  (Note: `User`'s H1 finding is an encapsulation defect, not anemia — the entity still has rich
  methods, it's the *attributes* that leak.)
- **Bounded contexts**: modules are cleanly separated; cross-module references are limited to
  Value Object IDs (`UserId`, `GolfCourseId`, `CountryCode`) rather than full entity imports —
  confirmed via a full grep of non-relative imports across every `domain/` package.

---

## Follow-up Issues Opened

| Issue | Severity | Priority | Title |
|-------|----------|----------|-------|
| [#109](https://github.com/agustinEDev/RyderCupAM/issues/109) | High   | P1       | `User` aggregate exposes public mutable state instead of private attrs + properties |
| [#110](https://github.com/agustinEDev/RyderCupAM/issues/110) | Medium | P2       | Extract SINGLES WHS differential handicap logic into `PlayingHandicapCalculator` |
| [#111](https://github.com/agustinEDev/RyderCupAM/issues/111) | Medium | P2       | Inject `LocationBuilder` via DI instead of instantiating it inside use case constructors |
| [#112](https://github.com/agustinEDev/RyderCupAM/issues/112) | Medium | P2       | De-duplicate `max_playing_handicap` cap between domain service and use case |
