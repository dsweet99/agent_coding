# Task 01 - Series CRUD and Persistence

Implement core dataset management with local persistence.

## Requirements
- Add persistent local storage for named numeric series.
- A series must include:
  - `id` (stable unique identifier)
  - `name`
  - `values` (ordered list of floats)
  - `created_at`
  - `updated_at`
- Implement commands:
  - `series add`
  - `series list`
  - `series show`
  - `series update`
  - `series delete`
- `series show` must print values in their original order.

## Constraints
- Validate that values are numeric.
- Preserve data between runs.

## Acceptance Criteria
- User can create/read/update/delete series from CLI.
- Unknown IDs return clear errors.
- Data survives process restarts.
