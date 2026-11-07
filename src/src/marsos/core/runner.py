"""Run external commands. A dry-run Runner records commands instead of executing them (used by tests and --dry-run)."""
from __future__ import annotations
import os
import subprocess
from dataclasses import dataclass, field
from typing import Callable, Sequence


@dataclass
class Result:
    returncode: int
    stdout: str = ""

    @property
    def ok(self) -> bool:
        return self.returncode == 0


@dataclass
class Runner:
    dry_run: bool = field(default_factory=lambda: os.environ.get("MARSOS_DRY_RUN") == "1")
    history: list[list[str]] = field(default_factory=list)
    stdin_log: list[str | None] = field(default_factory=list)
    canned: dict[str, str] = field(default_factory=dict)  # dry-run stdout by argv[0]

    def run(self, cmd: Sequence[str], *, input: str | None = None, check: bool = False,
            env: dict | None = None, timeout: float | None = None) -> Result:
        cmd = [str(c) for c in cmd]
        self.history.append(cmd)
        self.stdin_log.append(None if input is None else "<input>")
        if self.dry_run:
            return Result(0, self.canned.get(cmd[0], ""))
        try:
            p = subprocess.run(cmd, input=input, capture_output=True, text=True, timeout=timeout,
                               env={**os.environ, **(env or {})})
        except FileNotFoundError:
            res = Result(127, f"{cmd[0]}: not found")
        except subprocess.TimeoutExpired:
            res = Result(124, "timed out")
        else:
            res = Result(p.returncode, (p.stdout or "") + (p.stderr if p.returncode else ""))
        if check and not res.ok:
            raise RuntimeError(f"Command failed ({res.returncode}): {' '.join(cmd)}\n{res.stdout[-800:]}")
        return res

    def stream(self, cmd: Sequence[str], on_line: Callable[[str], None], *, input: str | None = None,
               env: dict | None = None) -> int:
        """Run and call on_line for every output line (splits on \\n and \\r so progress bars work)."""
        cmd = [str(c) for c in cmd]
        self.history.append(cmd)
        self.stdin_log.append(None if input is None else "<input>")
        if self.dry_run:
            return 0
        try:
            p = subprocess.Popen(cmd, stdin=subprocess.PIPE if input is not None else None,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 env={**os.environ, **(env or {})})
        except FileNotFoundError:
            on_line(f"{cmd[0]}: not found")
            return 127
        if input is not None:
            p.stdin.write(input.encode()); p.stdin.close()
        buf = b""
        while True:
            chunk = p.stdout.read1(4096) if hasattr(p.stdout, "read1") else p.stdout.read(4096)
            if not chunk:
                break
            buf += chunk
            parts = buf.replace(b"\r", b"\n").split(b"\n")
            buf = parts.pop()
            for part in parts:
                if part.strip():
                    on_line(part.decode("utf-8", "replace"))
        if buf.strip():
            on_line(buf.decode("utf-8", "replace"))
        return p.wait()

    def commands(self) -> list[str]:
        return [" ".join(c) for c in self.history]
