"""
CYPHEX Terminal Mascot — SENTRY
════════════════════════════════════════════════════════════════════════════
A tiny animated pixel-art robot companion that lives in the terminal and
redraws itself in place (ANSI cursor-up + line-clear, never scroll-spams)
on a background thread at a modest frame rate. It reacts to CLI state:

    mascot.idle()                        resting / breathing
    mascot.searching(label="...")        loop_scanning pulse + periodic
                                          light-beam flash (scan.png)
    mascot.thinking(label="...")         loop_loading pulse + periodic
                                          "..." head-cameo cutaway
    mascot.success(msg="...")            brightness flash + settle
    mascot.error(msg="...")              alert/error head-cameo strobe

Each of `idle` / `searching` / `thinking` also works as a context manager:

    with mascot.searching("scanning target..."):
        ...do the real work...
    # __exit__ stops the mascot cleanly, or flips to the error strobe first
    # if the block raised.

`searching(..., flourish=True)` / `thinking(..., flourish=True)` — and the
always-flourish `success` / `error` — are one-shot: they block briefly in
the calling thread, play a couple of animation cycles, then erase. This is
the safe way to bracket a call site that immediately hands the terminal to
something else afterwards (a subprocess, a Rich Live panel, etc.) without
leaving a competing redraw thread running underneath it.

REAL PIXEL ART, TIERED RENDERING
--------------------------------------------------------------------------
Frames are built once at import time (see `_build_state_frames` /
`_STATE_FRAMES`) by loading and compositing the real RGBA pixel-art sprites
in assets/mascot/ — no hand-drawn ASCII/box-drawing art is synthesized here
any more. Brightness pulses (PIL ImageEnhance) and bottom-center canvas
compositing (so a same-chassis pose swap never jitters the body) are the
only synthesis performed; everything else is the shipped art, as-is.

At render time, the CURRENT terminal's capability is probed (never
hardcoded) and the best available tier is used:

    Tier 3 — real inline pixel images (Kitty / iTerm2-WezTerm protocols),
             via mascot_backend_image.
    Tier 2 — 24-bit truecolor Unicode half-block art, via
             mascot_backend_halfblock (COLORTERM=truecolor/24bit).
    Tier 1 — 256-color quantized half-block art, same module (TERM has
             '256color').
    Tier 0 — a single plain, uncoloured status line (no escape codes, no
             animation) — the same fallback this module has always used
             for non-tty / NO_COLOR, now ALSO used whenever a real tty has
             no detected color/image support at all.

Colours for the text LABEL beside a frame are NOT reinvented — they are the
exact MONO ELECTRIC BLUE ramp from terminal_ui.py's HUD_THEME (imported
when available; mirrored, same convention as cx.py's plain-ANSI fallback
palette, if terminal_ui can't be imported for some reason).

Non-TTY / NO_COLOR / no-color-support-detected: every public call degrades
to at most one plain, uncoloured status line — no escape codes, no
animation, no cursor games — matching terminal_ui.py's own "no escape spam
on pipes/CI" rule. Every entry point is wrapped so a bug in here can never
crash the host CLI or leave the terminal in a dirty state (hidden cursor,
half-drawn frame). Pillow (and the mascot_backend_*/mascot_companion
modules) are all imported defensively — if any of them are missing or the
asset files fail to load, this module quietly falls back to Tier 0 rather
than raising, so `import mascot` itself can never fail the host CLI.
"""
import atexit
import os
import re
import shutil
import sys
import threading
import time

_ANSI_STRIP = re.compile(r"\033\[[0-9;?]*[A-Za-z]")

try:
    from terminal_ui import PHOS, PHOS_DIM, REF, CAUT, WARN_HOT, APEX, LABEL, _fg as _hex_fg
    _ANSI_RESET = "\033[0m"
except ImportError:
    # Mirror terminal_ui.py's MONO ELECTRIC BLUE ramp verbatim (same values as
    # terminal_ui.py:54-65 / HUD_THEME) so the mascot stays on-brand even when
    # terminal_ui/rich can't be imported. Same convention cx.py already uses
    # for its own plain-ANSI fallback palette — keep these hex values in sync
    # with terminal_ui.py by hand if that ramp ever changes.
    PHOS, PHOS_DIM, REF = "#3b82f6", "#1a4890", "#7dabff"
    CAUT, WARN_HOT, APEX, LABEL = "#2563c6", "#a9c9ff", "#d6e6ff", "#5f7391"

    def _hex_fg(hexcolor):
        r, g, b = (int(hexcolor[i:i + 2], 16) for i in (1, 3, 5))
        return f"\033[38;2;{r};{g};{b}m"

    _ANSI_RESET = "\033[0m"

FPS = 6                        # modest frame rate — every state loops at
DEFAULT_TARGET_COLS = 28       # ~4-6fps per the animation spec.
                                # Default inline render width in terminal
                                # columns for the module-level convenience
                                # functions; a future caller can pass a
                                # larger `size=` (e.g. for hero.png) without
                                # affecting any existing call site's default.


def _c(text, color):
    """Wrap `text` in the exact truecolor escape for one of the imported
    HUD_THEME hex constants (or its mirror above). Never invents a colour."""
    return _hex_fg(color) + text + _ANSI_RESET


# ── Tier-0 plain-glyph fallback (kept exactly as before — already correct
#    and tested) ────────────────────────────────────────────────────────
_STATIC_MARK = {"idle": "·", "searching": "?", "thinking": "…", "success": "✓", "error": "✗"}


# ═══════════════════════════════════════════════════════════════════════
#  Real pixel-art asset loading + frame composition (computed once, at
#  import time — see _build_state_frames / _STATE_FRAMES below).
# ═══════════════════════════════════════════════════════════════════════
_ASSET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "mascot")

try:
    from PIL import Image, ImageEnhance
except Exception:
    Image = None
    ImageEnhance = None

# Rendering backends — all optional/defensive. Any of these failing to
# import just narrows which tiers are reachable; it never breaks `import
# mascot` itself.
try:
    import mascot_backend_image as _img_backend
except Exception:
    _img_backend = None

try:
    import mascot_backend_halfblock as _hb_backend
except Exception:
    _hb_backend = None

try:
    import mascot_companion as _companion
except Exception:
    _companion = None

# Animation-timing constants for the composed frame lists (see
# _build_state_frames). Not user-tunable — this is the "hand-designed"
# timing from the product spec, not a knob.
_BREATH_DIM = 0.9              # idle/loop "breathing" pulse dim factor
_SUCCESS_FLASH = 1.3           # success flourish brief brightness flash
_HOLD_TICKS = 3                # ticks a "beat" frame (scan beam / thinking
                                # cutaway) holds before returning
_BREATH_CYCLES_PER_BEAT = 3    # breathing triplets played between each beat


def _load_asset(name):
    path = os.path.join(_ASSET_DIR, name)
    img = Image.open(path)
    img.load()
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    return img


def _brighten(img, factor):
    """Return a brightness-adjusted copy of img. PIL's ImageEnhance.Brightness
    special-cases the alpha band of an RGBA image (copies it verbatim into
    the black 'degenerate' image it blends against), so this only scales
    RGB — it is a real brightness pulse, not a synthesized opacity fade."""
    return ImageEnhance.Brightness(img).enhance(factor)


def _breathing_triplet(img):
    """The shared 3-frame 'breathing' pulse: 100% -> 90% -> 100% brightness
    on ONE image. No framing change, no jitter — just ImageEnhance."""
    dim = _brighten(img, _BREATH_DIM)
    return [img, dim, img]


def _anchor_bottom_center(img, canvas_size):
    """Composite img onto a new transparent canvas of canvas_size, anchored
    BOTTOM-CENTER (feet stay planted; padding is transparent pixels). Used
    so swapping between two same-chassis poses of different sizes (e.g.
    loop_scanning.png <-> scan.png, the latter wider for its light beam)
    never visually jitters/resizes the body."""
    cw, ch = canvas_size
    w, h = img.size
    canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    x = (cw - w) // 2
    y = ch - h
    canvas.paste(img, (x, y), img)
    return canvas


def _build_state_frames():
    """Build the exact per-state frame lists per the CYPHEX mascot animation
    spec, from the real pixel-art assets in assets/mascot/. Computed once
    (memoized into _STATE_FRAMES below at import time) — compositing a
    handful of small PNGs is cheap once, not worth redoing on every render
    tick. Brightness variants and bottom-center canvas compositing are the
    ONLY synthesis performed; everything else is the shipped art, as-is."""
    idle_img = _load_asset("idle.png")
    loop_scanning_img = _load_asset("loop_scanning.png")
    scan_img = _load_asset("scan.png")
    loop_loading_img = _load_asset("loop_loading.png")
    expr_thinking_img = _load_asset("expr_thinking.png")
    success_img = _load_asset("success.png")
    expr_alert_img = _load_asset("expr_alert.png")
    expr_error_img = _load_asset("expr_error.png")

    # idle: a slow 3-frame "breathing" pulse on ONE image.
    idle_frames = _breathing_triplet(idle_img)

    # searching (the "flash light while searching" state): loop_scanning.png
    # breathes for a few cycles, then scan.png (the literal light-beam
    # pose) is swapped in and held for one beat before returning — THIS is
    # the flash-the-light moment. Both poses are composited onto a SHARED
    # canvas (bottom-center anchored) sized to the wider of the two
    # (scan.png is wider, for the beam) so the swap never jitters the body.
    canvas_size = (
        max(loop_scanning_img.width, scan_img.width),
        max(loop_scanning_img.height, scan_img.height),
    )
    loop_scanning_c = _anchor_bottom_center(loop_scanning_img, canvas_size)
    scan_c = _anchor_bottom_center(scan_img, canvas_size)
    searching_frames = (
        _breathing_triplet(loop_scanning_c) * _BREATH_CYCLES_PER_BEAT
        + [scan_c] * _HOLD_TICKS
    )

    # thinking (the "think while thinking" state): loop_loading.png breathes
    # for a few cycles, then a hard CUT (deliberate framing change — full
    # body -> close-up face, reads like a cutaway shot) to expr_thinking.png
    # (the "..." head cameo), held for one beat, then cuts back. NOT
    # anchored to a shared canvas with loop_loading — the size/framing jump
    # is intentional here, unlike searching.
    thinking_frames = (
        _breathing_triplet(loop_loading_img) * _BREATH_CYCLES_PER_BEAT
        + [expr_thinking_img] * _HOLD_TICKS
    )

    # success: one-shot 2-frame flourish — a brief brightness flash (~130%)
    # settling to 100%. Mascot.success() plays this at cycles=2 via
    # _flourish, matching the existing "blocking one-shot" semantics.
    success_frames = [_brighten(success_img, _SUCCESS_FLASH), success_img]

    # error: one-shot fast strobe between the two real head-cameo assets —
    # no synthesis needed, both are shipped art as-is.
    error_frames = [expr_alert_img, expr_error_img]

    return {
        "idle": idle_frames,
        "searching": searching_frames,
        "thinking": thinking_frames,
        "success": success_frames,
        "error": error_frames,
    }


try:
    _STATE_FRAMES = _build_state_frames() if Image is not None else {}
except Exception:
    _STATE_FRAMES = {}

_PIXEL_ART_AVAILABLE = bool(_STATE_FRAMES)

# hero.png (larger/cleaner idle-pose render) — lazy-loaded ONLY if a caller
# actually asks for it via render_hero() below, so it never adds startup
# cost for the 11 existing call sites, none of which use it. Optional, per
# spec: "use for any big/banner-style display ... if there's a natural
# place for it" — not wired into any state or call site.
_HERO_IMG = None


def _get_hero_image():
    global _HERO_IMG
    if _HERO_IMG is None and Image is not None:
        try:
            _HERO_IMG = _load_asset("hero.png")
        except Exception:
            _HERO_IMG = False  # sentinel: tried and failed, don't retry
    return _HERO_IMG or None


# ═══════════════════════════════════════════════════════════════════════
#  Capability-tier dispatch — best tier the CURRENT terminal actually
#  supports, probed fresh (never hardcoded/cached at import).
# ═══════════════════════════════════════════════════════════════════════
def _select_tier():
    """Best-to-worst capability probe:
        3 — mascot_backend_image, if kitty_available() or iterm_available()
        2 — mascot_backend_halfblock truecolor, if COLORTERM is truecolor/24bit
        1 — mascot_backend_halfblock 256-color, if TERM contains '256color'
        0 — plain static glyph (no color/image support detected, or the
            pixel-art assets/backends themselves are unavailable)
    Re-run at the start of each render session, matching _enabled()'s own
    re-check-every-call convention (not cached at import)."""
    if not _PIXEL_ART_AVAILABLE:
        return 0
    if _img_backend is not None:
        try:
            if _img_backend.kitty_available() or _img_backend.iterm_available():
                return 3
        except Exception:
            pass
    if _hb_backend is not None:
        try:
            if os.environ.get("COLORTERM") in ("truecolor", "24bit"):
                return 2
            if "256color" in os.environ.get("TERM", ""):
                return 1
        except Exception:
            pass
    return 0


def _render_pixel_frame(tier, img, target_cols):
    """Render one composed PIL frame at the given capability tier. Returns
    (payload_str, rows, kind) where kind is 'kitty' | 'iterm' | 'text', or
    (None, 0, None) if rendering failed for any reason — the caller treats
    that as a dropped tick (skip this redraw), never a crash."""
    try:
        if tier == 3 and _img_backend is not None:
            if _img_backend.kitty_available():
                payload = _img_backend.kitty_render_frame(img, target_cols)
                rows = _img_backend.compute_rows(img, target_cols)
                return payload.decode("ascii", "replace"), rows, "kitty"
            if _img_backend.iterm_available():
                payload = _img_backend.iterm_render_frame(img, target_cols)
                rows = _img_backend.compute_rows(img, target_cols)
                return payload.decode("ascii", "replace"), rows, "iterm"
        elif tier in (1, 2) and _hb_backend is not None:
            text = _hb_backend.render_frame(img, target_cols, truecolor=(tier == 2))
            rows = _hb_backend.row_count(target_cols, img)
            return text, rows, "text"
    except Exception:
        pass
    return None, 0, None


def _kitty_delete_sequence():
    """The APC command that deletes/frees the mascot's image from a Kitty
    terminal's image table. Issued once on _erase() (in addition to the
    normal cursor-up+line-clear dance) because Kitty image placements are
    an overlay independent of the text grid — clearing text alone does not
    reliably remove them."""
    if _img_backend is None:
        return ""
    try:
        cmd = (
            _img_backend.KITTY_APC_START
            + f"a=d,d=I,i={_img_backend.DEFAULT_KITTY_IMAGE_ID}".encode("ascii")
            + _img_backend.KITTY_APC_END
        )
        return cmd.decode("ascii", "replace")
    except Exception:
        return ""


class _MascotSession:
    """Context-manager returned by idle()/searching()/thinking(). On a clean
    exit it stops the mascot; on an exception it flips to the error strobe
    first (so a failure is visually distinct) and never swallows the error."""
    __slots__ = ("_m",)

    def __init__(self, mascot):
        self._m = mascot

    def __enter__(self):
        return self._m

    def __exit__(self, exc_type, exc, tb):
        if exc_type is not None:
            try:
                self._m.error(str(exc) if exc else exc_type.__name__)
            except Exception:
                pass
        else:
            self._m.stop()
        return False


class _NoopSession:
    """Returned instead of _MascotSession if something inside the mascot
    itself misbehaves — `with mascot.searching(...):` must never break the
    caller just because the eye-candy did."""
    __slots__ = ()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


_NOOP = _NoopSession()


class Mascot:
    """One animated companion, redrawn in place on a background thread.
    Safe to start/stop repeatedly; always leaves the cursor visible and the
    terminal free of half-drawn frames on exit, including on exceptions."""

    def __init__(self, stream=None, fps=FPS, target_cols=DEFAULT_TARGET_COLS):
        self._stream = stream or sys.stdout
        self._interval = 1.0 / max(1, int(fps))
        self._lock = threading.Lock()
        self._thread = None
        self._stop_evt = threading.Event()
        self._state = "idle"
        self._label = ""
        self._target_cols = target_cols
        self._active_tier = 0
        self._active_kind = None
        self._lines_drawn = 0
        self._cursor_hidden = False
        atexit.register(self._atexit_cleanup)

    # ── availability ─────────────────────────────────────────────────────
    def _enabled(self):
        """Re-checked on every call (not cached) — matches terminal_ui.py's
        own _tty()/_cols(), which re-query fresh each render rather than
        trusting a value captured at import time (e.g. under pytest capsys,
        or if NO_COLOR is set/unset mid-run)."""
        try:
            if not self._stream.isatty():
                return False
        except Exception:
            return False
        if os.environ.get("NO_COLOR"):
            return False
        return True

    def _effective_tier(self):
        """0 whenever _enabled() is False (non-tty/NO_COLOR — the existing
        short-circuit, unchanged) OR whenever a real tty has no detected
        color/image support at all (a genuinely new case this tiered
        rendering introduces); otherwise the best tier _select_tier() finds."""
        if not self._enabled():
            return 0
        return _select_tier()

    # ── low-level draw / erase ──────────────────────────────────────────
    def _write(self, s):
        try:
            self._stream.write(s)
            self._stream.flush()
        except Exception:
            pass

    def _label_suffix(self, label):
        """Colour-wrapped label text for the line printed under a frame.
        Truncated to the terminal width (minus a small left margin) so a
        long label never wraps and breaks the redraw-in-place row count."""
        if not label:
            return ""
        # Some call sites (e.g. cx.py's plain-ANSI fallback messages) pass a
        # string that already carries its own colour codes — strip them so
        # they can't break out of the LABEL colour wrap below or throw off
        # the width math against a raw escape-code byte count.
        text = _ANSI_STRIP.sub("", label)
        if not text:
            return ""
        try:
            cols = shutil.get_terminal_size(fallback=(80, 24)).columns
        except Exception:
            cols = 80
        avail = max(cols - 4, 0)
        if len(text) > avail:
            text = text[: max(avail - 1, 0)].rstrip() + "…"
        return ("  " + _c(text, LABEL)) if text else ""

    def _draw_pixel(self, payload, rows, label, kind):
        """Draw one already-rendered frame (from _render_pixel_frame):
        cursor-up to the previous frame's top (or hide the cursor, first
        call), print the frame payload, then an optional label line below
        it. Tier-agnostic — `kind` only affects whether a trailing newline
        is needed to land the cursor at column 0 of the row after the
        frame (image protocols do this themselves by default; half-block
        text output does not, per that module's own docstring)."""
        parts = []
        if self._lines_drawn:
            parts.append(f"\033[{self._lines_drawn}A\r")
        else:
            parts.append("\033[?25l")  # hide cursor for a flicker-free redraw
            self._cursor_hidden = True
        parts.append(payload)
        if kind == "text":
            parts.append("\n")
        total_rows = rows
        suffix = self._label_suffix(label)
        if suffix:
            parts.append(suffix)
            parts.append("\033[K\n")
            total_rows += 1
        self._write("".join(parts))
        self._lines_drawn = total_rows
        self._active_kind = kind

    def _erase(self):
        if self._lines_drawn:
            n = self._lines_drawn
            out = f"\033[{n}A\r" + ("\033[K\n" * n) + f"\033[{n}A"
            if self._active_kind == "kitty":
                out = _kitty_delete_sequence() + out
            self._write(out)
            self._lines_drawn = 0
        if self._cursor_hidden:
            self._write("\033[?25h")  # restore cursor only if we ever hid it
            self._cursor_hidden = False
        self._active_kind = None

    def _print_static(self, state, label):
        mark = _STATIC_MARK.get(state, "·")
        label = _ANSI_STRIP.sub("", label) if label else label
        msg = f"  {mark} {label}".rstrip() if label else f"  {mark}"
        try:
            print(msg, file=self._stream)
        except Exception:
            pass

    # ── lifecycle ────────────────────────────────────────────────────────
    def start(self):
        """Idempotent — a no-op if already running (or if disabled / no
        capable tier detected)."""
        tier = self._effective_tier()
        if tier == 0:
            return self
        try:
            with self._lock:
                if self._thread is not None and self._thread.is_alive():
                    return self
                self._active_tier = tier
                self._stop_evt.clear()
                self._lines_drawn = 0
                self._thread = threading.Thread(
                    target=self._render_loop, name="cyphex-mascot", daemon=True
                )
                self._thread.start()
        except Exception:
            pass
        return self

    def stop(self):
        """Idempotent — safe to call even if never started. Always leaves
        the cursor visible and erases any lines the mascot drew."""
        t = None
        try:
            with self._lock:
                t = self._thread
                self._thread = None
            if t is not None and t.is_alive():
                self._stop_evt.set()
                t.join(timeout=1.0)
        except Exception:
            pass
        finally:
            self._erase()

    def _atexit_cleanup(self):
        try:
            self.stop()
        except Exception:
            pass

    def _render_loop(self):
        i = 0
        tier = self._active_tier
        try:
            while not self._stop_evt.is_set():
                with self._lock:
                    state, label, target_cols = self._state, self._label, self._target_cols
                frames = _STATE_FRAMES.get(state) or _STATE_FRAMES.get("idle") or []
                if not frames:
                    return
                idx = i % len(frames)
                payload, rows, kind = _render_pixel_frame(tier, frames[idx], target_cols)
                if payload is not None:
                    self._draw_pixel(payload, rows, label, kind)
                i += 1
                self._stop_evt.wait(self._interval)
        except Exception:
            pass

    def _flourish(self, state, label, cycles, size):
        """Blocking one-shot: stop any running session, play `cycles` loops
        of `state`'s frames in the CALLING thread, then erase. Guaranteed
        to be fully done (cursor restored) before it returns — the safe way
        to cue a beat right before something else (a subprocess, a Rich
        Live panel) takes over the terminal."""
        tier = self._effective_tier()
        if tier == 0:
            self._print_static(state, label)
            return self
        self.stop()  # never race a leftover background session
        try:
            frames = _STATE_FRAMES.get(state) or []
            for i in range(len(frames) * max(1, cycles)):
                payload, rows, kind = _render_pixel_frame(tier, frames[i % len(frames)], size)
                if payload is None:
                    continue
                self._draw_pixel(payload, rows, label, kind)
                time.sleep(self._interval)
        except Exception:
            pass
        finally:
            self._erase()
        return self

    def _enter(self, state, label, size):
        tier = self._effective_tier()
        if tier == 0:
            self._print_static(state, label)
            return _NOOP
        try:
            with self._lock:
                self._state, self._label, self._target_cols = state, label, size
            self.start()
            return _MascotSession(self)
        except Exception:
            return _NOOP

    # ── public state transitions ────────────────────────────────────────
    def idle(self, *, size=DEFAULT_TARGET_COLS):
        """Resting / breathing. Usable as `with mascot.idle():`."""
        return self._enter("idle", "", size)

    def searching(self, label="", *, flourish=False, size=DEFAULT_TARGET_COLS):
        """loop_scanning.png breathing pulse + periodic scan.png light-beam
        flash — "actively hunting". Usable as
        `with mascot.searching("scanning target..."):`, or pass
        flourish=True for a brief one-shot beat instead of a held state."""
        if flourish:
            return self._flourish("searching", label, 1, size)
        return self._enter("searching", label, size)

    def thinking(self, label="", *, flourish=False, size=DEFAULT_TARGET_COLS):
        """loop_loading.png breathing pulse + periodic "..." head-cameo
        cutaway — "processing". Same two forms as searching()."""
        if flourish:
            return self._flourish("thinking", label, 1, size)
        return self._enter("thinking", label, size)

    def success(self, msg="", *, size=DEFAULT_TARGET_COLS):
        """One-shot brightness flash + settle, then erases. Always
        blocking/brief — never leaves a session running."""
        return self._flourish("success", msg, 2, size)

    def error(self, msg="", *, size=DEFAULT_TARGET_COLS):
        """One-shot alert/error head-cameo strobe, then erases. Always
        blocking/brief."""
        return self._flourish("error", msg, 3, size)


# Module-level singleton + thin function wrappers, so callers just do
# `import mascot` and `mascot.searching("...")` / `with mascot.thinking(...):`
# — mirroring terminal_ui.py's module-level `soc` Console / `render_*` style.
_singleton = Mascot()


def idle(*, size=DEFAULT_TARGET_COLS):
    return _singleton.idle(size=size)


def searching(label="", *, flourish=False, size=DEFAULT_TARGET_COLS):
    return _singleton.searching(label, flourish=flourish, size=size)


def thinking(label="", *, flourish=False, size=DEFAULT_TARGET_COLS):
    return _singleton.thinking(label, flourish=flourish, size=size)


def success(msg="", *, size=DEFAULT_TARGET_COLS):
    return _singleton.success(msg, size=size)


def error(msg="", *, size=DEFAULT_TARGET_COLS):
    return _singleton.error(msg, size=size)


def stop():
    return _singleton.stop()


def open_companion_window(**kwargs):
    """Thin passthrough to mascot_companion.open_companion_window() — spawns
    a SEPARATE dedicated terminal window to host the mascot, for terminals
    that can't render it well integrated. EXPLICIT-CALL-ONLY: nothing in
    this module (or any of the 11 existing CLI call sites) invokes this
    automatically — it exists purely as an opt-in entry point for a future
    caller (e.g. a CLI flag) that has already decided the integrated render
    isn't an option. See mascot_companion.py's own module docstring for the
    full contract. Never raises; returns False if unavailable/failed."""
    if _companion is None:
        return False
    try:
        return _companion.open_companion_window(**kwargs)
    except Exception:
        return False


def render_hero(size=64):
    """Render hero.png (the larger/cleaner idle-pose banner art) at the
    current best-supported capability tier, for a caller with a natural
    big/banner-style spot (e.g. a CLI startup splash) to print directly.
    Optional — not used by any existing call site; hero.png is only loaded
    from disk the first time this is actually called. Returns the payload
    string to print, or "" if unavailable (no pixel art / no capability /
    non-tty / hero.png missing) — never raises."""
    try:
        tier = _singleton._effective_tier()
        if tier == 0:
            return ""
        img = _get_hero_image()
        if img is None:
            return ""
        payload, _rows, _kind = _render_pixel_frame(tier, img, size)
        return payload or ""
    except Exception:
        return ""


def render_and_print_state_loop(state_file_path, poll_interval=0.3):
    """Standalone render loop for the companion-window process
    (mascot_companion_loop.py, launched by mascot_companion.open_companion_
    window()): polls `state_file_path` for a single-word state name and
    redraws the matching real-pixel-art animation in place, using the exact
    same tiered rendering this module's own background thread uses — so the
    companion window shows the same animation the integrated terminal
    would. Runs until interrupted (KeyboardInterrupt/SystemExit); the
    caller is responsible for hiding/showing the cursor around this call,
    matching every other entry point's cursor-safety convention (this
    function also guarantees its own frame lines are erased and its own
    cursor-hide is undone in its `finally`, so it's safe either way)."""
    m = Mascot()
    tick = 0
    try:
        while True:
            try:
                with open(state_file_path, "r") as f:
                    state = f.readline().strip() or "idle"
            except Exception:
                state = "idle"
            if state not in _STATE_FRAMES:
                state = "idle"

            tier = m._effective_tier()
            if tier == 0:
                m._print_static(state, "")
            else:
                frames = _STATE_FRAMES.get(state) or []
                if frames:
                    idx = tick % len(frames)
                    payload, rows, kind = _render_pixel_frame(tier, frames[idx], m._target_cols)
                    if payload is not None:
                        m._draw_pixel(payload, rows, "", kind)

            tick += 1
            time.sleep(poll_interval)
    except (KeyboardInterrupt, SystemExit):
        pass
    except Exception:
        pass
    finally:
        try:
            m._erase()
        except Exception:
            pass


if __name__ == "__main__":
    # Manual smoke test: python3 mascot.py
    print("CYPHEX mascot — standalone demo (Ctrl+C to skip a beat)\n")
    with searching("scanning target..."):
        time.sleep(2.5)
    success("scan complete — 0 critical findings")
    time.sleep(0.4)
    with thinking("asking the model..."):
        time.sleep(2.5)
    error("model timed out")
    time.sleep(0.4)
    print("\ndone.")
