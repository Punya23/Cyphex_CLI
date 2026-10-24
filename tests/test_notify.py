import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from cyphex import notify as n

CHAT = "https://chat.googleapis.com/v1/spaces/X/messages?key=k&token=t"
SLACK = "https://hooks.slack.com/services/T/B/x"


def test_only_https_urls_are_used(monkeypatch):
    monkeypatch.setenv("CYPHEX_WEBHOOK_URLS", "http://insecure.example/x, https://hooks.slack.com/a ,")
    assert n.webhook_urls() == ["https://hooks.slack.com/a"]


def test_google_chat_gets_card_with_link_buttons():
    p = n._payload(CHAT, "Head", ["l1"], [("Review", "https://github.com/o/r/pull/1"), ("bad", "http://x")], "scan 1")
    widgets = p["cardsV2"][0]["card"]["sections"][0]["widgets"]
    buttons = widgets[1]["buttonList"]["buttons"]
    assert [b["text"] for b in buttons] == ["Review"]  # non-https button dropped
    assert buttons[0]["onClick"]["openLink"]["url"] == "https://github.com/o/r/pull/1"


def test_buddy_avatar_in_chat_header_and_slack_context(monkeypatch):
    monkeypatch.setenv("CYPHEX_BUDDY_ICON_URL", "https://cdn.example/buddy.png")
    head = n._payload(CHAT, "h", [], [], "s")["cardsV2"][0]["card"]["header"]
    assert head["imageUrl"] == "https://cdn.example/buddy.png" and head["imageType"] == "CIRCLE"
    ctx = n._payload(SLACK, "h", [], [], "s")["blocks"][1]["elements"][0]
    assert ctx == {"type": "image", "image_url": "https://cdn.example/buddy.png", "alt_text": "Cyphex Buddy"}


def test_default_icon_points_at_committed_asset(monkeypatch):
    monkeypatch.delenv("CYPHEX_BUDDY_ICON_URL", raising=False)
    assert n.icon_url().endswith("assets/buddy/cyphex_buddy.png")


def test_slack_gets_blocks_and_unknown_gets_text():
    p = n._payload(SLACK, "Head", ["l1"], [("Review", "https://github.com/o/r/pull/1")], "scan 1")
    assert p["blocks"][-1]["type"] == "actions" and p["text"].startswith("Head")
    assert n._payload("https://other.example/h", "Head", ["l1"], [], "") == {"text": "Head\nl1"}


def test_untrusted_finding_names_are_escaped():
    p = n._payload(CHAT, "h", ["<script>alert(1)</script>"], [], "")
    assert "<script>" not in p["cardsV2"][0]["card"]["sections"][0]["widgets"][0]["textParagraph"]["text"]


def test_merge_verdict_traffic_light():
    assert n.merge_verdict(80, 0, 3, 3)[0] == "🟢"
    assert n.merge_verdict(60, 0, 2, 3)[0] == "🟡"
    assert n.merge_verdict(17, 3, 6, 10)[0] == "🔴"


def test_step_uses_friendly_text(monkeypatch):
    sent = []
    monkeypatch.setattr(n, "send", lambda headline, lines=(), buttons=(), subtitle="": sent.append(headline))
    n.step("cli_1", "2/9", "STATIC CODE ANALYSIS")
    assert "weak spots" in sent[0]
    n.step("cli_1", "6/9", "AI ATTACK SIMULATION - GENOME DEFENSE")
    assert "fake attacks" in sent[1]


def test_post_sends_json_and_survives_dead_url():
    got = []

    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            got.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            self.send_response(200)
            self.end_headers()

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.handle_request, daemon=True).start()
    n._post(f"http://127.0.0.1:{srv.server_port}/", {"text": "*hi*"})
    assert got == [{"text": "*hi*"}]
    n._post("http://127.0.0.1:1/", {"text": "dead"})  # must not raise


def _fresh_store(monkeypatch, tmp_path):
    monkeypatch.setenv("CYPHEX_WEBHOOKS_FILE", str(tmp_path / "hooks.json"))
    monkeypatch.delenv("CYPHEX_WEBHOOK_URLS", raising=False)


def test_connect_saves_and_scans_use_it(monkeypatch, tmp_path):
    _fresh_store(monkeypatch, tmp_path)
    monkeypatch.setattr(n, "_send_now", lambda url, body: '{"name": "spaces/AAA/messages/m1"}')
    res = n.connect(CHAT)
    assert res == {"ok": True, "label": "Google Chat · spaces/AAA"}
    assert n.webhook_urls() == [CHAT]  # a later scan (even another process) picks it up
    if os.name != "nt":  # Windows has no POSIX file modes
        assert oct((tmp_path / "hooks.json").stat().st_mode & 0o777) == "0o600"


def test_connect_rejected_or_insecure_is_not_saved(monkeypatch, tmp_path):
    _fresh_store(monkeypatch, tmp_path)

    def boom(url, body):
        raise n.urllib.error.HTTPError(url, 400, "bad", {}, None)
    monkeypatch.setattr(n, "_send_now", boom)
    bad = n.connect(CHAT)
    assert not bad["ok"] and "400" in bad["error"] and "token=t" not in bad["error"]
    assert not n.connect("http://insecure.example/x")["ok"]
    assert n.saved_urls() == []


def test_label_never_leaks_the_secret():
    assert "key=k" not in n.label(CHAT) and "token=t" not in n.label(CHAT)
    assert "services/T/B/x" not in n.label(SLACK)


def test_pasted_link_detection():
    assert n.looks_like_webhook(CHAT) and n.looks_like_webhook(SLACK)
    assert not n.looks_like_webhook("https://github.com/o/r")  # a repo link is still a scan target
    assert not n.looks_like_webhook("scan https://hooks.slack.com/a")


def test_disconnect(monkeypatch, tmp_path):
    _fresh_store(monkeypatch, tmp_path)
    n._save([CHAT, SLACK])
    assert n.disconnect("1") == 1 and n.saved_urls() == [SLACK]
    assert n.disconnect("all") == 1 and n.saved_urls() == []
