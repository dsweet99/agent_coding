# FIRST RULE OF CURSOR - MANDATORY: READ THIS FIRST
MANDATORY FIRST ACTION: When the user sends their first request in a conversation, you MUST immediately read style.md using the read_file tool BEFORE performing any other action (no searches, no code reading, no tool calls of any kind). This is the absolute first step - do not answer the question, do not search, do not read other files. Read style.md first, then proceed with the user's request.

--

### Claims vs Hypotheses

- Label uncertain reasoning as Hypothesis; only use Claim with explicit evidence.
- Claims must cite evidence (code refs, logs, metrics). Otherwise, downgrade to Hypothesis.
- For each Hypothesis, include:
  - Hypothesis: concise, falsifiable statement.
  - Predictions: measurable outcomes if true.
  - Test: minimal experiment (setup, variables, metrics, pass/fail).
  - Confounders: likely alternatives and controls.
- Language:
  - Hypothesis: “suggests”, “may”, “indicates”.
  - Claim (with evidence): “shows”, “demonstrates”, “causes”.
- Label any statement which is a hypothesis as a hypothesis.


--

When running python code, you'll need to set PYTHONPATH

--

NEVER CALL GIT

--

# Coding Rules
When you write code, always make sure these checks pass.
### Python
- pytest -sv tests
- ruff check
- kiss check
### Rust
- cargo clippy --all-targets --all-features -- -D warnings
- cargo test

Iterate until they do.

--

# Debugging process rule

When debugging: run the broken code first to observe the actual failure, write a test that reproduces that exact failure, then fix it. Don't guess—observe empirically. Replicate the exact code path that fails in the test, not a simplified version. The broken code is the source of truth; observe it directly before fixing.
--


Acronyms we can use to make communication more efficient:
DCC: Don't Change Code. Repond to the user's query, but don't change *any* code.
--
