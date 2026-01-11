# ADR-019: Email Verification System

**Status**: ✅ Accepted
**Date**: Nov 12, 2025

---

## Context

We need to verify that user emails are real and belong to the person registering.

**Requirements**:
- Validate email ownership
- Prevent spam and fake accounts
- Low UX friction (not mandatory to use app)
- Testable without sending real emails
- Multilingual support (ES/EN)

---

## Decision

**Email verification system with persisted unique UUID tokens** + **Mailgun as provider**.

### Architecture

**Domain Layer**: User.generate_verification_token(), User.verify_email(), EmailVerifiedEvent
**Application Layer**: RegisterUserUseCase (generates token, sends email), VerifyEmailUseCase (validates token)
**Infrastructure Layer**: EmailService (Mailgun API), UserRepository.find_by_verification_token()
**Endpoint**: POST /api/v1/auth/verify-email

**Flow**:
1. Registration → UUID token → bilingual email
2. User clicks link → frontend extracts token
3. POST /auth/verify-email → validates → marks verified
4. Emits EmailVerifiedEvent for auditing

---

## Rejected Alternatives

**1. Signed JWTs as Tokens**: Not revocable - **UUID in DB chosen** (revocable, testable)
**2. SendGrid / AWS SES**: More expensive / complex setup - **Mailgun chosen** (12k free emails/month)
**3. Mandatory Verification**: High UX friction - **Optional chosen** (can use app, limited features)
**4. Magic Links**: Changes auth paradigm - **Separate verification chosen**

---

## Consequences

### Positive
✅ **Security**: Only email owner can verify
✅ **Revocable**: Token in DB, deletable
✅ **Testable**: Mock email service
✅ **Clean Architecture**: EmailService in infrastructure
✅ **Flexible UX**: Doesn't block app usage
✅ **Bilingual**: ES/EN from start
✅ **Auditable**: EmailVerifiedEvent

### Negative
⚠️ **Unverified Accounts**: Users can use app without verification
⚠️ **Non-Expiring Tokens**: No current expiration
⚠️ **No Resend**: No resend endpoint
⚠️ **External Dependency**: Requires Mailgun

**Mitigations**: Limit premium features to verified users, Phase 2: token expiration (7 days) + resend

---

## Configuration

**Environment Variables**: MAILGUN_API_KEY, MAILGUN_DOMAIN, MAILGUN_FROM_EMAIL, MAILGUN_API_URL, FRONTEND_URL

**Database Migration**: Added email_verified (bool), verification_token (varchar), index on verification_token

---

## Frontend Integration

**New Components**: VerifyEmailPage, EmailVerificationBanner
**Modified Pages**: Dashboard, Profile, Login
**Optimized UX**: 1.5s spinner + 3s confirmation + auto-redirect
**States**: verifying, success, error, invalid
**Visual Indicators**: Yellow banner if unverified, badges in profile

---

## References

- [ADR-007: Domain Events Pattern](./ADR-007-domain-events-pattern.md)
- [ADR-013: External Services Pattern](./ADR-013-external-services-pattern.md)
- [Mailgun API Documentation](https://documentation.mailgun.com/en/latest/api-sending.html)
