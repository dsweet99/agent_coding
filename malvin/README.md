# malvin

`malvin` is a CLI that orchestrates implementation and review loops with `cursor-agent`.

## Installation

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
