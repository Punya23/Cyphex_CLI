"""RouteTracer maps DAST/DeepAgent dynamic findings back to source files so
the patch pipeline can fix them; unmapped findings stay "no source to patch"
forever and can never clear from the security score. A real scan showed
IDOR/mass-assignment findings like /api/users/1, /api/users/9999999999999999,
and /api/admin/users/1?isAdmin=true staying unpatchable — the before/after
score was stuck at 16/100 across repeated patch runs because these Criticals
never cleared. Root cause: _regex_route_match used the URL's literal last
path segment as the route name to search for — for these findings that's the
numeric resource id itself, which no codebase search can ever match. These
tests pin the fix: skip id-like segments and match routes registered with a
:id/{id} placeholder.
"""
import os
import tempfile

from backend.council.route_tracer import RouteTracer, _looks_like_id

try:
    from models.scan import Vuln
except ImportError:
    from backend.backend.models.scan import Vuln


class TestLooksLikeId:
    def test_plain_digits_of_any_length_are_ids(self):
        assert _looks_like_id("1") is True
        assert _looks_like_id("9999999999999999") is True

    def test_uuid_shaped_token_is_an_id(self):
        assert _looks_like_id("550e8400-e29b-41d4-a716-446655440000") is True

    def test_resource_names_are_not_ids(self):
        assert _looks_like_id("users") is False
        assert _looks_like_id("admin") is False
        assert _looks_like_id("unsafe-search") is False


class TestRegexRouteMatch:
    def _tracer_with_file(self, rel_path: str, content: str) -> RouteTracer:
        tmpdir = tempfile.mkdtemp()
        full = os.path.join(tmpdir, rel_path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)
        return RouteTracer(tmpdir)

    def test_numeric_id_path_resolves_via_the_param_route_not_the_literal_id(self):
        """The real bug: /api/users/1 must NOT search for a route named '1'."""
        tracer = self._tracer_with_file(
            "src/routes/users.js",
            "router.get('/users/:id', (req, res) => { res.json(db.find(req.params.id)); });\n",
        )
        resolved = tracer._regex_route_match("/api/users/1")
        assert resolved is not None
        assert "users.js" in resolved

    def test_huge_numeric_id_also_resolves(self):
        tracer = self._tracer_with_file(
            "src/routes/users.js",
            "router.get('/users/:id', handler);\n",
        )
        assert tracer._regex_route_match("/api/users/9999999999999999") is not None

    def test_mass_assignment_put_with_id_resolves(self):
        tracer = self._tracer_with_file(
            "src/routes/users.js",
            "router.put('/users/:id', handler);\n",
        )
        assert tracer._regex_route_match("/api/users/1") is not None

    def test_admin_users_with_trailing_id_and_query_resolves_on_admin_segment(self):
        # Realistic Express sub-router: app.use('/admin', adminRouter) mounts
        # adminRouter, whose own routes are registered bare ('/users', not
        # '/admin/users') — RouteTracer only sees this file's own text.
        tracer = self._tracer_with_file(
            "src/routes/admin.js",
            "router.get('/users', handler);\n",
        )
        # urlparse already strips the query string before this is called —
        # mirror that here, same as RouteTracer.resolve_dast_vulns() does.
        assert tracer._regex_route_match("/api/admin/users/1") is not None

    def test_route_with_no_id_param_still_matches_as_before(self):
        tracer = self._tracer_with_file(
            "src/routes/orders.js",
            "router.post('/lookup', handler);\n",
        )
        assert tracer._regex_route_match("/api/orders/lookup") is not None

    def test_fastapi_style_brace_param_resolves(self):
        tracer = self._tracer_with_file(
            "app/routes.py",
            "@app.get('/users/{id}')\ndef get_user(id: int): ...\n",
        )
        assert tracer._regex_route_match("/api/users/1") is not None

    def test_truly_unroutable_path_still_returns_none(self):
        tracer = self._tracer_with_file(
            "src/routes/orders.js",
            "router.post('/orders/lookup', handler);\n",
        )
        assert tracer._regex_route_match("/api/completely/made/up/path") is None


class TestResolveDastVulnsEndToEnd:
    def test_idor_finding_gets_mapped_to_file_and_line(self):
        tmpdir = tempfile.mkdtemp()
        routes_dir = os.path.join(tmpdir, "src", "routes")
        os.makedirs(routes_dir)
        with open(os.path.join(routes_dir, "users.js"), "w", encoding="utf-8") as f:
            f.write("const express = require('express');\n")
            f.write("router.get('/users/:id', (req, res) => {});\n")

        tracer = RouteTracer(tmpdir)
        idor_vuln = Vuln(
            name="[DYNAMIC] IDOR with Admin Privileges",
            severity="Critical",
            endpoint="http://localhost:1234/api/users/1",
            evidence="", cwe="CWE-284", description="",
        )
        tracer.resolve_dast_vulns([idor_vuln])

        assert "users.js" in idor_vuln.endpoint
        assert "no source" not in idor_vuln.endpoint.lower()
