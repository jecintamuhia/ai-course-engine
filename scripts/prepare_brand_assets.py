"""Regenerate the SkillUp Action Africa brand assets from the official site.

The organisation's logo is published on the public website as an inline
PNG data-URI (the same file is used for the favicon, the navbar and the
footer). This script downloads that canonical file and derives the three
assets the platform needs:

    backend/frontend/public/brand/skillup-action-africa-logo.png
        full horizontal lockup (symbol + wordmark), transparent, trimmed
    backend/frontend/public/brand/skillup-action-africa-logo-sm.png
        downscaled lockup for navigation, footer and Moodle placements
    backend/frontend/public/brand/skillup-action-africa-mark.png
        symbol only, transparent, trimmed
    backend/frontend/public/favicon.png
        square favicon canvas with the symbol centred (aspect preserved)
    moodle-theme/skillup-auth/skillup-auth-hero.html
        Moodle login-page brand panel with the logo inlined as a data URI
    moodle-theme/skillup-auth/skillup-auth-head.html
        paste-ready Moodle "Additional HTML" head block (fonts + CSS + JS)

Everything is derived mechanically from the official artwork. The logo is
never redrawn, recoloured or approximated: colours are sampled from the
source pixels and the alpha channel is preserved as-is.

Usage (from the repo root, with the project virtualenv):

    python scripts/prepare_brand_assets.py

Set SKILLUP_SITE_URL to point at a staging copy of the site.
"""

from __future__ import annotations

import base64
import io
import re
import sys
import urllib.request
from pathlib import Path

from PIL import Image

SITE_URL = "https://skillupafrica.co.ke/"
REPO_ROOT = Path(__file__).resolve().parent.parent
BRAND_DIR = REPO_ROOT / "backend" / "frontend" / "public" / "brand"
PUBLIC_DIR = REPO_ROOT / "backend" / "frontend" / "public"
MOODLE_THEME_DIR = REPO_ROOT / "moodle-theme" / "skillup-auth"

#: Alpha value above which a pixel counts as part of the artwork.
INK_ALPHA = 16

#: Width of the compact lockup used for navigation and footer placements.
SMALL_LOGO_WIDTH = 480

#: Edge length of the square favicon canvas.
FAVICON_SIZE = 192


def fetch_logo_bytes() -> bytes:
    """Download the official logo PNG embedded in the organisation website."""
    request = urllib.request.Request(
        SITE_URL, headers={"User-Agent": "Mozilla/5.0 (brand asset fetcher)"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        html = response.read().decode("utf-8", "replace")

    match = re.search(r"data:image/png;base64,([A-Za-z0-9+/=]+)", html)
    if match is None:
        raise SystemExit(
            f"No inline PNG logo found on {SITE_URL}. The site layout may have "
            "changed; fetch the logo manually and place it in "
            f"{BRAND_DIR}."
        )
    return base64.b64decode(match.group(1))


def content_bbox(image: Image.Image) -> tuple[int, int, int, int]:
    """Return the (left, top, right, bottom) bbox of the visible artwork."""
    alpha = image.getchannel("A")
    bbox = alpha.point(lambda value: 255 if value > INK_ALPHA else 0).getbbox()
    if bbox is None:
        raise SystemExit("The downloaded logo is completely transparent.")
    return bbox


def save_mark(image: Image.Image) -> Path:
    """Save the symbol (the artwork left of the wordmark) as its own asset."""
    width, height = image.size
    alpha = image.getchannel("A")

    # The symbol occupies the leftmost cluster of artwork; the wordmark is
    # separated by a clear vertical gutter. Find that gutter instead of
    # hard-coding a pixel column so the split survives a re-export.
    occupied = {
        x for x in range(width) if alpha.crop((x, 0, x + 1, height)).getbbox()
    }
    gaps: list[tuple[int, int]] = []
    run_start: int | None = None
    for x in range(width):
        if x not in occupied:
            if run_start is None:
                run_start = x
        elif run_start is not None:
            gaps.append((run_start, x - 1))
            run_start = None
    if run_start is not None:
        gaps.append((run_start, width - 1))

    # The widest interior gutter separates the symbol from the wordmark.
    interior = [gap for gap in gaps if gap[0] > 0 and gap[1] < width - 1]
    split = (
        max(interior, key=lambda gap: gap[1] - gap[0])[1] + 1
        if interior
        else width
    )

    mark = image.crop((0, 0, split, height))
    mark = mark.crop(content_bbox(mark))

    target = BRAND_DIR / "skillup-action-africa-mark.png"
    _optimise(mark, target)
    return target


def _optimise(image: Image.Image, path: Path) -> None:
    """Write a PNG with maximum lossless compression.

    The official artwork contains thousands of distinct colours (real
    gradients and antialiased edges), so palette quantisation measurably
    degrades it and is deliberately not used. The file is stored lossless
    at the highest zlib level instead.
    """
    image.save(path, format="PNG", optimize=True, compress_level=9)


def save_logo(image: Image.Image) -> Path:
    """Save the full horizontal lockup, trimmed to the visible artwork."""
    trimmed = image.crop(content_bbox(image))
    target = BRAND_DIR / "skillup-action-africa-logo.png"
    _optimise(trimmed, target)
    return target


def save_logo_small(image: Image.Image) -> Path:
    """Save a downscaled lockup for compact UI placements.

    The canonical logo is served at the official resolution so nothing is
    resampled away from the source artwork. Navigation, footers and other
    compact placements use this variant, which is still larger than twice
    the size it is displayed at.
    """
    target = BRAND_DIR / "skillup-action-africa-logo-sm.png"
    _optimise(image.copy(), target)
    return target


def save_favicon(mark: Image.Image) -> Path:
    """Save a square favicon with the symbol centred and aspect preserved."""
    size = FAVICON_SIZE
    padding = int(size * 0.06)
    inner = size - padding * 2
    scale = min(inner / mark.width, inner / mark.height)
    resized = mark.resize(
        (max(1, round(mark.width * scale)), max(1, round(mark.height * scale))),
        Image.LANCZOS,
    )
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.paste(
        resized,
        ((size - resized.width) // 2, (size - resized.height) // 2),
        resized,
    )
    target = PUBLIC_DIR / "favicon.png"
    _optimise(canvas, target)
    return target


def write_moodle_hero(logo_path: Path) -> Path:
    """Write the Moodle authentication hero panel with the official logo.

    Moodle's "Additional HTML" cannot reference files on disk, so the logo
    is inlined as a data URI. This is the same technique the organisation's
    own website uses for its logo, so the login page shows the real
    artwork rather than a description of it.
    """
    encoded = base64.b64encode(logo_path.read_bytes()).decode("ascii")
    markup = f"""<!-- Skillup Action Africa - auth brand panel.
     Injected site-wide via Moodle "Additional HTML" (top of body) and shown
     only on body.pagelayout-login by skillup-auth.css. Decorative panel only:
     the native Moodle login/signup form is untouched.

     The logo below is the official artwork from skillupafrica.co.ke, inlined
     as a data URI because Moodle Additional HTML cannot load local files.
     Regenerate with: python scripts/prepare_brand_assets.py -->
<aside class="skillup-auth-hero" aria-label="About Skillup Action Africa">
  <div class="skillup-auth-hero__inner">
    <img
      class="skillup-auth-hero__logo"
      src="data:image/png;base64,{encoded}"
      alt="Skillup Action Africa"
      width="480"
      height="191"
    />
    <p class="skillup-auth-hero__brand">
      <span class="skillup-auth-hero__rule" aria-hidden="true"></span>
      Skillup Action Africa
    </p>
    <h2 class="skillup-auth-hero__title">Your next chapter starts here.</h2>
    <p class="skillup-auth-hero__lede">
      Join a growing community of learners building practical skills for a
      changing world.
    </p>
    <ul class="skillup-auth-hero__list">
      <li>Learn practical, career-relevant skills.</li>
      <li>Explore structured learning resources.</li>
      <li>Grow at your own pace.</li>
    </ul>
    <p class="skillup-auth-hero__note">Practical skills for a changing world.</p>
  </div>
</aside>
"""
    target = MOODLE_THEME_DIR / "skillup-auth-hero.html"
    target.write_bytes(markup.encode("utf-8"))
    return target


def write_moodle_head() -> Path:
    """Write the single paste-ready snippet for Moodle's "Additional HTML".

    Moodle's Additional HTML (head section) cannot reference local files, so
    the stylesheet and script are inlined here alongside the brand font
    links. Generating it from the source files keeps the two in sync.
    """
    css = (MOODLE_THEME_DIR / "skillup-auth.css").read_text(encoding="utf-8")
    js = (MOODLE_THEME_DIR / "skillup-auth.js").read_text(encoding="utf-8")
    markup = f"""<!-- Skillup Action Africa - Moodle auth styling.
     Paste this whole block into
     Site administration > Site admin > Appearance > Additional HTML
     (HEAD section). Then paste skillup-auth-hero.html into the same page's
     BODY section. Regenerate with: python scripts/prepare_brand_assets.py -->
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link
  href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800&family=Playfair+Display:wght@700;800&display=swap"
  rel="stylesheet"
/>
<style>
{css}</style>
<script>
{js}</script>
"""
    target = MOODLE_THEME_DIR / "skillup-auth-head.html"
    target.write_bytes(markup.encode("utf-8"))
    return target


def main() -> int:
    BRAND_DIR.mkdir(parents=True, exist_ok=True)
    MOODLE_THEME_DIR.mkdir(parents=True, exist_ok=True)

    raw = fetch_logo_bytes()
    source = Image.open(io.BytesIO(raw)).convert("RGBA")
    print(f"Downloaded official logo: {source.width}x{source.height}")

    logo_path = save_logo(source)
    mark_path = save_mark(source)
    favicon_path = save_favicon(Image.open(mark_path).convert("RGBA"))

    small = Image.open(logo_path).convert("RGBA")
    small = small.resize(
        (SMALL_LOGO_WIDTH, round(SMALL_LOGO_WIDTH * small.height / small.width)),
        Image.LANCZOS,
    )
    small_path = save_logo_small(small)

    hero_path = write_moodle_hero(small_path)
    head_path = write_moodle_head()

    for path in (logo_path, small_path, mark_path, favicon_path, hero_path, head_path):
        print(f"Wrote {path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
