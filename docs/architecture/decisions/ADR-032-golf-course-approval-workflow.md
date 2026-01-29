# ADR-032: Golf Course Approval Workflow

**Date**: January 27, 2026
**Status**: Accepted
**Decision Makers**: Development Team
**Sprint**: v2.0.0 - Sprint 1 (Golf Courses)

## Context and Problem

Creators request golf courses but need Admin approval before use. Balance: quality control without blocking workflow.

**Need**: Define workflow rules, visibility, notifications.

## Decisions

### 1. Approval States

**States**: `PENDING_APPROVAL`, `APPROVED`, `REJECTED` (all final).

**Transitions**:
- Creator creates → PENDING_APPROVAL
- Admin approves → APPROVED
- Admin rejects → REJECTED

**No intermediate states** (YAGNI principle).

### 2. Visibility Rules

| Status | Visible To | Use Case |
|--------|-----------|----------|
| PENDING_APPROVAL | Admin + Creator (owner) | Review pending |
| APPROVED | All Creators | Select for competition |
| REJECTED | Admin + Creator (owner) | View rejection reason |

### 3. Edit After Rejection

**Decision**: NOT allowed.

**Reason**: Audit trail + integrity. Creator creates NEW request.

### 4. Cascading Delete

**Decision**: Tees + Holes cascade-delete with rejected courses (hard delete).

**Reason**: Rejected courses not reusable, clean database.

### 5. Rejection Reason

**Field**: `rejection_reason VARCHAR(500) NULL`

**Required**: Only when rejecting (Pydantic validation min=10, max=500).

**Visibility**: Admin + owner only.

### 6. Email Notifications

**Decision**: Email Creator on approve/reject (bilingual ES/EN via Mailgun).

**Templates**: See `docs/email-templates.md` for approval/rejection templates.

**No batching**: Individual emails for immediate feedback.

### 7. Multi-Layer Validation

**Defense in depth**: Pydantic DTO → Domain Entity → Database constraints.

**Example**: 18 holes with unique stroke indexes validated at all 3 layers.

## Consequences

### Positive ✅
- Clear visibility (no unauthorized access)
- Audit trail (immutable after rejection)
- Quality control (Admin review)
- Immediate feedback (emails)
- Defense in depth (3 validation layers)

### Negative ⚠️
- Must recreate if rejected (no edit)
- Admin workload (manual review)
- Email volume (no batching)

## Alternatives Considered

- **Auto-approval for Admin** → Explicit better for audit
- **Intermediate states** → YAGNI
- **Soft delete** → Wastes storage
- **Batch emails** → Immediate feedback better

## References

- **ADR-025**: Competition Module Evolution
- **ROADMAP.md**: v2.0.0 Sprint 1
- **Similar**: GitHub PR approval workflow
