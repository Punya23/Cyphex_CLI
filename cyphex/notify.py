"""Cyphex Buddy: friendly scan updates for Slack / Google Chat incoming webhooks.

URLs come from CYPHEX_WEBHOOK_URLS (comma-separated) or --notify-webhook. The
payload is picked by URL: Google Chat gets a card, Slack gets Block Kit, anything
else gets plain text. Buttons are link buttons: an incoming webhook cannot
receive clicks, so approving/merging happens on the PR page they open
(shortcut: a true in-chat Approve button needs a Chat/Slack app, build it when asked).
"""
import html
import json
import os
import pathlib
import re
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

# One worker keeps messages in order; Python joins it at exit so the last one still sends.
_pool = ThreadPoolExecutor(max_workers=1)
BUDDY = "Cyphex Buddy 🛡️"
# Chat/Slack fetch the avatar themselves, so it must be a public https URL (a local path can't work).
# Serves assets/buddy/cyphex_buddy.png from main; CYPHEX_BUDDY_ICON_URL overrides it to host elsewhere.
DEFAULT_ICON = "https://raw.githubusercontent.com/vedant91/Cyphex_CLI/main/assets/buddy/cyphex_buddy.png"


def icon_url() -> str:
    return os.environ.get("CYPHEX_BUDDY_ICON_URL") or DEFAULT_ICON
SEV = {"Critical": "🔴", "High": "🟠", "Medium": "🟡", "Low": "🔵", "Info": "🔵"}

STEP_SAYS = (  # (keyword in the engine's step title, what the buddy says)
    ("SOURCE", "📥 Making a safe copy of your code. Your original stays untouched."),
    ("STATIC", "🔍 Reading your code for weak spots, without running it."),
    ("SANDBOX", "📦 Starting your app in an isolated sandbox so I can test it safely."),
    ("NETWORK", "🌐 Looking at the network around your app for exposed services."),
    ("DYNAMIC", "⚡ Testing your running app the way an attacker would."),
    ("SIMULATION", "🥊 Throwing fake attacks at my defences to see what gets blocked."),  # before GENOME: its title contains both
    ("GENOME", "🧬 Learning what normal traffic looks like so odd requests stand out."),
    ("REPORT", "📝 Writing up what I found."),
    ("PATCH", "🛠️ Writing fixes and proving each one works before I keep it."),
)


def _store() -> pathlib.Path:
    return pathlib.Path(os.environ.get("CYPHEX_WEBHOOKS_FILE") or pathlib.Path.home() / ".cyphex" / "webhooks.json")


def saved_urls() -> list[str]:
    try:
        return [u for u in json.loads(_store().read_text()) if isinstance(u, str)]
    except Exception:
        return []  # missing or corrupt file just means "nothing connected"


def _save(urls: list[str]) -> None:
    path = _store()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_text(json.dumps(urls))
    path.chmod(0o600)  # the URLs are secrets


def webhook_urls() -> list[str]:
    """Env/flag URLs first, then those connected with /webhook; https only (the URL is a secret)."""
    urls = [u.strip() for u in os.environ.get("CYPHEX_WEBHOOK_URLS", "").split(",")] + saved_urls()
    return list(dict.fromkeys(u for u in urls if u.startswith("https://")))


def platform(url: str) -> str:
    for host, name in (("chat.googleapis.com", "Google Chat"), ("hooks.slack.com", "Slack"),
                       ("office.com", "Microsoft Teams"), ("logic.azure.com", "Microsoft Teams")):
        if host in url:
            return name
    return "Webhook"


def looks_like_webhook(text: str) -> bool:
    """True for a pasted chat-webhook URL, so a bare paste is never mistaken for a scan target."""
    t = text.strip()
    return " " not in t and t.startswith("https://") and platform(t) != "Webhook"


def label(url: str) -> str:
    """Safe-to-print description of a webhook: platform + space id, never the key/token."""
    m = re.search(r"/spaces/([^/?]+)", url)
    return f"{platform(url)} · space {m.group(1)}" if m else f"{platform(url)} · …{url.split('?')[0][-6:]}"


def _payload(url, headline, lines, buttons, subtitle):
    plain = "\n".join([headline, *lines])
    esc = html.escape  # finding names come from the scanned app: never trust them as markup
    buttons = [(t, u) for t, u in buttons if u.startswith("https://")]
    if "chat.googleapis.com" in url:
        widgets = [{"textParagraph": {"text": "<br>".join([f"<b>{esc(headline)}</b>", *map(esc, lines)])}}]
        if buttons:
            widgets.append({"buttonList": {"buttons": [
                {"text": t, "onClick": {"openLink": {"url": u}}} for t, u in buttons]}})
        return {"cardsV2": [{"cardId": "cyphex", "card": {
            "header": {"title": BUDDY, "subtitle": subtitle,
                       "imageUrl": icon_url(), "imageType": "CIRCLE"},
            "sections": [{"widgets": widgets}]}}]}
    if "hooks.slack.com" in url:
        blocks = [{"type": "section", "text": {"type": "mrkdwn",
                   "text": "\n".join([f"*{esc(headline)}*", *map(esc, lines)])}},
                  {"type": "context", "elements": [
                      {"type": "image", "image_url": icon_url(), "alt_text": "Cyphex Buddy"},
                      {"type": "mrkdwn", "text": f"{BUDDY} · {esc(subtitle)}"}]}]
        if buttons:
            blocks.append({"type": "actions", "elements": [
                {"type": "button", "text": {"type": "plain_text", "text": t}, "url": u} for t, u in buttons]})
        return {"text": plain, "blocks": blocks}
    return {"text": plain}


def _send_now(url: str, body: dict) -> str:
    req = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as r:
        return r.read().decode(errors="replace")


def _post(url: str, body: dict) -> None:
    try:
        _send_now(url, body)
    except Exception:
        pass  # a chat outage must never break a scan; never print the URL (secret)


def connect(url: str) -> dict:
    """Validate a webhook by posting a hello card, and remember it only if the chat accepted it.
    Returns {"ok", "label", "error"}."""
    url = url.strip()
    if not url.startswith("https://"):
        return {"ok": False, "error": "A webhook link starts with https://"}
    hello = _payload(url, "✅ Connected! I'm your Cyphex Buddy, and I'll post every security scan here.",
                     ["I'll tell you what I'm testing, what I find, and when a fix is ready for you to approve. 🛡️"],
                     [], "webhook connected")
    try:
        reply = _send_now(url, hello)
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": f"{platform(url)} rejected that link (HTTP {e.code}). Copy it again from the space settings."}
    except Exception as e:
        return {"ok": False, "error": f"Could not reach it ({type(e).__name__}). Check the link and your network."}
    name = label(url)
    try:  # Google Chat answers with the space it posted to; Slack only says "ok"
        name = f"{platform(url)} · {json.loads(reply)['name'].split('/messages')[0]}"
    except Exception:
        pass
    _save(list(dict.fromkeys([*saved_urls(), url])))
    return {"ok": True, "label": name}


def disconnect(which: str) -> int:
    """Remove one saved webhook by its 1-based number, or all with 'all'. Returns how many were removed."""
    urls = saved_urls()
    keep = [] if which == "all" else [u for i, u in enumerate(urls, 1) if str(i) != which]
    _save(keep)
    return len(urls) - len(keep)


def send(headline, lines=(), buttons=(), subtitle=""):
    for url in webhook_urls():
        _pool.submit(_post, url, _payload(url, headline, list(lines), buttons, subtitle))


def step(scan_id, num, title):
    says = next((s for k, s in STEP_SAYS if k in title.upper()), f"▶️ {title.title()}")
    send(says, subtitle=f"scan {scan_id} · step {num}")


def report(scan_id, label, score, counts, findings):
    """counts: (critical, high, medium, low); findings: [(severity, name), ...]"""
    c, h, m, lo = counts
    total = c + h + m + lo
    head = ("🎉 All clear! I couldn't find anything wrong."
            if not total else f"🔎 Scan done: I found {total} issue{'s' if total != 1 else ''}. Security score {score}/100 ({label}).")
    lines = [f"🔴 {c} critical · 🟠 {h} high · 🟡 {m} medium · 🔵 {lo} low"]
    if findings:
        lines.append("Worst first:")
        lines += [f"{SEV.get(s, '•')} {n}" for s, n in findings[:3]]
        lines.append("Next I'll try to fix what I can and prove each fix works. 🛠️")
    send(head, lines, subtitle=f"scan {scan_id}")


def merge_verdict(score_after, critical_left, applied, total):
    """Traffic light for the approver: (emoji, headline)."""
    if critical_left == 0 and total and applied == total:
        return "🟢", "Looks safe to merge"
    if critical_left == 0 and applied:
        return "🟡", "Merge with care: some issues are still open"
    return "🔴", "Not ready to merge: critical issues remain"


def review_card(scan_id, branch, score_before, score_after, critical_left, applied, total, pr_url=""):
    light, verdict = merge_verdict(score_after, critical_left, applied, total)
    lines = [
        f"✅ Score: {score_before} → {score_after}/100",
        f"🛠️ Fixes kept: {applied} of {total} (each one re-checked after patching)",
        f"{'✅' if not critical_left else '⚠️'} Critical issues left: {critical_left}",
        "⚠️ I verified fixes statically (syntax + re-scan). Please run your own tests before merging.",
        f"🌿 Branch: {branch}",
        "👇 These buttons open GitHub, where the approval and merge are recorded.",
    ]
    buttons = [("👀 Review changes", pr_url), ("✅ Approve & merge on GitHub", pr_url)] if pr_url else []
    send(f"{light} PR ready for your review: {verdict}", lines, buttons, subtitle=f"scan {scan_id}")
