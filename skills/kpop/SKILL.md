---
name: kpop
description: >-
  Karl Popper-inspired scientific reasoning.
disable-model-invocation: true
---

### KPOP: Apply this method to the user's problem.

Restate the problem clearly.
do
 **Hypothesize**: Hypothesize one falsifiable explanation of the cause of the problem.
 **Predict**: Define a falsifying test. If the hypothesis were true, what outcome would the test produce?
 **Falsify**: Run the test. If falsified, reject the hypothesis.

until you think you've solved the problem

Log all hypotheses and results -- as they become available, DON'T WAIT UNTIL THE END -- to an .md file specified by the user (or else,
 if the user doesn't specify, log to _kpop/exp_log_{name}.md, where you invent a meaningful {name}).

At the end of the log, write a brief executive summary (maybe with a table?). Follow it with a super-brief tl;dr. Echo the
 executive summary and tl;dr to the user chat (the context).

You have a budget of 10 hypotheses, unless the user specifies otherwise.
