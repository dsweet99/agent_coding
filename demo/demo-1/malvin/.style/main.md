# Project Style Guide

## Quality Gates (Run Frequently)
```bash
cd /home/dsweet/coding && ruff check . && kiss check . && pytest -v
```

- **ruff**: Line length 88, Python 3.9+
- **kiss**: 90% coverage, max indent 4, no duplication, ≤5 statements per try block
- **pytest**: All tests must pass

## Hard Constraints
- Never modify `.kissconfig`
- No `# noqa` except for correct code functioning
- All checks must pass on ALL files - no "pre-existing issue" excuses
- Run checks frequently; don't batch cleanup at end

## Codebase Structure
```
knn_cli/           # Main package
  cli.py           # Argparse CLI entry point
  commands.py      # Command implementations (create, add_csv, query_csv)
  csv_io.py        # CSV reading/writing with validation
  dataset.py       # Dataset storage (~/.knn_cli/datasets/)
  predictor.py     # KNN regression engine (see .style/algorithms.md)
tests/
  conftest.py      # Shared fixtures (temp_data_dir)
  test_*.py        # Unit tests
```

## Code Patterns

### Error Messages
Must be "explicit and actionable" - include file path, line number, expected vs actual.

### CLI Flags
- Destructive ops (overwrite, delete) require explicit flags (e.g., `--overwrite`)
- Error without flag: `"Dataset '{name}' already exists. Use --overwrite to replace it."`

### CSV Validation
- Reject NaN/Infinity: use `math.isfinite()` after `float()` conversion
- Validate row lengths match header column count
- Reject header-only files (no data rows)
- Clear error: `"Row {n} has {x} columns, expected {y} in {filepath}"`

### Command Pre-conditions
- Validate dataset state before operations (e.g., has training data before query)
- Actionable errors: `"Dataset '{name}' has no training data. Use add-csv to add observations before querying."`

### Atomic File Operations
- Use temp file + `os.replace()` for writes that must not corrupt on failure
- Pattern: `tempfile.mkstemp()` → write → `os.replace()` → cleanup on error
- Extract `_write_*_content()` helper to keep try block ≤5 statements
- Test that failed operations preserve existing data

### CLI Error Handling
- Catch `ValueError`, `FileNotFoundError`, and `OSError` in main()
- `OSError` covers `PermissionError`, disk full, read-only filesystem

### Ruff Line Length Fixes
- Extract variables: `got = features.shape[1]` before f-string
- Split long strings across lines with parentheses

### kiss Coverage & Deduplication
- Test all public functions directly
- Test all validation paths (empty names, invalid values, duplicates)
- Use shared fixtures in `conftest.py` to avoid duplication
- Use `@pytest.mark.parametrize("fn", [fn1, fn2])` to test multiple implementations without kiss duplication violations

### Benchmark & Determinism Tests
- **Determinism**: Test same data → identical output; fresh dataset recreation → same results
- **Scale test**: 10k train × 10k query × 100 features; baseline ~3.4s, threshold <60s
- Quality reports go in task folder as `quality_report.md`

## Workflow
- Work without asking for input; use best judgment
- Be tenacious about fixing all issues
- When review.md exists, address all concerns listed

## Index
- **Algorithm & storage details** (KNN, vectorized distance, memory optimization, NPY format decision): `.style/algorithms.md`
