# Contributing to Dataset Analyzer

Thank you for considering contributing to Dataset Analyzer! This document provides guidelines and instructions for contributing.

## Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Help others learn and grow
- Prioritize production quality

## Development Setup

### 1. Fork and Clone

```bash
git clone https://github.com/your-username/dataset-analyzer.git
cd dataset-analyzer
```

### 2. Install Dependencies

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dev dependencies
make install-dev
```

### 3. Setup Pre-commit Hooks (Optional)

```bash
pip install pre-commit
pre-commit install
```

## Development Workflow

### 1. Create Feature Branch

```bash
git checkout -b feature/your-feature-name
```

### 2. Make Changes

- Write clean, documented code
- Follow PEP 8 style guide
- Add type hints
- Include docstrings

### 3. Run Tests

```bash
# Run all tests
make test

# Run specific tests
pytest integration-tests/test_e2e.py

# With coverage
make test
```

### 4. Code Quality Checks

```bash
# Linting
make lint

# Formatting
make format

# Type checking
make type-check

# Security scan
make security-scan

# Run all checks (CI pipeline)
make ci
```

### 5. Commit Changes

```bash
git add .
git commit -m "feat: add amazing feature"
```

**Commit Message Format:**
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `test:` Test additions/changes
- `refactor:` Code refactoring
- `perf:` Performance improvements
- `security:` Security improvements

### 6. Push and Create PR

```bash
git push origin feature/your-feature-name
```

Then create Pull Request on GitHub.

## Testing Guidelines

### Test Priorities

1. **Integration tests** (60% of effort)
   - Test complete workflows
   - Test layer interactions
   - Test real-world scenarios

2. **Security tests** (25% of effort)
   - XSS protection
   - Excel injection
   - Rate limiting
   - File validation

3. **Performance tests** (10% of effort)
   - Benchmarks
   - Stress tests
   - Memory profiling

4. **Unit tests** (5% of effort)
   - Edge cases
   - Complex logic

### Writing Tests

```python
# integration-tests/test_feature.py

def test_feature_end_to_end():
    """Test complete feature workflow."""
    # Arrange
    input_data = create_test_data()

    # Act
    result = process_data(input_data)

    # Assert
    assert result.status == "success"
    assert result.records_count > 0
```

### Running Tests

```bash
# All tests
pytest

# Specific test file
pytest integration-tests/test_e2e.py

# Specific test
pytest integration-tests/test_e2e.py::test_full_pipeline_csv

# With markers
pytest -m security  # Security tests only
pytest -m slow      # Slow/stress tests only

# With coverage
pytest --cov=shared --cov=layers
```

## Code Style

### Python Style Guide

- Follow PEP 8
- Use Black formatter (line length: 100)
- Use Ruff linter
- Add type hints
- Write docstrings

### Example

```python
"""
Module for data processing.

This module provides utilities for processing NPS datasets.
"""

from typing import List, Optional

import polars as pl


def process_data(
    df: pl.DataFrame,
    sanitize: bool = True,
    excel_safe: bool = True,
) -> pl.DataFrame:
    """
    Process and clean dataset.

    Args:
        df: Input DataFrame
        sanitize: Apply XSS protection
        excel_safe: Apply Excel formula protection

    Returns:
        Cleaned DataFrame

    Raises:
        ValueError: If DataFrame is empty

    Example:
        >>> df = pl.DataFrame({"text": ["Hello", "World"]})
        >>> clean_df = process_data(df)
    """
    if df.height == 0:
        raise ValueError("DataFrame is empty")

    # Processing logic here
    return df
```

## Performance Guidelines

### Optimization Priorities

1. Use Polars instead of pandas (10x faster)
2. Use ONNX INT8 for ML inference (4x faster)
3. Use sharded SQLite for writes (100x faster)
4. Use vectorized operations
5. Avoid Python loops over large data

### Example

```python
# ❌ Bad: Slow pandas + Python loop
for row in df.iterrows():
    df.at[row, 'clean'] = clean_text(row['text'])

# ✅ Good: Fast Polars + vectorized
df = df.with_columns(
    pl.col('text')
    .map_elements(clean_text, return_dtype=pl.Utf8)
    .alias('clean')
)
```

## Security Guidelines

### Security Priorities

1. **Input validation**: Never trust user input
2. **XSS protection**: 6-layer defense-in-depth
3. **Excel injection**: Always escape formulas
4. **Rate limiting**: Prevent abuse
5. **File validation**: Check type, size, content

### Example

```python
from shared.security import sanitize_text, FileValidator

# Input validation
FileValidator.validate_file(file_path)

# XSS protection
clean_text = sanitize_text(user_input, excel_safe=True)

# Rate limiting
rate_limiter.check(client_ip)
```

## Documentation

### What to Document

- Public functions/classes (docstrings)
- Complex algorithms (inline comments)
- Configuration options (.env.example)
- API endpoints (OpenAPI/FastAPI)
- Architecture decisions (docs/)

### Documentation Style

```python
def complex_function(param1: str, param2: int) -> dict:
    """
    One-line summary of function.

    Longer description explaining what the function does,
    why it exists, and any important details.

    Args:
        param1: Description of param1
        param2: Description of param2

    Returns:
        Description of return value

    Raises:
        ValueError: When does this happen
        TypeError: When does this happen

    Example:
        >>> result = complex_function("test", 42)
        >>> print(result)
        {'status': 'success'}

    Note:
        Any important notes or caveats
    """
    pass
```

## Pull Request Process

### Before Submitting

- [ ] Tests pass locally (`make test`)
- [ ] Code quality checks pass (`make ci`)
- [ ] Documentation updated
- [ ] CHANGELOG.md updated (if applicable)
- [ ] Commit messages follow convention

### PR Description Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Integration tests added/updated
- [ ] Security tests added/updated
- [ ] Performance tests added/updated
- [ ] All tests pass

## Checklist
- [ ] Code follows style guidelines
- [ ] Documentation updated
- [ ] No security vulnerabilities introduced
- [ ] Performance impact considered
```

### Review Process

1. Automated CI checks must pass
2. At least one maintainer review required
3. Security-sensitive changes require security review
4. Performance-critical changes require benchmark results

## Questions?

- Open an issue for discussion
- Join community discussions
- Read documentation

Thank you for contributing! 🎉
