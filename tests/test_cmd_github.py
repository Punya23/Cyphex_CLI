"""cx.py's /github slash command: status display and its two independent
ways to connect — gh auth login (interactive, inherits the terminal) and
pasting a personal access token directly via /github token.
"""
from unittest.mock import patch

import pytest

pytest.importorskip("fcntl", reason="cx.py is POSIX-only")

import cx


def _no_saved_token():
    return patch("backend.services.github_discovery.load_saved_token", return_value="")


def test_status_warns_when_no_token_anywhere(capsys, monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    with _no_saved_token(), \
         patch("backend.services.github_discovery.resolve_github_token", return_value=""):
        cx._cmd_github("")
    out = capsys.readouterr().out
    assert "No GitHub token found" in out
    assert "/github login" in out
    assert "/github token" in out


def test_status_shows_env_var_source(capsys, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "tok123")
    with _no_saved_token(), \
         patch("backend.services.github_discovery.resolve_github_token", return_value="tok123"):
        cx._cmd_github("")
    assert "GITHUB_TOKEN environment variable" in capsys.readouterr().out


def test_status_shows_saved_token_source(capsys, monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    with patch("backend.services.github_discovery.load_saved_token", return_value="saved-tok"):
        cx._cmd_github("")
    assert "saved via /github token" in capsys.readouterr().out


def test_status_shows_gh_cli_source(capsys, monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    with _no_saved_token(), \
         patch("backend.services.github_discovery.resolve_github_token", return_value="gh-token"):
        cx._cmd_github("")
    assert "gh CLI auth" in capsys.readouterr().out


# ── /github login ────────────────────────────────────────────────────────

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


# ── /github token ────────────────────────────────────────────────────────

def test_token_inline_saves_and_reports_authenticated_user(capsys):
    with patch("cx._verify_github_token", return_value="octocat") as mock_verify, \
         patch("backend.services.github_discovery.save_token") as mock_save:
        cx._cmd_github("token ghp_abc123")
    mock_verify.assert_called_once_with("ghp_abc123")
    mock_save.assert_called_once_with("ghp_abc123")
    assert "Authenticated as octocat" in capsys.readouterr().out


def test_token_inline_saves_even_when_verification_fails(capsys):
    """The user explicitly chose this token — save it regardless, just warn
    that GitHub didn't accept it (could be a transient network issue)."""
    with patch("cx._verify_github_token", return_value=""), \
         patch("backend.services.github_discovery.save_token") as mock_save:
        cx._cmd_github("token ghp_bad")
    mock_save.assert_called_once_with("ghp_bad")
    assert "didn't accept it" in capsys.readouterr().out


def test_token_no_inline_arg_prompts_hidden_input(capsys):
    with patch("cx.getpass.getpass", return_value="from-prompt") as mock_getpass, \
         patch("cx._verify_github_token", return_value="someone"), \
         patch("backend.services.github_discovery.save_token") as mock_save:
        cx._cmd_github("token")
    mock_getpass.assert_called_once()
    mock_save.assert_called_once_with("from-prompt")


def test_token_empty_prompt_saves_nothing(capsys):
    with patch("cx.getpass.getpass", return_value="   "), \
         patch("backend.services.github_discovery.save_token") as mock_save:
        cx._cmd_github("token")
    mock_save.assert_not_called()
    assert "No token entered" in capsys.readouterr().out


# ── /github clear ────────────────────────────────────────────────────────

def test_clear_reports_removed(capsys):
    with patch("backend.services.github_discovery.clear_saved_token", return_value=True):
        cx._cmd_github("clear")
    assert "Removed the saved token" in capsys.readouterr().out


def test_clear_reports_nothing_to_remove(capsys):
    with patch("backend.services.github_discovery.clear_saved_token", return_value=False):
        cx._cmd_github("clear")
    assert "nothing to remove" in capsys.readouterr().out
