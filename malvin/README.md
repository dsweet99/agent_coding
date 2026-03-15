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


## Development
```bash
pip install -e requirements.txt
cargo install kiss-ai
```
