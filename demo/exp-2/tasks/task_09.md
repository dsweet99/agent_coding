# Task 09 - Improvement: Confidence Intervals via Bootstrap

Add uncertainty estimates to forecast evaluation.

## Requirements
- Extend `forecast evaluate` with optional bootstrap confidence intervals for MAE and RMSE.
- Add flag examples such as:
  - `--bootstrap-samples <n>`
  - `--ci <percent>` (for example 95)
- Keep default behavior fast when bootstrap flags are not used.
- Show interval bounds clearly in output.

## Constraints
- Use deterministic seeding when a seed option is provided.
- Validate bootstrap sample count and CI range.
- Update tests to cover interval computation and edge cases.

## Acceptance Criteria
- Evaluation works with and without bootstrap mode.
- Interval output is numerically plausible and reproducible with a fixed seed.
