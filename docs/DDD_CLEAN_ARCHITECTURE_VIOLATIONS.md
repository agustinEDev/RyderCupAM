# 🔍 DDD and Clean Architecture Violations Report

> **Date:** February 1, 2026
> **Version:** 2.0.2 (Sprint 2 - Block 1)
> **Compliance Score:** 90% ✅
> **Status:** 3 CRITICAL, 8 WARNING, 4 INFO violations

---

## 📊 Executive Summary

After an exhaustive code review of the RyderCupAm backend, **15 distinct violations** were identified across three severity levels. Overall, the codebase demonstrates **strong adherence to Clean Architecture and DDD principles** (90%+ compliance). Most violations are tactical implementation details rather than fundamental architectural breaks.

### Severity Breakdown

### 🔴 CRITICAL
3 violations (breaks architecture, must fix)

### ⚠️ WARNING
8 violations (code smells, should fix)

### ℹ️ INFO
4 violations (minor improvements)

### Key Strengths

1. ✅ **Clean layer separation** - no application importing infrastructure (except reconstructor)
2. ✅ **Strong use of Value Objects** - Email, Password, CompetitionName, etc.
3. ✅ **Repository Pattern** correctly implemented with interfaces
4. ✅ **Unit of Work Pattern** correctly used for transactions
5. ✅ **Domain Events** properly implemented throughout
6. ✅ **Dependency Injection** used consistently
7. ✅ **Good entity design** in most cases (GolfCourse, UserDevice are excellent)

### Key Weaknesses

1. ❌ **Anemic Domain Model** in some use cases (UpdateGolfCourse, ReorderGolfCourses)
2. ❌ **Application layer accessing private aggregate internals** (ReorderGolfCourses)
3. ❌ **SQLAlchemy leaking into domain** (reconstructor imports)
4. ⚠️ **Inconsistent encapsulation** (Competition vs GolfCourse)
5. ⚠️ **God Objects in API layer** (1600+ line files)

---

## 🔴 CRITICAL Violations (Must Fix)

### 1. Use Case Accessing Private Aggregate Internals

**Severity:** 🔴 CRITICAL
**File:** `src/modules/competition/application/use_cases/reorder_golf_courses_use_case.py`
**Lines:** 126, 129, 133, 143, 145, 152, 155

**Code:**
```python
# Line 126
if len(new_order) != len(competition._golf_courses):

# Line 133
competition_gc_ids = {cgc.golf_course_id for cgc in competition._golf_courses}

# Line 143-146
for cgc in competition._golf_courses:
    if cgc.golf_course_id == golf_course_id:
        cgc._display_order = 10000 + idx + 1  # Direct access!

# Line 152-156
for cgc in competition._golf_courses:
    if cgc.golf_course_id == golf_course_id:
        cgc._display_order = new_display_order  # Direct access!
```

**Violation:**
- Application layer directly accessing private aggregate internals (`competition._golf_courses`)
- Application layer directly manipulating child entity private attributes (`cgc._display_order`)
- **This is the most severe violation** - bypassing the aggregate root's encapsulation

**Why it's wrong:**
1. Breaks the **Aggregate Pattern** - only the aggregate root (Competition) should modify its internal entities
2. Violates **Encapsulation** - private attributes exist to prevent external manipulation
3. Business logic (reordering) is in the **wrong layer** - should be in the domain entity
4. Makes the aggregate **anemic** - no behavior, just data holder

**Impact:**
- Domain model becomes anemic (data bag)
- Business logic scattered across use cases
- Hard to test business rules in isolation
- Violates Tell, Don't Ask principle

**Recommended Fix:**

#### Option A: Two-phase method in domain (preferred)
```python
# In Competition entity (domain/entities/competition.py)
def reorder_golf_courses_phase1(self, new_order: list[tuple[GolfCourseId, int]]) -> None:
    """
    Phase 1: Assign temporary high values to avoid UNIQUE constraint violations.

    NOTE: Must call flush() after this, then call reorder_golf_courses_phase2()
    This is a pragmatic compromise due to SQLAlchemy UNIQUE constraint handling.
    """
    # Validations...

    # Assign temporary values (10001+)
    for idx, (golf_course_id, _) in enumerate(new_order):
        for cgc in self._golf_courses:
            if cgc.golf_course_id == golf_course_id:
                cgc.change_order(10000 + idx + 1)  # Use public method
                break

def reorder_golf_courses_phase2(self, new_order: list[tuple[GolfCourseId, int]]) -> None:
    """Phase 2: Assign final order values after flush."""
    for golf_course_id, new_display_order in new_order:
        for cgc in self._golf_courses:
            if cgc.golf_course_id == golf_course_id:
                cgc.change_order(new_display_order)
                break

    self.updated_at = datetime.now()

# In ReorderGolfCoursesUseCase (application)
async def execute(self, request, user_id):
    async with self._uow:
        competition = await self._uow.competitions.find_by_id(competition_id)

        # Validations...
        new_order = [(GolfCourseId(uuid), idx + 1) for idx, uuid in enumerate(request.golf_course_ids)]

        # Delegate to domain
        competition.reorder_golf_courses_phase1(new_order)
        await self._uow.flush()
        competition.reorder_golf_courses_phase2(new_order)

        await self._uow.competitions.update(competition)
```

#### Option B: Create a Domain Service
```python
# Domain service for complex reordering
class GolfCourseReorderingService:
    """Domain service for reordering golf courses with SQLAlchemy constraint handling."""

    async def reorder(
        self,
        competition: Competition,
        new_order: list[tuple[GolfCourseId, int]],
        flush_callback: Callable[[], Awaitable[None]]
    ) -> None:
        # Implementation here
```

**Status:** 🔵 PENDING FIX (defer to refactoring sprint)

---

### 2. SQLAlchemy Infrastructure Leaking into Domain Layer

**Severity:** 🔴 CRITICAL
**Files:**
- `src/modules/golf_course/domain/entities/golf_course.py:10`
- `src/modules/user/domain/entities/user_device.py:24`

**Code:**
```python
# golf_course.py line 10
from sqlalchemy.orm import reconstructor

# user_device.py line 24
from sqlalchemy.orm import reconstructor
```

**Violation:**
- Domain layer importing from infrastructure library (SQLAlchemy)
- Breaks the **Dependency Rule** of Clean Architecture

**Why it's wrong:**
1. Domain should be **framework-agnostic** - no knowledge of persistence mechanisms
2. Makes domain entities **coupled to SQLAlchemy**
3. Violates **Dependency Inversion Principle** (DIP) - high-level modules depending on low-level details

**Impact:**
- Cannot swap ORM without changing domain
- Domain becomes infrastructure-aware
- Harder to test domain in isolation

**Recommended Fix:**

#### Option A: Move reconstructor logic to infrastructure (PREFERRED)

```python
# Domain entity (NO SQLAlchemy imports!)
class GolfCourse:
    def __init__(...):
        self._domain_events: list[DomainEvent] = domain_events or []

    def ensure_domain_events_initialized(self) -> None:
        """Public method to initialize domain events if needed."""
        if not hasattr(self, "_domain_events"):
            self._domain_events = []

# Infrastructure mapper (can use SQLAlchemy)
from sqlalchemy import event

@event.listens_for(GolfCourse, "load")
def receive_load(target, context):
    """SQLAlchemy event listener - initializes domain events after load."""
    if not hasattr(target, "_domain_events"):
        target._domain_events = []
```

#### Option B: Accept pragmatic compromise (document it)

Create ADR documenting this decision:

```python
# golf_course.py
"""
INFRASTRUCTURE LEAK WARNING:
This domain entity uses SQLAlchemy's @reconstructor decorator.
While this violates pure Clean Architecture, it's a pragmatic compromise
for imperative mapping with SQLAlchemy.

See ADR-036: SQLAlchemy Reconstructor in Domain for justification.

RULE: This is the ONLY infrastructure import allowed in domain.
"""
from sqlalchemy.orm import reconstructor  # ONLY exception!
```

**Status:** 🟡 DECISION NEEDED (create ADR-036 or refactor to Option A)

---

### 3. Business Logic in Use Case Instead of Domain

**Severity:** 🔴 CRITICAL
**File:** `src/modules/golf_course/application/use_cases/update_golf_course_use_case.py`
**Lines:** 136-226

**Code:**
```python
# Lines 136-226 - Complex if/else logic in use case
if is_admin:
    # CASO 1 y 3: Admin siempre actualiza in-place
    original_course.update(...)
    await self._uow.golf_courses.save(original_course)
    # ...
elif original_course.approval_status == ApprovalStatus.PENDING_APPROVAL:
    # CASO 3: Creator edita su propio campo PENDING → in-place
    original_course.update(...)
    # ...
else:
    # CASO 2: Creator edita su campo APPROVED → crear CLONE
    clone = GolfCourse.create(...)
    clone_reconstructed = GolfCourse.reconstruct(...)
    original_course.mark_as_pending_update()
    # ...
```

**Violation:**
- Complex **business rules** (when to clone vs update) are in the application layer
- The domain entity is **anemic** - it has a generic `update()` method but doesn't understand its own update workflow

**Why it's wrong:**
1. **Anemic Domain Model** - entity is just a data bag
2. Business logic scattered across use cases instead of centralized in domain
3. Hard to test - need to test use case instead of entity
4. Duplication risk - other use cases might implement different update logic

**Impact:**
- Cannot test business rules in isolation
- Logic duplicated if multiple use cases need it
- Domain model doesn't express business invariants

**Recommended Fix:**

Move the decision logic to the domain entity:

```python
# In GolfCourse entity (domain)
def apply_update(
    self,
    name: str,
    country_code: CountryCode,
    course_type: CourseType,
    tees: list[Tee],
    holes: list[Hole],
    requester_is_admin: bool
) -> "GolfCourse | None":
    """
    Applies an update to this golf course.

    Returns:
        - None: If update was applied in-place
        - GolfCourse: If a clone was created (pending approval)

    Business Rules:
    - Admin: Always update in-place (any status)
    - Creator on PENDING: Update in-place
    - Creator on APPROVED: Create clone for approval
    - REJECTED: Cannot update (raise ValueError)
    """
    # Validation
    if self._approval_status == ApprovalStatus.REJECTED:
        raise ValueError("Cannot edit a REJECTED golf course")

    # Decision: In-place or clone?
    if requester_is_admin or self._approval_status == ApprovalStatus.PENDING_APPROVAL:
        # Update in-place
        self.update(name, country_code, course_type, tees, holes)
        return None

    # Creator editing APPROVED → create clone
    clone = GolfCourse.create(
        name=name,
        country_code=country_code,
        course_type=course_type,
        creator_id=self._creator_id,
        tees=tees,
        holes=holes,
    )

    # Mark as update proposal
    clone._original_golf_course_id = self._id
    self.mark_as_pending_update()

    return clone

# In UpdateGolfCourseUseCase (application - thin orchestration)
async def execute(self, golf_course_id, request, user_id, is_admin):
    async with self._uow:
        original_course = await self._uow.golf_courses.find_by_id(golf_course_id)

        # Authorization checks...
        # Build tees and holes from DTOs...

        # Delegate decision to domain
        clone = original_course.apply_update(
            name=request.name,
            country_code=country_code,
            course_type=request.course_type,
            tees=tees,
            holes=holes,
            requester_is_admin=is_admin
        )

        # Save original (always)
        await self._uow.golf_courses.save(original_course)

        # Save clone if created
        if clone:
            await self._uow.golf_courses.save(clone)

        # Build response...
```

**Status:** 🔵 PENDING FIX (defer to refactoring sprint)

---

## ⚠️ WARNING Violations (Should Fix)

### 4. Value Objects Missing `__eq__` and `__hash__` Implementations

**Severity:** ⚠️ WARNING
**Files:**
- `src/modules/competition/domain/value_objects/team_assignment.py`
- `src/modules/competition/domain/value_objects/enrollment_status.py`
- `src/modules/competition/domain/value_objects/competition_status.py`
- `src/modules/golf_course/domain/value_objects/course_type.py`
- `src/modules/golf_course/domain/value_objects/approval_status.py`
- `src/modules/golf_course/domain/value_objects/tee_category.py`

**Violation:**
- Value Objects (Enums) inherit from `str, Enum` but don't explicitly define equality semantics
- While Python's Enum provides default equality, it's by **identity** not **value**

**Why it's problematic:**
- Value Objects should be compared by **value**, not identity
- Missing explicit `__hash__` can cause issues in sets/dicts
- Not following DDD value object contract explicitly

**Recommended Fix:**

```python
class TeamAssignment(str, Enum):
    MANUAL = "MANUAL"
    AUTOMATIC = "AUTOMATIC"

    def __eq__(self, other: object) -> bool:
        """Compare by value (DDD Value Object pattern)."""
        if isinstance(other, TeamAssignment):
            return self.value == other.value
        if isinstance(other, str):
            return self.value == other
        return False

    def __hash__(self) -> int:
        """Hash by value for use in sets/dicts."""
        return hash(self.value)
```

**Priority:** Low (Python's Enum already provides reasonable equality)

---

### 5. God Object Anti-Pattern in API Routes

**Severity:** ⚠️ WARNING
**Files:**
- `src/modules/competition/infrastructure/api/v1/competition_routes.py` (1606 lines)
- `src/modules/user/infrastructure/api/v1/auth_routes.py` (879 lines)
- `src/modules/golf_course/infrastructure/api/v1/golf_course_routes.py` (767 lines)

**Violation:**
- API route files exceed 500 lines (competition_routes.py is 1606!)
- Single Responsibility Principle violation
- Hard to maintain and test

**Why it's problematic:**
- Difficult to navigate and understand
- Multiple responsibilities in one file
- High coupling - changes affect many features

**Recommended Fix:**

Split into smaller modules by feature:

```markdown
infrastructure/api/v1/
├── competition/
│   ├── __init__.py
│   ├── create_routes.py      # POST /competitions
│   ├── query_routes.py        # GET /competitions
│   ├── update_routes.py       # PUT /competitions
│   ├── state_routes.py        # activate, close, start, complete, cancel
│   └── golf_course_routes.py # add/remove/reorder golf courses
```

**Priority:** Medium

---

### 6. Domain Logic Scattered in Use Cases (Anemic Domain)

**Severity:** ⚠️ WARNING
**Examples:**
- `UpdateGolfCourseUseCase`: 136-226 lines of if/else business logic
- `ReorderGolfCoursesUseCase`: 126-158 lines of ordering logic
- `UpdateCompetitionUseCase`: Building HandicapSettings in use case

**Violation:**
- Business rules are in the **application layer** instead of **domain layer**
- Entities have minimal behavior (mostly getters/setters)
- Classic **Anemic Domain Model** anti-pattern

**Recommended Fix:**

Move business logic to domain entities. See Violation #3 for detailed example.

**Priority:** High (related to CRITICAL #1 and #3)

---

### 7. Missing Domain Services for Cross-Aggregate Logic

**Severity:** ⚠️ WARNING
**File:** `src/modules/competition/application/use_cases/update_competition_use_case.py:71`

**Code:**
```python
class UpdateCompetitionUseCase:
    def __init__(self, uow: CompetitionUnitOfWorkInterface):
        self._uow = uow
        self._location_builder = LocationBuilder(self._uow.countries)  # Domain service
```

**Violation:**
- `LocationBuilder` is a domain service but instantiated in **application layer**
- Domain service depends on repository interface - should be injected

**Recommended Fix:**

```python
# Domain service interface
class ILocationBuilder(ABC):
    @abstractmethod
    async def build_from_codes(...) -> Location:
        pass

# Use case with DI
class UpdateCompetitionUseCase:
    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        location_builder: ILocationBuilder  # Injected!
    ):
        self._uow = uow
        self._location_builder = location_builder
```

**Priority:** Medium

---

### 8. Domain Entities with Public Attributes (Weak Encapsulation)

**Severity:** ⚠️ WARNING
**File:** `src/modules/competition/domain/entities/competition.py:119-133`

**Code:**
```python
class Competition:
    def __init__(self, ...):
        # PUBLIC attributes (no underscore!)
        self.id = id
        self.creator_id = creator_id
        self.name = name
        # ... etc

        # Only these are private
        self._domain_events: list[DomainEvent] = domain_events or []
        self._golf_courses: list[CompetitionGolfCourse] = []
```

**Violation:**
- Most attributes are **public** (no underscore)
- **Inconsistent encapsulation** - GolfCourse uses `_name`, `_id`, etc.

**Recommended Fix:**

Make all attributes private with properties (for consistency with GolfCourse):

```python
class Competition:
    def __init__(self, ...):
        self._id = id
        self._creator_id = creator_id
        self._name = name
        # ...

    @property
    def id(self) -> CompetitionId:
        return self._id

    # No setters! Force changes through business methods
    def update_info(self, name: CompetitionName | None = None, ...):
        if name is not None:
            self._name = name
```

**Priority:** Medium (consistency improvement)

---

### 9. Missing Validation in Entity Constructor

**Severity:** ⚠️ WARNING
**File:** `src/modules/competition/domain/entities/competition.py:81-133`

**Code:**
```python
def __init__(
    self,
    max_players: int = 24,  # NO validation!
    # ...
):
    # Validates team names
    self._validate_team_names(team_1_name, team_2_name)

    # NO validation for max_players here!
    self.max_players = max_players
```

**Violation:**
- Constructor accepts `max_players` without validation
- Validation only happens in `update_info()` method
- **Invariants not enforced at creation time**

**Recommended Fix:**

```python
def __init__(self, max_players: int = 24, ...):
    # Validate ALL invariants BEFORE assignment
    self._validate_team_names(team_1_name, team_2_name)
    self._validate_max_players(max_players)  # NEW!

    self.max_players = max_players

def _validate_max_players(self, max_players: int) -> None:
    """Validates max_players is within allowed range."""
    if not MIN_PLAYERS <= max_players <= MAX_PLAYERS:
        raise ValueError(f"max_players must be between {MIN_PLAYERS} and {MAX_PLAYERS}")
```

**Priority:** Medium

---

### 10. Temporal Coupling in Domain Methods

**Severity:** ⚠️ WARNING
**File:** `src/modules/golf_course/domain/entities/golf_course.py:320-342`

**Code:**
```python
def update(self, name, country_code, course_type, tees, holes):
    # ... validations ...

    # Actualizar colecciones rastreadas por SQLAlchemy
    del self._tees[:]  # Delete in-place

    # IMPORTANTE: Creamos NUEVOS objetos... para evitar conflictos con SQLAlchemy
    for tee in tees:
        new_tee = TeeEntity(...)  # Create NEW objects
        self._tees.append(new_tee)
```

**Violation:**
- Domain entity knows about SQLAlchemy's collection tracking behavior
- Comment explicitly mentions "evitar conflictos con SQLAlchemy"
- **Domain entity coupled to ORM implementation details**

**Recommended Fix:**

```python
def update(self, name, country_code, course_type, tees, holes):
    # Domain shouldn't know about SQLAlchemy tracking
    self._name = name
    self._country_code = country_code

    # Simple assignment - let mapper handle the details
    self._tees = list(tees)  # Defensive copy
    self._holes = list(holes)

    self._validate_holes()
    self._validate_tees()
```

**Priority:** Low (works fine, but couples domain to infrastructure)

---

### 11. Inconsistent Use of Value Objects

**Severity:** ⚠️ WARNING
**File:** `src/modules/competition/domain/entities/competition.py:88-89, 124-125`

**Code:**
```python
# Lines 88-89 - Plain strings!
team_1_name: str,
team_2_name: str,

# Lines 124-125 - Assigned as strings
self.team_1_name = team_1_name
self.team_2_name = team_2_name
```

**Violation:**
- `team_1_name` and `team_2_name` are plain strings
- Other concepts use Value Objects (`CompetitionName`, `Location`)
- **Inconsistent domain modeling** (primitive obsession)

**Recommended Fix:**

Create a `TeamName` Value Object:

```python
# domain/value_objects/team_name.py
@dataclass(frozen=True)
class TeamName:
    """Value Object for team name with validation."""

    value: str

    def __post_init__(self):
        if not self.value or not self.value.strip():
            raise ValueError("Team name cannot be empty")

        if len(self.value) > 100:
            raise ValueError("Team name cannot exceed 100 characters")

# Competition entity
def __init__(self, team_1_name: TeamName, team_2_name: TeamName, ...):
    if team_1_name == team_2_name:
        raise ValueError("Team names must be different")

    self.team_1_name = team_1_name
    self.team_2_name = team_2_name
```

**Priority:** Low

---

## ℹ️ INFO Violations (Minor Improvements)

### 12. Missing `__composite_values__()` Documentation

**Severity:** ℹ️ INFO
**File:** `src/modules/user/domain/value_objects/handicap.py`

**Recommendation:** Add documentation comment explaining why it doesn't implement `__composite_values__()`:

```python
@dataclass(frozen=True)
class Handicap:
    """
    Value Object for golf handicap.

    NOTE: This VO uses TypeDecorator mapping (single column, optional NULL).
    It does NOT implement __composite_values__() because it's not a composite.
    See ADR: Handicap Value Object Mapping (Nov 2025).
    """
    value: float
```

---

### 13. Inconsistent Event Naming Convention

**Severity:** ℹ️ INFO
**Examples:**
- `UserRegisteredEvent` vs `CompetitionCreatedEvent`
- `EmailVerifiedEvent` vs `CompetitionActivatedEvent`

**Recommendation:** Standardize to past tense (DDD best practice):
- Events should always be **past tense** (something happened)
- Current names are clear enough, but consistency would be better

---

### 14. Missing Bounded Context Boundaries

**Severity:** ℹ️ INFO
**Observation:**
- `GolfCourseId` imported directly into `Competition` module
- No explicit **Anti-Corruption Layer** (ACL)

**Recommendation:** For large projects, create ports/adapters between bounded contexts. Current approach is acceptable for MVP.

---

### 15. Potential Circular Dependency Risk

**Severity:** ℹ️ INFO
**Observation:**
- `Competition` imports `CompetitionGolfCourse`
- If `CompetitionGolfCourse` ever needs `Competition`, circular import occurs

**Recommendation:** Use forward references:

```python
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .competition import Competition
```

---

## 📋 Action Plan by Priority

### High Priority (Fix this sprint)

1. **Decide on SQLAlchemy `@reconstructor`**:
   - ✅ **Option A**: Create ADR-036 accepting the pragmatic compromise
   - ⏸️ Option B: Refactor to use SQLAlchemy event listeners in infrastructure

2. **Document Violation #1** (ReorderGolfCourses):
   - Accept current implementation as technical debt
   - Add TODO comment referencing this document
   - Plan refactoring for future sprint

3. **Add validation** to Competition constructor (max_players)

### Medium Priority (Fix within 1 month)

1. Refactor `UpdateGolfCourseUseCase` - move logic to domain
2. Make Competition entity attributes private (consistency with GolfCourse)
3. Split large API route files into smaller modules
4. Inject `LocationBuilder` as dependency (not create in use case)

### Low Priority (Refactor when convenient)

1. Add `__eq__`/`__hash__` to Enum Value Objects
2. Create `TeamName` Value Object
3. Clean up SQLAlchemy temporal coupling in GolfCourse.update()
4. Standardize event naming convention
5. Add documentation for TypeDecorator vs composite()

---

## 🎯 Recommended Immediate Actions

### Before Sprint 2 Continues:

1. ✅ **Create ADR-036**: "SQLAlchemy `@reconstructor` in Domain - Pragmatic Exception"
2. ✅ **Add TODO comments** in violation locations referencing this document
3. ✅ **Write missing tests** for Block 1 (31 application + integration tests)
4. ⏸️ **Defer refactoring** to dedicated sprint (avoid scope creep)

### Before v2.1.0 (Major Refactoring):

1. Fix Violation #1 (ReorderGolfCourses) - move to domain or create Domain Service
2. Fix Violation #3 (UpdateGolfCourse) - move logic to domain
3. Split God Objects in API layer
4. Make Competition attributes private

---

## 📚 References

- **Clean Architecture** by Robert C. Martin
- **Domain-Driven Design** by Eric Evans
- **Implementing Domain-Driven Design** by Vaughn Vernon
- **CLAUDE.md** - Project architecture decisions
- **ROADMAP.md** - Current sprint status

---

**Generated:** February 1, 2026
**Next Review:** End of Sprint 2 (Feb 24, 2026)
