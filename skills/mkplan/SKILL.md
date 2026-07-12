---
name: mkplan
description: >-
  Research the codebase and write an implementation plan to plan.md (or a user-specified file).
  Use when the user invokes mkplan, asks to "make a plan", or wants a structured plan before coding.
disable-model-invocation: true
---

# mkplan

**Plan only — do not implement.** Research the codebase, write the plan file, and stop unless the user explicitly asks you to execute it.

## Inputs

- **USER_REQUEST** — the change or question from the user (this conversation turn, or text they point at).
- **PLAN_FILE** — `plan.md` unless the user names another file.

## Process

1. Read USER_REQUEST and identify PLAN_FILE.
2. Research the codebase (grep, read relevant files, trace call paths).
3. Write PLAN_FILE using the template below.
4. In **Q&A**, list open questions first, then research and add **Answer:** blocks under each question. If nothing is unclear after research, write `None`.
5. In **Plan**, break work into implementation phase(s). Each phase ends with concrete validation steps.

Do not edit application code, tests, or config while running this skill — only PLAN_FILE.
Do not make anything optional. Either require it, or just don't mention it in the plan.

## Document template

Use this skeleton. Keep **Current State** factual (what exists today); keep **Requested Changes** normative (what should change).

```markdown
# Plan: <short title>

## User Request

<echo USER_REQUEST; use the user's wording when possible>

## Current State

### <topic>

- Relevant files, modules, and behaviors.
- Include **adjacent** state: code that might be affected even if not explicitly mentioned.
- Use tables, file paths, and short code references where they aid navigation.

## Requested Changes

1. <change>
2. <change>

## Q&A

### Q1. <question>?

**Answer:** <research-backed answer with file paths / behavior>

(or: None)

## Plan

### Phase 1 — <title>

- [ ] <task>
- [ ] <task>

**Validation:** <how to verify this phase>

### Phase 2 — <title> (only if needed)

- [ ] <task>

**Validation:** <how to verify this phase>
```

## Section rules

### User Request

- Default: echo USER_REQUEST verbatim or as a tight bullet list.
- Shorten only when the user pasted a long thread — then summarize the decision they want, and say you summarized.

### Current State

- Describe structure **and** runtime behavior, not just file names.
- Call out gaps, dead code, tests that encode today's behavior, and docs that will need updates.
- Prefer subsections by topic (e.g. `### Prompt assembly`, `### CLI flags`).

### Requested Changes

- One numbered list of outcomes the user asked for.
- Do not mix in implementation steps here — those belong in **Plan**.

### Q&A

- Format each item as `### Qn. …` followed by `**Answer:** …`.
- Ask questions when scope is ambiguous (e.g. two similarly named mechanisms, or delete vs relocate).
- Answer every question you raised; do not leave dangling `TBD`.
- If no questions: section body is exactly `None`.

### Plan

- If the work fits one focused diff, use **Phase 1** only.
- If it spans many files or independent concerns, split into phases the user could land separately.
- Order phases by dependency (types/constants → call sites → tests → docs).

**Validation** (required after every phase — be specific, not "run tests"):

- Name commands: e.g. `cargo test context_recovery`, `malvin do --mini "…"`.
- Name files or assertions: e.g. "assert `trace.jsonl` contains `miniPromptShrink`".
- For doc-only phases: e.g. "grep confirms no references to `header_do.md`".

## Quality bar

- Plans should be readable by someone who has not seen this chat.
- Prefer paths like `src/cli/do_flow_prompt.rs` over vague "the do flow".
- Flag behavioral impact when replacing or removing user-visible behavior.
- Do not invent requirements the user did not ask for; note optional follow-ups separately if useful.

## Example (abbreviated)

```markdown
# Plan: Use header.md in do mode

## User Request

Remove header_do.md; use header.md when in do mode.

## Current State

### Do prompt assembly

`build_do_coder_run_with_store` (`src/cli/do_flow_prompt.rs`) joins header_do.md + do_header.md + user text.

## Requested Changes

1. Delete header_do.md and wire do mode to header.md via `render_header()`.
2. Remove HEADER_DO_MD constant and related tests.

## Q&A

### Q1. Keep do_header.md as the second header?

**Answer:** Yes — only the coding header changes; do_header.md stays.

## Plan

### Phase 1 — Switch do mode to header.md

- [ ] Replace HEADER_DO_MD usage with render_header() in do_flow_prompt.rs
- [ ] Delete default_prompts/header_do.md and DEFAULT_PROMPTS entry
- [ ] Update do_flow_tests.rs and default_prompts/docs/do.md

**Validation:** `cargo test do_flow`; `build_do_coder_run` integration test passes; grep shows no HEADER_DO_MD.
```
