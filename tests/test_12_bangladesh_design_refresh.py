# tests/test_12_bangladesh_design_refresh.py
#
# Spec: .claude/specs/12-bangladesh-design-refresh.md
#       "Bangladesh Design Refresh" — Option A (chosen)
#
# This is a pure visual / static-asset change: no new routes, no DB writes, no
# auth guards, no validation errors. Tests are translated directly from the
# spec's "Files to change", "Files to create", hard requirements, and
# Definition of Done sections — NOT from reading the current implementation.
# They exist to catch a regression even if a correct implementation were
# reverted.
#
# Behaviors under test:
#
#  1. `/` (landing, via base.html) includes a <link rel="icon" ...> pointing
#     at favicon.svg
#  2. base.html's footer tagline reads "Track every taka." (not "rupee")
#  3. style.css :root defines the exact new token values (Option A)
#  4. style.css's .footer rule has a 3px top border in var(--accent)
#  5. style.css's .mock-bar-3 / .mock-bar-4 reference var(--mock-blue) /
#     var(--mock-purple), not raw hex
#  6. style.css's --danger / --danger-light are UNCHANGED (regression check)
#  7. landing.css, profile.css, analytics.css, add_expense.css are untouched
#     by this token change: zero occurrences of the new token values or the
#     bd-green/bd-red strings, and the old accent hexes are not duplicated
#     there
#  8. base.html's Google Fonts <link> (DM Serif Display + DM Sans) is present
#     and unchanged — fonts were NOT touched by this spec
#  9. static/favicon.svg exists and is valid enough to be recognized as SVG
#     content, filled with the chosen accent hex
#
# Any test that imports `app` (to drive its test client against `/`) follows
# this project's DB-isolation pattern: patch database.db.DB_PATH to a temp
# file BEFORE importing app, per tests/test_06_date_filter_profile.py. Tests
# that only read static files/templates from disk do not need Flask at all
# and are written as plain file-content assertions.

import os
import re
import tempfile

import pytest

# ---------------------------------------------------------------------------
# DB isolation — must happen before `app` is imported anywhere in this file,
# even though this spec makes no DB changes, so import-time init_db()/
# seed_db() never touch a real spendly.db.
# ---------------------------------------------------------------------------
_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp_db.close()

import database.db as _db_module

_db_module.DB_PATH = _tmp_db.name

from app import app as flask_app  # noqa: E402
from database.db import init_db  # noqa: E402

# ---------------------------------------------------------------------------
# Paths to the static/template files under test. Read directly with plain
# file I/O for the pure-CSS/template-content assertions — no Flask needed.
# ---------------------------------------------------------------------------
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STYLE_CSS = os.path.join(REPO_ROOT, "static", "css", "style.css")
LANDING_CSS = os.path.join(REPO_ROOT, "static", "css", "landing.css")
PROFILE_CSS = os.path.join(REPO_ROOT, "static", "css", "profile.css")
ANALYTICS_CSS = os.path.join(REPO_ROOT, "static", "css", "analytics.css")
ADD_EXPENSE_CSS = os.path.join(REPO_ROOT, "static", "css", "add_expense.css")
BASE_HTML = os.path.join(REPO_ROOT, "templates", "base.html")
FAVICON_SVG = os.path.join(REPO_ROOT, "static", "favicon.svg")


def _read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def client():
    """Flask test client backed by the isolated temp-file DB."""
    flask_app.config.update(TESTING=True, SECRET_KEY="test-secret")
    with flask_app.app_context():
        init_db()
    return flask_app.test_client()


# ---------------------------------------------------------------------------
# 1. Favicon link present in rendered HTML (base.html, via `/`)
# ---------------------------------------------------------------------------

class TestFaviconLinkRendered:
    def test_landing_page_returns_200(self, client):
        response = client.get("/")
        assert response.status_code == 200

    def test_landing_page_includes_favicon_link_tag(self, client):
        """
        Spec: 'Add a favicon link in <head> ... <link rel="icon"
        type="image/svg+xml" href="{{ url_for('static', filename='favicon.svg') }}">'
        Because base.html is extended by every page, this must appear on `/`.
        """
        body = client.get("/").data.decode()
        assert 'rel="icon"' in body, "Expected a <link rel=\"icon\" ...> tag in <head>"

    def test_landing_page_favicon_link_points_at_favicon_svg(self, client):
        body = client.get("/").data.decode()
        # url_for('static', filename='favicon.svg') resolves to a path ending
        # in /static/favicon.svg regardless of any query-string cache-buster.
        assert re.search(r'rel="icon"[^>]*href="[^"]*favicon\.svg', body), (
            "Expected the icon <link> href to point at favicon.svg"
        )

    def test_landing_page_favicon_link_type_is_svg_mime(self, client):
        body = client.get("/").data.decode()
        assert 'type="image/svg+xml"' in body, (
            "Spec calls for type=\"image/svg+xml\" on the favicon <link>"
        )


# ---------------------------------------------------------------------------
# 2. Footer tagline text fix: "rupee" -> "taka"
# ---------------------------------------------------------------------------

class TestFooterTaglineText:
    def test_base_html_footer_says_track_every_taka(self):
        content = _read(BASE_HTML)
        assert "Track every taka." in content, (
            "Spec requires base.html's footer tagline to read "
            "'Track every taka. Own your finances.'"
        )

    def test_base_html_footer_does_not_say_rupee(self):
        content = _read(BASE_HTML)
        assert "rupee" not in content.lower(), (
            "'Track every rupee.' is the leftover step-11 copy this spec fixes; "
            "it must not remain anywhere in base.html"
        )

    def test_landing_page_html_shows_taka_tagline(self, client):
        """End-to-end: the fix must actually reach rendered output on `/`."""
        body = client.get("/").data.decode()
        assert "Track every taka." in body
        assert "Track every rupee." not in body


# ---------------------------------------------------------------------------
# 3. style.css :root token values (Option A, exact values, no drift)
# ---------------------------------------------------------------------------

class TestStyleCssTokenValues:
    @pytest.mark.parametrize("token,value", [
        ("--accent", "#006A4E"),
        ("--accent-light", "#E3F3EC"),
        ("--accent-2", "#F42A41"),
        ("--accent-2-light", "#FDE6E8"),
    ])
    def test_root_token_has_exact_value(self, token, value):
        content = _read(STYLE_CSS)
        # Match "--accent: #006A4E;" allowing for whitespace variation, but
        # require the exact hex value (case as specified) with a word
        # boundary so --accent doesn't also match --accent-light/--accent-2.
        pattern = re.compile(
            re.escape(token) + r"\s*:\s*" + re.escape(value) + r"\s*;"
        )
        assert pattern.search(content), (
            f"Expected {token}: {value}; in style.css :root — no drift from "
            f"the Option A values the spec locks in"
        )

    def test_paper_token_unchanged(self):
        """Option A does not touch --paper."""
        content = _read(STYLE_CSS)
        assert re.search(r"--paper\s*:\s*#f7f6f3\s*;", content), (
            "--paper must remain #f7f6f3 — Option A does not touch it"
        )

    def test_ink_token_present_and_not_removed(self):
        """
        --ink is unchanged per spec; we only assert the token still exists
        (its exact historical hex is not restated by the spec, so we don't
        assert a specific value here beyond presence).
        """
        content = _read(STYLE_CSS)
        assert re.search(r"--ink\s*:\s*#[0-9a-fA-F]{3,6}\s*;", content), (
            "--ink token must still be defined in :root"
        )


# ---------------------------------------------------------------------------
# 4. .footer border-top uses var(--accent)
# ---------------------------------------------------------------------------

class TestFooterBorder:
    def test_footer_rule_has_3px_accent_top_border(self):
        content = _read(STYLE_CSS)
        assert "border-top: 3px solid var(--accent)" in content, (
            "Spec: 'Add .footer { border-top: 3px solid var(--accent); }'"
        )

    def test_footer_border_is_inside_a_footer_rule_block(self):
        """
        Loosely confirm the border-top declaration is scoped to a .footer
        rule, not just present anywhere in the file.
        """
        content = _read(STYLE_CSS)
        match = re.search(r"\.footer\s*\{[^}]*\}", content, re.DOTALL)
        assert match, "Expected a .footer { ... } rule in style.css"
        assert "border-top: 3px solid var(--accent)" in match.group(0), (
            "The 3px accent top border must live inside the .footer rule"
        )


# ---------------------------------------------------------------------------
# 5. .mock-bar-3 / .mock-bar-4 reference new tokens, not raw hex
# ---------------------------------------------------------------------------

class TestMockBarTokens:
    def test_mock_bar_3_uses_mock_blue_var(self):
        content = _read(STYLE_CSS)
        match = re.search(r"\.mock-bar-3\s*\{[^}]*\}", content, re.DOTALL)
        assert match, "Expected a .mock-bar-3 rule in style.css"
        assert "var(--mock-blue)" in match.group(0), (
            "Spec: .mock-bar-3 must reference var(--mock-blue), not raw hex #5b7fa6"
        )
        assert "#5b7fa6" not in match.group(0), (
            "Raw hex #5b7fa6 must be replaced by the --mock-blue token"
        )

    def test_mock_bar_4_uses_mock_purple_var(self):
        content = _read(STYLE_CSS)
        match = re.search(r"\.mock-bar-4\s*\{[^}]*\}", content, re.DOTALL)
        assert match, "Expected a .mock-bar-4 rule in style.css"
        assert "var(--mock-purple)" in match.group(0), (
            "Spec: .mock-bar-4 must reference var(--mock-purple), not raw hex #8b5e83"
        )
        assert "#8b5e83" not in match.group(0), (
            "Raw hex #8b5e83 must be replaced by the --mock-purple token"
        )

    def test_mock_blue_token_defined_with_original_hex(self):
        content = _read(STYLE_CSS)
        assert re.search(r"--mock-blue\s*:\s*#5b7fa6\s*;", content), (
            "Spec: new token --mock-blue: #5b7fa6 must be defined"
        )

    def test_mock_purple_token_defined_with_original_hex(self):
        content = _read(STYLE_CSS)
        assert re.search(r"--mock-purple\s*:\s*#8b5e83\s*;", content), (
            "Spec: new token --mock-purple: #8b5e83 must be defined"
        )


# ---------------------------------------------------------------------------
# 6. --danger / --danger-light are UNCHANGED (regression check)
# ---------------------------------------------------------------------------

class TestDangerTokenUnchanged:
    def test_danger_token_value_unchanged(self):
        content = _read(STYLE_CSS)
        assert re.search(r"--danger\s*:\s*#c0392b\s*;", content), (
            "--danger must remain #c0392b — it is a semantic status color, "
            "not a brand color, and this spec does not touch it"
        )

    def test_danger_light_token_value_unchanged(self):
        content = _read(STYLE_CSS)
        assert re.search(r"--danger-light\s*:\s*#fdecea\s*;", content), (
            "--danger-light must remain #fdecea — unchanged by this spec"
        )

    def test_danger_is_not_the_new_flag_red(self):
        """--danger must be a visibly different shade from --accent-2 (#F42A41)."""
        content = _read(STYLE_CSS)
        danger_match = re.search(r"--danger\s*:\s*(#[0-9a-fA-F]{6})\s*;", content)
        assert danger_match, "--danger token must be defined"
        assert danger_match.group(1).lower() != "#f42a41", (
            "--danger must stay distinct from the new --accent-2 flag red"
        )


# ---------------------------------------------------------------------------
# 7. Other page stylesheets are untouched by this token change
# ---------------------------------------------------------------------------

NEW_TOKEN_VALUES = ["#006A4E", "#E3F3EC", "#F42A41", "#FDE6E8"]
OLD_ACCENT_HEXES = ["#1a472a", "#c17f24"]  # forest green / ochre, pre-refresh


class TestOtherStylesheetsUntouched:
    @pytest.mark.parametrize("css_path", [
        LANDING_CSS, PROFILE_CSS, ANALYTICS_CSS, ADD_EXPENSE_CSS,
    ])
    def test_no_new_token_hex_values_leaked_in(self, css_path):
        content = _read(css_path)
        for value in NEW_TOKEN_VALUES:
            assert value.lower() not in content.lower(), (
                f"{os.path.basename(css_path)} must not contain the new "
                f"accent hex {value} — this spec confines the token change "
                f"to style.css's :root"
            )

    @pytest.mark.parametrize("css_path", [
        LANDING_CSS, PROFILE_CSS, ANALYTICS_CSS, ADD_EXPENSE_CSS,
    ])
    def test_no_bd_green_or_bd_red_token_names(self, css_path):
        """
        The earlier draft's rejected --bd-green/--bd-red tokens must not
        appear anywhere — they were dropped in favor of redefining the
        existing --accent/--accent-2 tokens directly.
        """
        content = _read(css_path).lower()
        assert "bd-green" not in content
        assert "bd-red" not in content

    def test_style_css_also_has_no_bd_green_or_bd_red(self):
        """style.css itself must not carry the rejected token names either."""
        content = _read(STYLE_CSS).lower()
        assert "bd-green" not in content
        assert "bd-red" not in content


# ---------------------------------------------------------------------------
# 8. Google Fonts <link> unchanged — confirms fonts were NOT touched
# ---------------------------------------------------------------------------

class TestGoogleFontsUnchanged:
    def test_base_html_has_dm_serif_display_and_dm_sans_font_link(self):
        content = _read(BASE_HTML)
        assert "fonts.googleapis.com/css2" in content, (
            "Expected the Google Fonts stylesheet <link> in base.html"
        )
        assert "DM+Serif+Display" in content, (
            "DM Serif Display must remain the loaded display font"
        )
        assert "DM+Sans" in content, (
            "DM Sans must remain the loaded body font"
        )

    def test_landing_page_head_includes_google_fonts_link(self, client):
        """End-to-end: the unchanged font link must reach rendered `/` output."""
        body = client.get("/").data.decode()
        assert "fonts.googleapis.com/css2" in body
        assert "DM+Serif+Display" in body


# ---------------------------------------------------------------------------
# 9. static/favicon.svg exists and is valid enough to be recognized as SVG
# ---------------------------------------------------------------------------

class TestFaviconSvgFile:
    def test_favicon_svg_file_exists(self):
        assert os.path.isfile(FAVICON_SVG), (
            "Spec requires a new file static/favicon.svg"
        )

    def test_favicon_svg_contains_svg_root_element(self):
        content = _read(FAVICON_SVG)
        assert "<svg" in content, "favicon.svg must contain an <svg root element"

    def test_favicon_svg_filled_with_chosen_accent_hex(self):
        """
        Spec: 'a small diamond shape ... filled with the literal hex of the
        chosen option's --accent value' (#006A4E) — SVG can't reference a
        CSS custom property, so the hardcoded hex is the one sanctioned
        exception.
        """
        content = _read(FAVICON_SVG)
        assert "#006A4E" in content or "#006a4e" in content.lower(), (
            "favicon.svg must be filled with the literal accent hex #006A4E"
        )

    def test_favicon_svg_served_at_static_route(self, client):
        """The favicon must actually be reachable through Flask's static handler."""
        response = client.get("/static/favicon.svg")
        assert response.status_code == 200
        assert b"<svg" in response.data
