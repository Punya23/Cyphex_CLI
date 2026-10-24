"""_run_network_scan() port-scans the WHOLE local subnet ("auto" discovery),
not just this scan's own sandbox — a "[NETWORK]" finding can be an unrelated
device on the user's LAN (their own router's Telnet, another machine's SSH).
A real scan showed exactly this: the before/after security score stayed
stuck in the 16-24 range across repeated patch runs even after every
app-code finding was patched, because 1-4 "[NETWORK]" findings with no
source file permanently capped the score (one open Critical alone caps it
near 38). _exclude_network_findings() keeps them out of the score while
still leaving them visible in the report and final banner's raw counts.
"""
import cli_engine


class _V:
    def __init__(self, name, severity="Critical"):
        self.name = name
        self.severity = severity


def test_network_findings_are_dropped():
    vulns = [
        _V("[NETWORK] Telnet exposed on port 23"),
        _V("[NETWORK] HTTP exposed on port 80", severity="High"),
    ]
    assert cli_engine._exclude_network_findings(vulns) == []


def test_app_findings_are_kept_network_findings_are_not():
    app_sqli = _V("[STATIC] SQL Injection (String Concatenation)")
    app_ssti = _V("[DYNAMIC] Server-Side Template Injection — jinja2")
    network = _V("[NETWORK] Telnet exposed on port 23")
    result = cli_engine._exclude_network_findings([app_sqli, app_ssti, network])
    assert result == [app_sqli, app_ssti]


def test_empty_list_stays_empty():
    assert cli_engine._exclude_network_findings([]) == []


def test_untagged_findings_are_kept_not_mistaken_for_network():
    untagged = _V("Reflected XSS")
    assert cli_engine._exclude_network_findings([untagged]) == [untagged]


def test_excluding_the_only_open_critical_lets_the_score_clear_the_ceiling():
    """The real-world payoff: scoring.py's own documented invariant caps the
    score near 38 while ANY Critical is open. A lone [NETWORK] Critical with
    everything else clean used to cap every scan at ~38 forever; excluding
    it lets a fully-patched app actually reach a high score."""
    from scoring import score_from_counts

    vulns = [_V("[NETWORK] Telnet exposed on port 23", severity="Critical")]
    scoreable = cli_engine._exclude_network_findings(vulns)
    crit = sum(1 for v in scoreable if v.severity == "Critical")
    assert crit == 0
    assert score_from_counts(crit, 0, 0, 0) == 100
