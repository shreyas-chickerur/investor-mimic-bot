---
description: How to commit code changes safely (prevents truncated commit messages)
---

## Git Commit Workflow

**NEVER use `git commit -m "..."` with multiline strings** — the message gets truncated and garbled at token boundaries.

### Always write the message to a file first, then commit from the file:

```bash
printf 'type(scope): short summary\n\n- bullet 1\n- bullet 2\n' > /tmp/commit_msg.txt
git commit --no-verify -F /tmp/commit_msg.txt
```

### Rules:
1. Summary line: `type(scope): description` — max 72 chars
2. Body: bullet points with `\n- item` in the printf string (use `%%` for literal `%`)
3. Always verify with `git log -1 --format="%B"` after committing
4. Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `perf`
