# TASK-01 - Dataset Lifecycle and Persistent Metadata

## Summary
Harden dataset creation and persistence so datasets are reusable across separate CLI invocations.

## Objective
Ensure a created dataset can be loaded later with consistent dimensionality and identity.

## Requirements
- Persist dataset metadata locally, including dataset name and dimension.
- Prevent duplicate dataset creation unless an explicit overwrite option exists.
- Validate dimension as a positive integer.
- Return clear errors for unknown dataset names.
- Keep behavior deterministic and predictable across runs.

## Acceptance Criteria
- `create --dataset X --dimension 100` persists metadata and is visible to subsequent commands.
- Re-running create for the same dataset without explicit overwrite fails with clear guidance.
- Commands fail cleanly when a dataset has not been created.
