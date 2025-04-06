# Python Validation

Configuration and tools for Python code validation in ShiftWise.

## Tools

- **Black**: Code formatter (25.1.0)
- **isort**: Import organizer (5.10.1)
- **Flake8**: Linter (7.2.0)

## Quick Start

```bash
# Install tools
pip install black==25.1.0 isort==5.10.1 flake8==7.2.0

# Check code
./validate_python.sh accounts/models.py

# Fix code
./validate_python.sh accounts/models.py --fix
```

## Configuration

The repository includes configuration files:
- `pyproject.toml` - Black and isort settings
- `.flake8` - Flake8 rules

## Validation Script

The included `validate_python.sh` script:
- Tests code before and after changes
- Formats imports with isort
- Formats code style with black
- Lints with flake8

## Tips For Long Lines

Break long model fields at commas:

```python
model_field = models.CharField(
    max_length=100, 
    choices=CHOICES, 
    default="value",
)
```

## Import Organization

Structure imports in the following order:
1. Standard library
2. Third-party packages
3. Django framework
4. Local applications