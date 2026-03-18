# Task 00 - Bootstrap SequenceLab CLI

Create the initial Python project structure and runnable CLI skeleton.

## Requirements
- Add a Python package named `sequencelab`.
- Add an entry point so the app runs as:
  - `python -m sequencelab --help`
- Add placeholder command groups:
  - `series`
  - `stats`
  - `forecast`
- Each placeholder should print a clear "not implemented yet" message and exit successfully.
- Add a short README section with run instructions.

## Constraints
- Keep dependencies minimal.
- Only scaffold command wiring in this task.

## Acceptance Criteria
- `python -m sequencelab --help` shows commands.
- `python -m sequencelab series --help` (and others) works.
- Project layout is ready for later tasks.
