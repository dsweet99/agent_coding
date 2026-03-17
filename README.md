
# Dave's Agent Coding Workflow

- `rules.md` - This goes into every context. For Cursor this is `.cursorrules`.
- `commands/*.md` - These are called into a context by name. For example, "/kpop".

## Cursor setup
```
cp rules.md /path/to/your/repo/.cursorrules
mkdir -p /path/to/your/repo/.cursor/commands
cp commands/*.md /path/to/your/repo/.cursor/commands
```

# How I Code (20260315)

## Plan
I write a brief descripton of what I want, then I type
```
/rr
```
Then I look over `plan.md`, especially the questions. If there are any unanswered questions, I put my
 answers in `plan.md`. I also add my notes on anything else that catches my eye. All of my edits begin
 with "[dsweet]".

If it's a big plan, I'll run
```
/kpop Check plan.md
```
[KPop](https://github.com/dsweet99/agent_coding/blob/main/commands/kpop.md) (named for philospher of science, [Karl Popper](https://en.wikipedia.org/wiki/Karl_Popper)) shows up a lot in my work. It instructs the agent to treat the text as a set of hypotheses
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
/kpop Falsify review.md
```
(odd phrasing, but go with it)
Then, back in the implementer's context, I'll call
```
/concerns
```
which fixes the code based on `review.md`.
I repeat these steps -- `/review_1`, `/kpop`, `/concerns` -- until the reviewer says "LGTM".
Then I repeat them *again* using `/review_2`, which is a more fine-grained review.

### Serious coding
The **Code** and **Review** sections can be combined and automated by a simple [Python script](https://github.com/dsweet99/agent_coding/tree/main/malvin) calling out to `cursor-agent`. For serious work, I do the planning interactively in Cursor and then call something like

```
malvin plan.md
```
that carries out the implementation and review cycles.

With a little bookeeping, you can get multiple coding agents going at the same time.

## Bugs and performance optimization
Coding agents are great at fixing difficult bugs and squeezing performance out of your code. You just need to tell
them how to go about it.

### Bugs
I'll describe a bug and point to the evidence or a shell command that demostrates it so that
the agent can see the problem. Then I'll type something like
```
/kpop Fix the bug. You have a budget of 30 hypotheses.
```
If you give the agent a budget, it'll keep working instead of a pausing and asking, `Do you want me to try this?` or
whatever it's trained to do to save tokens. It'll really stop at 30 hypotheses, though, so it won't go off the rails
and spend all your tokens.

It'll generate one hypothesis at a time and test it, either by running the broken code or searching for evidence in the logs
or maybe even writing a new bit of code as a side-test. It's pretty clever.

### Performance
If I want to speed up code, limit memory use, etc. I'll ask the agent to develop a metric, like
- a timing script or log messages timing pieces of code
- log messages reporting memory usage

If you can measure it, you can improve it.

Then I'll say
```
/kpop Reduce the time by 50%. You have a budget of 30 hypotheses.
```
It's key to name the metric and the goal as well as give a budget. Then the agent knows how aggressive it has to be,
and it knows when to stop. If you say you're looking for a 10% improvement, it'll look for tweaks. If you say you're
looking for a 90% improvement, it'll be more bold.

This all might look familiar if you follow social media, as Andrej Karpathy recently popularized his [autoresearch](https://x.com/karpathy/status/2030371219518931079?s=20)
 which is very similar.

### Tough problems
Sometimes I'll read through the hypotheses and see that the agent is kind of milling around a small area
in the "space of ideas" and not improving the metrics. To solve tough problems, it needs to get creative.

Philosopher and cognitive scientist [Margaret Boden](https://en.wikipedia.org/wiki/Margaret_Boden) studied creativity and
classified it into three levels. The first level is the "milling around" that the agent does naturally. To get the
agent to be more creative, we need to activate [level 2](https://github.com/dsweet99/agent_coding/blob/main/commands/mbc2.md)
creativity:

```
/mbc2 Generate 5 ideas for solving this problem.
```
Write the above in your agent and be amazed. Your agent can be *very* creative if you ask it to be.

Once you have the ideas, you can get back to testing them:
```
/kpop Draw upon the ideas above to reduce the time by 50%. You have a budget of 30 hypotheses.
```

or you can be more focused:
```
/kpop Falsify each of the ideas above.
```

## Memory
If you look at the [rules](https://github.com/dsweet99/agent_coding/blob/main/rules.md), you'll see the "First rule of Cursor" is
 to read in `style.md`, yet there is no `style.md` in this repo. The file `style.md` is created by the [/learn](https://github.com/dsweet99/agent_coding/blob/main/commands/learn.md)
 command.

At the end of a planning or coding session, I call
```
/learn
```
This instructs the agent to identify and store a few new things it learned during this session. "New things" come from my expressing
 me preferences, from `/kpop` experiments, and from feedback from the linters and tests. You'll notice the stored information pop up
 in future sessions.

## Global information / Stopping "Wack-A-Mole"
Agents get a very localized view of a problem since their context is built from snippets of code that it thinks it needs to
 solve a particular problem. What's gets lost is the "big picture":

- The overall plan for the codebase
- The overall structure of the codebase

This leads to steadily-increasing complexity, duplicate code, leaky abstractions, and this annoying feeling that
 you're playing wack-a-mole with the agent.

To fix these problems, I do two things:
- `grounding.md`: I manually maintain files called `grounding.md` in the repo. I put them in any subdirectory where I think they're needed. They
 contain the broad objectives and constraints of the project -- not implementation details.  For example, I might write,
  "This module contains statistical sampling functions." or "These functions should stay O(N)." At planning and review time the agent will
  be instructed to look at `grounding.md` and will be less likely to put non-statistical sampling functions in that module. KPop will be
  more likely to measure the scaling of a function it thinks might violate the O(N) constraint.
- [kiss check](https://github.com/dsweet99/kiss): `kiss` is a linter that looks at the full codebase, builds a
  graph, and reports to the agent problems of too much complexity, duplicate code, orphaned code, and low test coverage.
