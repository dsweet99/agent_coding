# Storage Format Benchmark Report

## Configuration

- Training observations: 10,000
- Query observations: 10,000
- Features: 100
- Benchmark runs: 3

## Results

| Metric | CSV (Option A) | NumPy Binary (Option B) | Winner |
|--------|----------------|------------------------|--------|
| Dataset load time | 0.6729s | 0.0021s | NumPy (317.2x faster) |
| Query startup latency | 4.4930s | 3.8222s | NumPy |
| On-disk size | 18.92 MB | 7.71 MB | NumPy (2.5x smaller) |

## Analysis

### Load Time

NumPy binary format loads 317.2x faster than CSV. This is because NumPy's `.npy` format stores data in a direct binary representation that can be memory-mapped without parsing, while CSV requires text parsing and float conversion for each value.

### Disk Size

NumPy binary format uses 2.5x less disk space than CSV. CSV stores each float as text (typically 15-20 characters per value), while NumPy stores each float64 as exactly 8 bytes.

## Decision

**Selected Format: NumPy binary**

The NumPy binary format is selected based on winning 3 of 3 measured criteria. The performance gains in load time and reduced disk footprint make NumPy binary the better choice for the target scale (10K observations, 100 features).

## Validation

- Repeated `add-csv` operations verified to append correctly
- CLI contract remains unchanged (same flags and semantics)
- Output behavior preserved
