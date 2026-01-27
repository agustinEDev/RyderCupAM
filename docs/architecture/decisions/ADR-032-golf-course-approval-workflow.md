# ADR-032: Golf Course Approval Workflow Details

**Date**: January 27, 2026
**Status**: Accepted
**Decision Makers**: Development Team
**Sprint**: v2.1.0 - Sprint 1 (Golf Courses)

## Context and Problem

Creators need to request new golf courses, but require Admin approval before being usable in competitions. This prevents data quality issues while not blocking Creators.

**Need**: Define detailed workflow rules, visibility permissions, and notification system.

## Decisions

### 1. Approval States

```python
class ApprovalStatus(Enum):
    PENDING_APPROVAL = "PENDING_APPROVAL"  # Initial state
    APPROVED = "APPROVED"                   # Admin approved
    REJECTED = "REJECTED"                   # Admin rejected
```

**State transitions**:
- Creator creates → PENDING_APPROVAL
- Admin approves → APPROVED (final)
- Admin rejects → REJECTED (final)

**No intermediate states** (PENDING_REVIEW, PENDING_CHANGES) → YAGNI principle

### 2. Visibility Rules

| Status | Visible To | Use Case |
|--------|-----------|----------|
| PENDING_APPROVAL | Admin + Creator (owner) | Review pending courses |
| APPROVED | All Creators | Select for competition |
| REJECTED | Admin + Creator (owner) | View rejection reason |

**Implementation**:
```python
def can_view_golf_course(user: User, course: GolfCourse) -> bool:
    if course.approval_status == ApprovalStatus.APPROVED:
        return user.has_role("CREATOR") or user.has_role("ADMIN")

    if course.approval_status in [ApprovalStatus.PENDING_APPROVAL, ApprovalStatus.REJECTED]:
        return user.has_role("ADMIN") or user.id == course.requested_by

    return False
```

### 3. Edit After Rejection

**Decision**: NOT allowed

**Reason**: Audit trail + data integrity. Creator must create NEW request with corrections.

**Alternative considered**: Allow editing rejected courses → Descartado (complicates audit, potential data inconsistency)

### 4. Cascading Delete

**Decision**: Tees + Holes deleted if golf course is rejected (hard delete)

```sql
ALTER TABLE tees ADD CONSTRAINT fk_tees_golf_course
    FOREIGN KEY (golf_course_id) REFERENCES golf_courses(id)
    ON DELETE CASCADE;

ALTER TABLE holes ADD CONSTRAINT fk_holes_golf_course
    FOREIGN KEY (golf_course_id) REFERENCES golf_courses(id)
    ON DELETE CASCADE;
```

**Reason**: Rejected courses are not reusable, clean up database

**Alternative considered**: Soft delete → Descartado (unnecessary complexity, approved courses never deleted)

### 5. Rejection Reason

**Field**: `rejection_reason VARCHAR(500) NULL`

**Required**: Only when rejecting (Pydantic validation)

```python
class RejectGolfCourseRequest(BaseModel):
    rejection_reason: str = Field(min_length=10, max_length=500)
```

**Visibility**: Only Admin + Creator (owner) can see

### 6. Email Notifications

**Decision**: Send email to Creator when Admin approves/rejects

**Templates** (bilingual ES/EN, Mailgun):

**Approval email**:
```
Subject: ✅ Your golf course "{name}" has been approved
Body:
- Course is now available for competitions
- Link to course detail page
```

**Rejection email**:
```
Subject: ❌ Your golf course "{name}" requires corrections
Body:
- Rejection reason (from Admin)
- Suggestion to create new request with corrections
- Link to create new course
```

**No batch notifications**: Email sent individually (even if Admin approves 10 courses)

**Reason**: Immediate feedback > batching

### 7. Validation in Multiple Layers

**Defense in depth**:

```python
# 1. Pydantic DTO validation (API layer)
class GolfCourseRequest(BaseModel):
    holes: list[HoleDTO] = Field(min_length=18, max_length=18)

    @field_validator('holes')
    def validate_stroke_index_unique(cls, holes):
        # Exactly 18 holes, stroke index 1-18 unique

# 2. Domain Entity validation
class GolfCourse:
    def __init__(self, ...):
        if len(holes) != 18:
            raise DomainValidationError("Must have exactly 18 holes")

# 3. Database constraint
CHECK (LENGTH(holes) = 18)
```

**Reason**: Catch errors as early as possible, multiple safety nets

## Consequences

### Positive ✅
- Clear visibility rules (no unauthorized access)
- Audit trail (no editing after rejection)
- Data quality control (Admin review)
- Immediate feedback (email notifications)
- Defense in depth (validation at 3 layers)

### Negative ⚠️
- Creator must recreate entire course if rejected (not just edit)
- Admin workload (manual review required)
- Email spam if Admin approves many courses at once

## Alternatives Considered

1. **Auto-approval for Admin** → Descartado (explicit approval better for audit)
2. **Intermediate states (PENDING_CHANGES)** → Descartado (YAGNI, adds complexity)
3. **Soft delete rejected courses** → Descartado (no reuse, wastes storage)
4. **Batch email notifications** → Descartado (immediate feedback more important)

## References

- **ADR-025**: Competition Module Evolution v2.1.0 (mentions approval briefly)
- **ROADMAP.md**: v2.1.0 Sprint 1 (Golf Courses endpoints)
- **Similar workflow**: GitHub PR approval (request → review → approve/reject)

---
**Lines**: 98 | **Immutable after acceptance**
