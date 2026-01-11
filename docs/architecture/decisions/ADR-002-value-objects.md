# ADR-002: Value Objects Implementation

**Date**: October 31, 2025
**Status**: Accepted
**Deciders**: Development Team

## Context and Problem

We need to decide how to represent domain concepts (identifiers, emails, passwords, handicaps). Options: primitive types or Value Objects.

**Problem with Primitive Types**: No validation, unclear intent, scattered business rules.

## Options Considered

1. **Simple Primitive Types**: string, int for all fields - Rejected
2. **Validation in Constructor**: Validate in entity constructor - Rejected
3. **Value Objects**: Immutable objects with encapsulated validation - **Accepted**
4. **Mixed**: Value Objects only for complex cases - Rejected

## Decision

**We implement Value Objects** for important domain concepts:

- **UserId**: UUID v4 unique identifier
- **Email**: Validated and normalized email
- **Password**: bcrypt hashed password
- **Handicap**: Golf handicap with RFEG/EGA range validation (-10.0 to 54.0)

### Implementation Pattern:
```python
@dataclass(frozen=True)
class Email:
    value: str
    
    def __post_init__(self):
        normalized = self._normalize_email(self.value)
        if not self._is_valid_email(normalized):
            raise InvalidEmailError(f"'{self.value}' is not valid")
        object.__setattr__(self, 'value', normalized)
```

## Justification

### Advantages of Value Objects:

1. **Validation Encapsulation**: Automatic validation, impossible to create invalid objects
2. **Immutability**: `@dataclass(frozen=True)` prevents mutations, thread-safe
3. **Code Expressiveness**: Clear types (Email vs str)
4. **Reusability**: Email can be used across entities
5. **Testability**: Granular unit tests (49 specific tests)

### Specific Use Cases:

**UserId (UUID v4)**: Guaranteed security and uniqueness
**Email**: Normalization (lowercase, trim) + regex validation, consistent throughout app
**Password**: Automatic bcrypt + strength validation, security by default
**Handicap**: Range validation (-10.0 to 54.0) per RFEG/EGA rules, guarantees valid values

## Consequences

### Positive:
- ✅ **Automatic validation**: Impossible to create invalid objects
- ✅ **More expressive code**: Specific vs generic types
- ✅ **Immutability**: Prevents bugs and side effects
- ✅ **Centralization**: Single source of truth
- ✅ **Testability**: Granular and specific tests

### Negative:
- ❌ **More code**: More files and classes to maintain
- ❌ **Initial complexity**: Learning curve
- ❌ **Performance**: Minimal overhead in object creation

### Mitigated Risks:
- **Complexity**: Clear documentation and examples
- **Performance**: Benchmarks show negligible impact
- **Maintenance**: Automated tests guarantee functionality

## Applied Patterns

1. **Factory Methods**: `Password.from_plain_text()`, `UserId.generate()`
2. **Validation in __post_init__**: Automatic on construction
3. **Immutability with frozen=True**: No modifications after creation

### Testing Optimizations:
- Fast bcrypt: rounds=4 in tests vs rounds=12 in production
- TESTING variable: Automatic environment detection
- Performance: Value Objects don't impact test speed

## References

- [Domain-Driven Design by Eric Evans](https://domainlanguage.com/ddd/)
- [Value Objects Explained](https://martinfowler.com/bliki/ValueObject.html)
- [Python Dataclasses Documentation](https://docs.python.org/3/library/dataclasses.html)
- [ADR-014: Handicap Management System](./ADR-014-handicap-management-system.md) - Specific Handicap VO implementation
- [Design Document](../design-document.md) - See Metrics section for implemented Value Objects