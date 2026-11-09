# Known Security Issues

> Documentation of known security vulnerabilities and risk assessment

---

## 🔒 Active Issues

### CVE-2024-23342 - ecdsa Minerva Timing Attack

**Package**: `ecdsa==0.19.1` (transitive dependency via `python-jose`)
**Severity**: 🔴 HIGH (CVSS 7.4)
**Discovered**: January 2024
**Status**: ⚠️ ACCEPTED RISK

#### Vulnerability Description

The `python-ecdsa` package is vulnerable to a Minerva timing attack on the P-256 elliptic curve. An attacker can analyze timing differences in ECDSA signature operations to potentially extract the private key.

**Affected Components**:
- ECDSA signatures (ES256, ES384, ES512 algorithms)
- ECDSA key generation
- ECDH operations

**Not Affected**:
- ECDSA signature verification
- HMAC-based algorithms (HS256, HS384, HS512)

#### Impact on Our Project

**Risk Level**: 🟢 **LOW**

**Reason**: This project uses **HS256 (HMAC SHA256)** for JWT signing, NOT elliptic curve algorithms.

**Evidence**:
```python
# src/config/settings.py
ALGORITHM: ClassVar[str] = "HS256"  # HMAC, not ECDSA; fixed, not read from the env (ADR-047)
```

**Code Analysis**:
- ✅ No usage of ES256/ES384/ES512 algorithms
- ✅ No ECDSA key generation
- ✅ No P-256/secp256r1 curve usage
- ✅ No ECDH operations

#### Remediation Status

**Fix Available**: ❌ NO

The `python-ecdsa` maintainers consider this vulnerability **out of scope** with the reasoning:
> "Implementing side-channel free code in pure python is impossible"

**No fix is planned.**

#### Our Decision

**Action**: ACCEPT RISK - No mitigation required

**Rationale**:
1. We don't use the vulnerable functionality (ECDSA)
2. No fix is available from upstream
3. Switching algorithms is unnecessary given no actual risk
4. Removing the dependency would require replacing `python-jose` with alternatives

#### Monitoring

**Conditions for Re-evaluation**:
- ⚠️ If we switch to ES256/ES384/ES512 algorithms → **CRITICAL**
- ⚠️ If a fix becomes available → Update dependency
- ⚠️ If we implement ECDSA key generation → Migrate to `cryptography` library

**Alternative Solutions** (if needed in future):
1. Replace `python-jose` with `PyJWT[crypto]` (uses `cryptography` backend)
2. Use `cryptography` library directly for JWT operations
3. Implement custom JWT handler with `cryptography`

#### References

- **CVE**: https://nvd.nist.gov/vuln/detail/CVE-2024-23342
- **GitHub Advisory**: https://github.com/tlsfuzzer/python-ecdsa/security/advisories/GHSA-wj6h-64fc-37mp
- **Research**: https://minerva.crocs.fi.muni.cz/

---

## 📊 Risk Assessment Summary

| CVE | Package | Severity | Impact | Status | Last Review |
|-----|---------|----------|--------|--------|-------------|
| CVE-2024-23342 | ecdsa 0.19.1 | HIGH (7.4) | LOW | Accepted | 2026-01-29 |

---

**Last Updated**: January 29, 2026
**Reviewed By**: Development Team
**Next Review**: When upgrading JWT-related dependencies
