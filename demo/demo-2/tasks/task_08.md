# Task 08 - Change: CSV Import/Export

Integrations need simple file exchange with spreadsheets.

## Requirements
- Add:
  - `series import-csv --name <name> --file <path>`
  - `series export-csv --series <id> --file <path>`
- CSV format: one numeric value per line (header optional but supported).
- Validate and report malformed rows with line numbers.
- Preserve existing JSON/local storage as the system of record.

## Constraints
- Import should not create partial corrupt series on failure.
- Export must be deterministic and documented.

## Acceptance Criteria
- Valid CSV imports into a usable series.
- Exported CSV can be re-imported with equivalent values.
- Invalid CSV gives actionable validation errors.
