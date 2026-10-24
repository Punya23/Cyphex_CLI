"""cx.py's /github slash command: status display and the login flow it
delegates to `gh auth login` for (interactive, inherits the terminal — never
captured, so the browser/device-code prompt actually reaches the user).
"""
from unittest.mock import patch

import pytest

pytest.importorskip("fcntl", reason="cx.py is POSIX-only")

import cx


def test_status_warns_when_no_token_anywhere(capsys, monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    with patch("backend.services.github_discovery.resolve_github_token", return_value=""):
        cx._cmd_github("")
    out = capsys.readouterr().out
    assert "No GitHub token found" in out
    assert "/github login" in out


def test_status_shows_env_var_source(capsys, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "tok123")
    with patch("backend.services.github_discovery.resolve_github_token", return_value="tok123"):
        cx._cmd_github("")
    assert "GITHUB_TOKEN environment variable" in capsys.readouterr().out


def test_status_shows_gh_cli_source(capsys, monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    with patch("backend.services.github_discovery.resolve_github_token", return_value="gh-token"):
        cx._cmd_github("")
    assert "gh CLI auth" in capsys.readouterr().out


def test_login_without_gh_installed_never_calls_subprocess(capsys):
    with patch("cx.shutil.which", return_value=None), \
         patch("cx.subprocess.run") as mock_run:
        cx._cmd_github("login")
    mock_run.assert_not_called()
    assert "gh CLI not found" in capsys.readouterr().out


def test_login_runs_gh_auth_login_interactively_and_reports_success(capsys):
    with patch("cx.shutil.which", return_value="/usr/bin/gh"), \
         patch("cx.subprocess.run") as mock_run, \
         patch("backend.services.github_discovery.resolve_github_token", return_value="new-token"):
        cx._cmd_github("login")
    mock_run.assert_called_once_with(["gh", "auth", "login"])
    assert "Connected" in capsys.readouterr().out


def test_login_reports_warning_when_still_no_token_after_gh_login(capsys):
    with patch("cx.shutil.which", return_value="/usr/bin/gh"), \
         patch("cx.subprocess.run") as mock_run, \
         patch("backend.services.github_discovery.resolve_github_token", return_value=""):
        cx._cmd_github("login")
    assert "Still no token found" in capsys.readouterr().out
