# ADR-003: Testing and Optimization Strategy

**Date**: October 31, 2025
**Status**: Accepted
**Deciders**: Development Team

## Context and Problem

We need to establish a testing strategy that is:
- **Fast**: Immediate feedback during development
- **Comprehensive**: Adequate coverage of functionality
- **Maintainable**: Easy to understand and update
- **Scalable**: Works as the project grows

### Specific Challenges:
- Slow bcrypt tests (100-200ms per hash)
- Confusing organization by test types
- Poor visual feedback during execution
- Lack of test parallelization

## Options Considered

1. **Basic Testing**: Simple pytest without optimizations
2. **Optimized Testing**: Parallelization + specific optimizations
3. **Advanced Testing**: Complex tools (tox, coverage, etc.)
4. **Minimal Testing**: Only essential tests

## Decision

**We implement Optimized Testing** with:

### 1. Framework and Tools:
- **pytest 8.3.0**: Main framework
- **pytest-xdist 3.8.0**: Automatic parallelization
- **httpx 0.27.0**: HTTP client for API tests

### 2. Performance Optimizations:
- **Accelerated bcrypt**: rounds=4 in tests vs rounds=12 in production
- **Parallelization**: 7 concurrent workers (CPU cores - 1)
- **TESTING variable**: Automatic detection of testing environment

### 3. Organization by Clean Architecture:
```
tests/
├── unit/                          # Unit tests
│   └── modules/user/domain/
│       ├── entities/              # Entity tests
│       ├── value_objects/         # Value Object tests
│       └── repositories/          # Interface tests
└── integration/                   # Integration tests
  └── api/                       # Endpoint tests
```

### 4. Custom Testing Script:
- **dev_tests.py**: Organized visual presentation
- **Separation by objects**: User, Email, Password, etc.
- **Real-time metrics**: Duration and statistics

## Justification

### bcrypt Optimization:
- Production: rounds=12 (~100ms, secure)
- Testing: rounds=4 (~5ms, 95% faster)
- TESTING variable for environment detection
- Zero security impact on production

### Smart Parallelization:
- Automatic detection: CPU cores - 1 (7 workers)
- Uses all available CPU cores
- Automatic fallback if xdist unavailable

## Results Achieved

### Performance Improvements:
- Total Time: 5s → 0.54s (90% reduction)
- CPU Usage: 100% → 319% (full parallelization)
- bcrypt tests: 100ms → 5ms (95% reduction)
- 80 tests, 100% pass rate maintained

## Consequences

### Positive:
- ✅ **Ultra-fast feedback**: 0.54s for 80 tests
- ✅ **Agile development**: Tests do not interrupt flow
- ✅ **Clear organization**: Easy to locate problems
- ✅ **Scalability**: Ready for hundreds of tests
- ✅ **Zero configuration**: Works out-of-the-box

### Negative:
- ❌ **Initial complexity**: Custom script to maintain
- ❌ **Additional dependency**: pytest-xdist required
- ❌ **Specific configuration**: Environment detection logic

### Risks Mitigated:
- bcrypt security: Only affects testing
- Parallelization: Automatic fallback
- Maintenance: Well-documented

## Database Isolation in Integration Tests

**Problem**: Race conditions with parallel `pytest-xdist` workers sharing same database.

**Solution**: Create unique database per worker (e.g., `test_db_gw0`):
1. Detect worker ID from pytest-xdist
2. Create unique temporary database
3. Run test in isolated database
4. Destroy database after test

**Benefits**: 100% reliable parallel tests, easier debugging, clean state guaranteed.

## Decision Validation

### Success Criteria (All Met):
- [x] Tests < 2 seconds: 0.54s achieved
- [x] 100% pass rate: 80/80 tests passing
- [x] Clear feedback: Architecture-based organization
- [x] Easy debugging: Quick problem identification

## References

- [pytest Documentation](https://docs.pytest.org/)
- [pytest-xdist Plugin](https://pytest-xdist.readthedocs.io/)
- [Testing Best Practices](https://testing.googleblog.com/)
- [Clean Architecture Testing](https://blog.cleancoder.com/uncle-bob/2014/05/14/TheLittleMocker.html)  
- `requirements.txt`: Documented testing dependencies