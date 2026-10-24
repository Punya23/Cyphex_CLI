"""CyphexEngine._try_assemble_org(): gated on a token being available
(GITHUB_TOKEN, or the one `gh auth login` already has) so an ordinary scan
is unaffected when neither exists; delegates to backend.services.
github_discovery once a token is found.
"""
from unittest.mock import AsyncMock, patch

import pytest

from cli_engine import CyphexEngine


def _engine():
    engine = CyphexEngine()
    engine.scan_id = "scantest"
    return engine


@pytest.mark.asyncio
async def test_no_token_anywhere_returns_none_without_touching_github():
    engine = _engine()
    with patch("backend.services.github_discovery.resolve_github_token", return_value=""), \
         patch("backend.services.github_discovery.discover_and_assemble_org") as mock_discover:
        result = await engine._try_assemble_org("https://github.com/acme/main-repo", "main")
    assert result is None
    mock_discover.assert_not_called()


@pytest.mark.asyncio
async def test_token_found_delegates_to_github_discovery():
    engine = _engine()
    expected = {"org": "acme", "main_repo": "main-repo",
                "cloned": ["main-repo", "sibling-service"], "failed": []}
    with patch("backend.services.github_discovery.resolve_github_token", return_value="tok123"), \
         patch("backend.services.github_discovery.discover_and_assemble_org",
               new=AsyncMock(return_value=expected)) as mock_discover:
        result = await engine._try_assemble_org("https://github.com/acme/main-repo", "main")
    assert result == expected
    mock_discover.assert_called_once()
    args, kwargs = mock_discover.call_args
    assert args[0] == "https://github.com/acme/main-repo"
    assert "tok123" in args or "tok123" in kwargs.values()


@pytest.mark.asyncio
async def test_discovery_failure_degrades_to_none_not_a_crash():
    engine = _engine()
    with patch("backend.services.github_discovery.resolve_github_token", return_value="tok123"), \
         patch("backend.services.github_discovery.discover_and_assemble_org",
               new=AsyncMock(side_effect=RuntimeError("github is down"))):
        result = await engine._try_assemble_org("https://github.com/acme/main-repo", "main")
    assert result is None
