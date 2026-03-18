# Task 04 - Forecast Baselines and Error Metrics

Add simple forecasting and evaluation support.

## Requirements
- Implement `forecast run --series <id> --method <name> --horizon <n>`.
- Required methods:
  - `naive` (repeat last value)
  - `moving-average` (use trailing window)
- Implement `forecast evaluate --series <id> --method <name>` with rolling one-step prediction.
- Report at least MAE and RMSE.

## Constraints
- Keep method behavior deterministic.
- Validate horizon and window arguments.

## Acceptance Criteria
- Forecast command outputs predicted values.
- Evaluate command outputs correct MAE/RMSE for known datasets.
