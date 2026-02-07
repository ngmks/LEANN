---
name: index-sessions
description: Set up automatic LEANN indexation of Claude Code sessions for the current project.
disable-model-invocation: true
---

# Set up LEANN session indexation

Run the setup script:

```bash
~/.claude/skills/index-sessions/scripts/setup.sh "$(pwd)" "${CLAUDE_SESSION_ID}"
```

Report the output to the user. If it fails, show the error message.
