# Task 05 - Requirement Change: Forecast Method Rename

Product language changed: `naive` should now be called `last-value`.

## Requirements
- Replace user-facing method name `naive` with `last-value`.
- Keep backward compatibility:
  - old configs/data referencing `naive` must still work
  - store or display the canonical new name going forward
- Update help text, docs, and tests to prefer `last-value`.

## Constraints
- Existing user workflows must not break.
- Migration/alias handling must be explicit and test-covered.

## Acceptance Criteria
- `forecast run ... --method last-value` works.
- `--method naive` still works as an alias.
- Outputs and docs consistently use `last-value`.
