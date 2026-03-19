# TASK-07 - Decision Ticket: Dataset Storage Format

## Summary
Choose the data storage format that best meets speed and memory objectives for repeated loads/queries.

## Objective
Optimize dataset persistence for practical CLI usage under benchmark conditions.

## Decision Required
Implement either approach A or B, then keep whichever best meets objective criteria:
- **A:** CSV-centric persisted storage
- **B:** NumPy-native binary persisted storage (for example `.npy` / `.npz`)

## Requirements
- Compare both options on:
  - dataset load time
  - query startup latency
  - on-disk size
- Validate that repeated `add-csv` remains correct.
- Document measured outcomes and chosen format.
- Keep output behavior and CLI contract unchanged.

## Acceptance Criteria
- A measurable comparison artifact/report exists for A vs B.
- Selected format is justified by objective metrics.
- Existing commands continue to operate with unchanged flags and semantics.
