# agent_coding

Dave's Cursor / Claude prompts.

`rules.md` - This goes into every context. For Cursor this is `.cursorrules`.  
`commands/*.md` - These are called into a context by name. For example, in Cursor, "/kpop".

# How I Code (20260315)

## Plan
I write a brief descripton of what I want, then I type
```
/rr
```
The I look over `plan.md`, especially the questions. If there are any unanswered questions, I put my
 answers in plan.md. I also add my notes on anything else that catches my eye. All of my edits begin
 with "[dsweet]".

If it's a big plan, I'll run
```
/kpop Check plan.md
```
[KPop](https://github.com/dsweet99/agent_coding/blob/main/commands/kpop.md) (named for [Karl Popper](https://en.wikipedia.org/wiki/Karl_Popper)) shows up a lot in my work. It instructs the agent to treat the text as a set of hypotheses
 and to try to falsify them. You might see the agent look for counter-evidence in the code, in the docs, or in
 small, bespoke tests that it writes.

## Code
Next I'll call
```
/implement
```
This implements the plan. When this is done, the code should pass all linters and tests, too.

## Review
In a fresh context, I'll call
```
/review_1
```
```
/kpop Check review.md
```
Then, back in the implementer's context I'll call
```
/concerns
```
which fixes the code based on `review.md`.
I repeat these steps -- `/review_1`, `/kpop`, `/concerns` -- until the reviewer says "LGTM".
Then I repeat them *again* using `/review_2`, which is a more fine-grained review.

## Practical Matters
The whole **Code** section can be done by a simple Python script calling out to `cursor-agent`. My actual
 process is that I do the planning interactively in Cursor and then call something like

```
  nohup ./write_the_code.py &> log
```

With a little bookeeping, you can get multiple coding agents going at the same time.

