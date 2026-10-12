"""Regression: keyword_lines must survive stray separators in a line.

str.splitlines() splits on \\x0c, and run() reads git output in text
mode, which turns a bare \\r into \\n. Either one cuts a grep line in
two, and the second piece has no "path:N:" prefix, so it must not
yield an anchor.
"""

import importlib.util
import subprocess
import sys
import types
from pathlib import Path

RUN_PY = Path(__file__).resolve().parents[1] / "benchmarks" / "tokens" / "run.py"


class _StubEncoding:
    def encode(self, text, **_kwargs):
        return list(text)  # one token per character; counts only need to be positive


def _load_run(monkeypatch):
    # run.py imports tiktoken at module level and builds its encoding
    # at import time. tiktoken is not a dev dependency and the real
    # encoding needs network, so swap in a stub for this test.
    stub = types.ModuleType("tiktoken")
    stub.get_encoding = lambda _name: _StubEncoding()
    monkeypatch.setitem(sys.modules, "tiktoken", stub)
    spec = importlib.util.spec_from_file_location("token_benchmark_run", RUN_PY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _keyword_lines_for(tmp_path, monkeypatch, content):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "a.py").write_bytes(content)
    subprocess.run(["git", "add", "a.py"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"],
        cwd=tmp_path,
        check=True,
    )
    return _load_run(monkeypatch).keyword_lines(tmp_path, "a.py", ["foo"])


def test_keyword_lines_keeps_line_with_form_feed(tmp_path, monkeypatch):
    cost, lines = _keyword_lines_for(
        tmp_path, monkeypatch, b"x = 1\nfoo = 'a\x0cb'\nfoo_again = 2\n"
    )

    assert lines == [2, 3]
    assert cost > 0


def test_keyword_lines_keeps_line_with_bare_carriage_return(tmp_path, monkeypatch):
    cost, lines = _keyword_lines_for(
        tmp_path, monkeypatch, b"x = 1\nfoo = 'a\rb'\nfoo_again = 2\n"
    )

    assert lines == [2, 3]
    assert cost > 0
