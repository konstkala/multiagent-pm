"""Claude Code PreToolUse hook: blocks shell commands that are hard to undo.

Claude Code sends the tool call as JSON on stdin; exit code 2 blocks it and shows stderr to
Claude, which then asks the user to run the command themselves. A guard against accidents,
not an adversary: it looks at commands, not at text such as commit messages.
"""

import json
import re
import sys

# Where a command can start: beginning of a line, or after ; & | ( and optional spaces.
START = r"(?:^|[;&|(])\s*"
BLOCKED = [
    (START + r"git\s+push\b[^\n]*\s(--force\S*|-f)(\s|$)", "a force push rewrites published history"),
    (START + r"git\s+push\b[^\n]*\s\+\S", "a +branch push is a force push"),
    (START + r"git\s+filter-(branch|repo)\b", "it rewrites every commit"),
    (START + r"gh\s+repo\s+delete\b", "it deletes the repository"),
    (START + r"gh\s+repo\s+edit\b[^\n]*--visibility", "it changes who can see the repository"),
    (START + r"terraform\s+(apply|destroy)\b", "it changes real cloud resources"),
]
# The body of a heredoc (<<'EOF' ... EOF) is text, e.g. a commit message: not a command.
HEREDOC = re.compile(r"<<-?\s*['\"]?(\w+)['\"]?[^\n]*\n.*?\n\s*\1\s*(?:\n|$)", re.DOTALL)


def blocked_reason(command: str) -> str | None:
    code = HEREDOC.sub("\n", command)
    for pattern, why in BLOCKED:
        if re.search(pattern, code, re.MULTILINE):
            return why
    return None


def main() -> None:
    event = json.load(sys.stdin)
    why = blocked_reason(str(event.get("tool_input", {}).get("command", "")))
    if why:
        print(
            f"Blocked by .claude/hooks/guard_commands.py: {why}. "
            "Show the user the exact command and let them run it.",
            file=sys.stderr,
        )
        sys.exit(2)


if __name__ == "__main__":
    main()
