# Reflection: Static Analysis of the Warehouse Stock Manager

## 1. Which issues were the easiest to fix, and which were the hardest? Why?

The easiest were mechanical: unused imports and variables, snake_case naming, docstrings, `with open(...)`, and the `__main__` guard. They didn't change behavior and the tools pointed straight at them. The hardest were replacing `eval()` with an AST-based `safe_eval`, removing the bare `except: pass` (which meant choosing error policies and updating callers), and adding input validation that no tool flagged. These were harder because they involved design decisions that rippled into other code.

## 2. Did the static analysis tools report any false positives? If so, describe one example.

Yes. Bandit flags `hashlib.md5` in `sku_checksum` as a weak hash (B324), but it is only a 6-character fingerprint for printed bin labels, not a security feature. I fixed it with `usedforsecurity=False` and a docstring note instead of silencing the warning. The `global` warning in `loadStock` was also only partly useful, since the real issue is the module-level state.

## 3. How would you integrate static analysis tools into your actual software development workflow?

I'd run Ruff/Pylint in the editor for instant feedback, and use pre-commit hooks (Ruff, Bandit, a secrets scanner) so issues like the hardcoded password never get committed. CI would then run Pylint, Bandit and mypy with the tests on every pull request and fail on high-severity findings. Config files would live in the repo, and suppressions like `# nosec` would require a written justification.

## 4. What tangible improvements did you observe in the code quality, readability, or potential robustness after applying the fixes?

The code is safer: no `eval()` and no hardcoded password (it now comes from an environment variable). It is more robust: invalid SKUs and quantities, overselling and unknown SKUs now raise clear errors instead of failing silently, and the shared mutable default `history=[]` is fixed. It is also more readable, with PEP 8 names, docstrings, constants, a shorter `check_reorder`, and a module that can be imported and tested without running the demo.