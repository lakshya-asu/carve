# pkgname

Template package. Copy, rename `pkgname` everywhere, delete this line.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
ruff format . && ruff check . && mypy src && pytest
```
