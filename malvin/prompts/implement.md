Implement the plan in the file specified by the user: `{{ plan_path }}`.

Use parallelized subagents.

Work until the end without asking for user input. If you are uncertain about an implementation
detail, use your best judgement. There will always be an opportunity to revise later on.


Be sure that all checks pass:
- ruff
- cargo clippy
- kiss
and all unit tests pass:
- pytest
- cargo test

Run checks & tests frequently to avoid a big cleanup at the end.
