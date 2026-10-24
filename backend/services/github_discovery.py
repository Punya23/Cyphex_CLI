"""CYPHEX — organization-wide microservice discovery.

Given ONE repo (the "main" repo CYPHEX was pointed at), finds its sibling
microservices living as SEPARATE repos in the same GitHub org — not folders
in one monorepo, that's backend.services.service_discovery's job — then
clones every match into one local folder shaped exactly like that module
expects, so the existing detect_and_build_service_graph() / Phase 2 pivot /
Phase 3 multi-deploy pipeline runs on it completely unchanged.

Two directions, both cheap (no cloning of candidates):
  - outbound: main repo's own outbound-call hints (the same regex extraction
    service_discovery already does) matched against the org's repo names.
  - inbound: GitHub code search for the main repo's name across the whole
    org — which other repos mention it in their own source, i.e. call it.

Scope: discovery + assembly only, gated on GITHUB_TOKEN being set (same env
var cyphex/github_hook.py already uses) so an ordinary scan is untouched.
The org-wide webhook that would trigger this on every push is a separate
piece, not built here.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from urllib.parse import urlparse

import httpx

from backend.services.service_discovery import _normalize, discover_outbound_edges

GITHUB_API = "https://api.github.com"


def repo_owner_and_name(repo_url: str) -> tuple[str, str] | None:
    """'https://github.com/acme/whatsapp-broadcast(.git)' -> ('acme', 'whatsapp-broadcast').
    None for anything that isn't a github.com repo URL."""
    parsed = urlparse(repo_url)
    if "github.com" not in parsed.netloc.lower():
        return None
    parts = [p for p in parsed.path.strip("/").split("/") if p]
    if len(parts) < 2:
        return None
    name = parts[1]
    if name.endswith(".git"):
        name = name[:-4]
    return parts[0], name


def _clone_shallow(repo_url: str, dest: str, branch: str = "") -> bool:
    """Same hardened clone cli_engine._get_source uses for the scan's main
    repo — kept as its own small copy here (this module has no dependency
    on cli_engine) rather than threading a shared import through for one
    call site. Any change to the validation rules must be mirrored in both
    places."""
    if repo_url.startswith("-") or (branch and branch.startswith("-")):
        return False
    if not (repo_url.startswith("https://") or repo_url.startswith("git@")
            or repo_url.startswith("ssh://")):
        return False
    git_env = {**os.environ, "GIT_ALLOW_PROTOCOL": "https:ssh:git"}
    cmd = ["git", "clone", "--depth", "1"]
    if branch:
        cmd += ["-b", branch]
    cmd += ["--", repo_url, dest]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120, env=git_env)
    except Exception:
        return False
    return proc.returncode == 0


async def list_org_repos(org: str, token: str = "") -> list[dict]:
    """Every repo in a GitHub org, paginated — [{"name", "clone_url"}].
    Works unauthenticated for a public org too, just rate-limited; an empty
    list on any non-200 (bad org, no access, rate limited) rather than
    raising — callers treat "found nothing" as the honest failure mode."""
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    repos: list[dict] = []
    page = 1
    async with httpx.AsyncClient(timeout=15.0) as client:
        while True:
            try:
                res = await client.get(
                    f"{GITHUB_API}/orgs/{org}/repos",
                    headers=headers, params={"per_page": 100, "page": page},
                )
            except Exception:
                break
            if res.status_code != 200:
                break
            batch = res.json()
            if not batch:
                break
            repos.extend({"name": r["name"], "clone_url": r["clone_url"]} for r in batch)
            if len(batch) < 100:
                break
            page += 1
    return repos


async def search_org_code_for_term(org: str, term: str, token: str) -> list[str]:
    """Repo names in `org` whose code mentions `term` — GitHub's code
    search covers the whole org in one query, no cloning. Requires an
    authenticated token (GitHub blocks unauthenticated code search); an
    empty list on any failure, same honest-failure convention as
    list_org_repos."""
    if not token:
        return []
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            res = await client.get(
                f"{GITHUB_API}/search/code",
                headers=headers, params={"q": f"{term} org:{org}", "per_page": 50},
            )
    except Exception:
        return []
    if res.status_code != 200:
        return []
    items = res.json().get("items") or []
    return sorted({item["repository"]["name"] for item in items if item.get("repository")})


async def find_linked_repos(main_repo_dir: str, main_repo_name: str,
                             org: str, token: str = "") -> list[dict]:
    """Which other repos in `org` are this one's microservice siblings —
    outbound (main repo calls them, by name/env-var hint) and inbound
    (their code mentions main repo's name, by GitHub code search)."""
    org_repos = await list_org_repos(org, token)
    if not org_repos:
        return []
    by_name = {r["name"]: r for r in org_repos if r["name"] != main_repo_name}

    edges = discover_outbound_edges(main_repo_name, main_repo_dir)
    hints_norm = [_normalize(e.target_hint) for e in edges]
    outbound = {
        name for name in by_name
        if _normalize(name) and any(_normalize(name) in h for h in hints_norm)
    }

    inbound = set(await search_org_code_for_term(org, main_repo_name, token)) & set(by_name)

    linked = outbound | inbound
    return [by_name[name] for name in linked]


def assemble_workspace(main_repo_url: str, main_repo_name: str,
                        linked_repos: list[dict], workdir: str,
                        branch: str = "") -> dict:
    """Clone the main repo + every linked repo as sibling subfolders of
    `workdir` — the exact shape service_discovery.detect_services() expects.
    Returns {"cloned": [names], "failed": [names]}; a repo that fails to
    clone is listed in "failed" and simply isn't a subfolder, same as
    multi_deploy's honest status-on-failure convention."""
    os.makedirs(workdir, exist_ok=True)
    cloned, failed = [], []
    all_repos = [(main_repo_name, main_repo_url)] + [
        (r["name"], r["clone_url"]) for r in linked_repos
    ]
    for name, url in all_repos:
        dest = os.path.join(workdir, name)
        if _clone_shallow(url, dest, branch):
            cloned.append(name)
        else:
            failed.append(name)
    return {"cloned": cloned, "failed": failed}


async def discover_and_assemble_org(main_repo_url: str, workdir: str,
                                     branch: str = "", token: str = "") -> dict | None:
    """Top-level entry point. Clones the main repo alone into a throwaway
    probe folder to read its outbound calls, finds its linked siblings in
    the same org, then clones everything (main repo included — a second,
    still-shallow clone, kept simple over reusing an earlier clone of it)
    into one workdir. Returns None — caller falls back to a normal
    single-repo clone — when main_repo_url isn't a GitHub URL, the probe
    clone fails, or the main repo itself couldn't be cloned into workdir."""
    owner_name = repo_owner_and_name(main_repo_url)
    if not owner_name:
        return None
    org, main_repo_name = owner_name

    probe_dir = os.path.join(workdir, f".__probe_{main_repo_name}")
    if not _clone_shallow(main_repo_url, probe_dir, branch):
        return None
    try:
        linked = await find_linked_repos(probe_dir, main_repo_name, org, token)
    finally:
        shutil.rmtree(probe_dir, ignore_errors=True)

    result = assemble_workspace(main_repo_url, main_repo_name, linked, workdir, branch)
    if main_repo_name not in result["cloned"]:
        return None
    return {"org": org, "main_repo": main_repo_name, **result}
