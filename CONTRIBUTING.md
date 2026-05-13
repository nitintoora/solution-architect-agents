# Contributing to solution-architect-agents

Thanks for your interest in contributing! This project is primarily improved through better prompts — you don't need to write Python to make a meaningful contribution.

## Ways to contribute

### Improve a prompt (highest impact)
All agent prompts live in `src/prompts/` as plain markdown files. If you find wording that produces consistently better output, open a PR with:
- The changed prompt file
- A brief explanation of what you changed and why
- Example output showing the improvement (before/after if possible)

### Add an agent
1. Add `src/agents/<name>.py` — follow the pattern in existing agents
2. Add `src/prompts/<name>.md`
3. Add the new output fields to `ArchitectureState` in `src/state.py`
4. Wire the agent into the graph in `src/graph.py`
5. Update `src/utils/output_writer.py` if the agent produces a new output file

### Report a bug
Open a GitHub issue with:
- What you ran (command + input snippet)
- What you expected
- What actually happened (output or error)

### Fix a bug or add a feature
1. Fork the repo and create a branch from `master`
2. Make your change
3. Run the tests: `pytest tests/`
4. Open a PR with a clear description of what changed and why

## Development setup

```bash
git clone https://github.com/nitintoora/solution-architect-agents
cd solution-architect-agents
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install pytest pytest-mock
cp .env.example .env        # add your ANTHROPIC_API_KEY
```

## Running tests

Tests mock the Claude API — no credits consumed.

```bash
pytest tests/ -v
```

## PR guidelines

- Keep PRs focused — one change per PR
- If you change a prompt, include example output showing the improvement
- Tests must pass before merging
- Update the README if you add user-visible behaviour

## Code style

No formatter is enforced yet. Follow the style of the surrounding code — clear variable names, short functions, no clever one-liners.
