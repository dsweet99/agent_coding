# malvin

`malvin` implement's [Dave's coding workflow](https://github.com/dsweet99/agent_coding/tree/main).

## Installation

Install `cursor-agent`: [https://cursor.com/blog/cli](https://cursor.com/blog/cli)
It's also just called `agent`, but either name should work. Be sure to get yourself authenticated.

```bash
pip install -e .
```

## Usage
```
malvin plan.md
```

If you want to watch the agent work on stdout:
```
malvin --tee plan.md
```

Code will be written in `./`. Logs will be in `./_malvin`.


## Demo
I asked Cursor (calling GPT-5.3 Codex) to image an application the produce a `grounding.md` file that described it along with 10 tasks files (think Jira tickets). I compared two agents
- `plain` - This is `cursor-agent` running Opus-4.5, called once for each task file.
- `malvin` - This is `malvin`.
Both agents were aware of the `grounding.md` file.  Their output is in `demo/demo-1/`.


### Results: malvin
`malvin`'s code worked:
```
$ ./demo-1/evaluate.py 'python /home/dsweet/out/malvin/knn_cli/cli.py'
EVAL_RESULT dataset=benchmark seed=20260318 n_train=10000 n_test=10000 dimension=100 train_chunks=10 test_chunks=10 rmse=8.40451281 time_create_s=0.185535 time_add_s=2.406298 time_query_s=5.944037 time_total_s=8.535871
```
It's predictions aren't great, but grounding didn't mention tuning the model. When asked to inpect malvin's code, Cursor (calling GPT-5.3 Codex) reports:
```
Me: Please read over the code.  Does the KNN algorithm makes sense? Does the querying make sense?
Cursor(GPT-5.3 Codex): Yes — for the intended CLI inference workflow, it mostly makes sense.

KNN logic is structurally correct: computes Euclidean distances with the standard identity, selects k nearest via argpartition, and predicts by averaging neighbor targets (knn_cli/predictor.py).
Query flow is coherent: query-csv validates dataset + dimensions, reads query features, loads training data, predicts, and writes one prediction per row without mutating training state (knn_cli/commands.py, knn_cli/csv_io.py).
Behavior is tested well: repeated query calls, row-order preservation, error paths, and scale sanity are covered; local run shows 71 passed.
```

### Results: plain
Plain `cursor-agent`'s code did not run according to spec.

It failed with
```
$ ./demo-1/evaluate.py 'python /home/dsweet/out/plain/knn_cli.py'
Traceback (most recent call last):
  File "/home/dsweet/Projects/agent_coding/demo/./demo-1/evaluate.py", line 341, in <module>
    main()
  File "/home/dsweet/Projects/agent_coding/demo/./demo-1/evaluate.py", line 322, in main
    metrics = _evaluate(config)
              ^^^^^^^^^^^^^^^^^
  File "/home/dsweet/Projects/agent_coding/demo/./demo-1/evaluate.py", line 278, in _evaluate
    t_add += _run_cli(
             ^^^^^^^^^
  File "/home/dsweet/Projects/agent_coding/demo/./demo-1/evaluate.py", line 204, in _run_cli
    raise RuntimeError(f"Command failed ({completed.returncode}): {' '.join(command)}\n{err}")
RuntimeError: Command failed (1): python /home/dsweet/out/plain/knn_cli.py add-csv --dataset benchmark --file /tmp/knn_eval_gkrv8ifs/train_chunk_000.csv
Error: Row 1, column 1 in '/tmp/knn_eval_gkrv8ifs/train_chunk_000.csv' contains non-numeric value: 'x0'.
```
When asked to inpect malvin's code, Cursor (calling GPT-5.3 Codex) reports:
```
Me: Please read over the code.  Does the KNN algorithm makes sense? Does the querying make sense?
Cursor(GPT-5.3 Codex):
Findings
High – CSV contract mismatch with benchmark inputs (headers).
validate_csv_file() parses every row as numeric and never skips a header row, so files with x0,x1,... fail immediately. The shared benchmark/eval flow writes header rows, so this breaks compatibility there.
Medium – Non-finite values (nan, inf) are accepted.
Since validation only checks float(...) conversion, nan/inf pass and can silently poison distances/predictions.

Low – Output path behavior is a bit brittle.
Temp output is created in . if parent dir doesn’t exist; final replace() can fail late with a generic write error instead of clear “parent directory missing”.
```


## Development
```bash
pip install -e requirements.txt
cargo install kiss-ai
```
