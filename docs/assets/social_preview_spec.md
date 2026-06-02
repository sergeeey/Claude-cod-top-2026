# GitHub Social Preview Image — Spec

**Target:** `assets/social-preview.png` (1280×640px, sRGB, < 1 MB)
**Used by:** GitHub Settings → Social preview · Twitter/X / LinkedIn / Slack link unfurl cards

## Why this matters

When someone shares `https://github.com/sergeeey/Claude-cod-top-2026` on X / LinkedIn / Slack, the
preview card uses this image. Without one set, GitHub shows a generic placeholder. Pages with a
custom social preview have **~2× CTR** on shared links (GitHub blog data).

## Visual spec

```
┌────────────────────────────────────────────────────────────────────┐
│                                                                    │
│   Dark background (#0d1117 — GitHub dark mode default)             │
│                                                                    │
│   ╔═══════════════════════════════════════════════════════════╗    │
│   ║                                                           ║    │
│   ║   Claude Code Config — Top 2026                           ║    │
│   ║   ────────────────────────────────                        ║    │
│   ║   The only config that catches Validation Theater         ║    │
│   ║   automatically.                                          ║    │
│   ║                                                           ║    │
│   ║   ✓ 59 hooks · 25 events                                  ║    │
│   ║   ✓ 1321 tests · 75% coverage · MIT                       ║    │
│   ║   ✓ Evidence Policy enforced as hard rule                 ║    │
│   ║                                                           ║    │
│   ╚═══════════════════════════════════════════════════════════╝    │
│                                                                    │
│                                            github.com/sergeeey/... │
└────────────────────────────────────────────────────────────────────┘
   1280 × 640 px · 16:8 aspect · safe area: inner 1140×570
```

## Typography

- Title: **Inter Bold 64pt**, color `#e6edf3`
- Subtitle: **Inter Regular 36pt**, color `#7d8590`
- Proof bullets: **JetBrains Mono 28pt**, color `#00ff9f` (checkmarks), `#e6edf3` (text)
- URL footer: **Inter Regular 22pt**, color `#7d8590`

## Colors

- Background: `#0d1117` (GitHub dark)
- Accent green: `#00ff9f` (matches existing test/coverage badges)
- Accent pink: `#ff2d78` (matches existing agents badge — reserve for a small decoration)
- Text primary: `#e6edf3`
- Text secondary: `#7d8590`

## Where the source lives

- Existing banner: `assets/banner.svg` — can be cropped/recomposed for social preview
- Existing pipeline diagram: `assets/pipeline.svg` — too detailed for 1280×640, skip

## Generation steps

**Option A — manual (recommended for quality):**
1. Open Figma / Sketch / Affinity with 1280×640 frame
2. Apply the spec above
3. Export as PNG at 1× (1280×640) and 2× (2560×1280) — GitHub will use 1×
4. Save to `assets/social-preview.png`

**Option B — automated (SVG → PNG):**
```bash
# Requires Inkscape installed
inkscape assets/banner.svg --export-type=png --export-width=1280 --export-height=640 \
         --export-filename=assets/social-preview.png
```

This may need post-processing in an image editor to fit the spec above.

## Upload to GitHub

1. Go to https://github.com/sergeeey/Claude-cod-top-2026/settings
2. Scroll to "Social preview"
3. Click "Upload an image"
4. Select `assets/social-preview.png`
5. Save

Note: this is a one-time manual step. GitHub does NOT auto-detect images from the repo.

## Validation after upload

- Share the repo URL on X — preview should show the card
- Test via Twitter Card Validator: https://cards-dev.twitter.com/validator
- Test via LinkedIn Post Inspector: https://www.linkedin.com/post-inspector/

## Decision log

- **Why dark theme?** Matches GitHub's default. Most viewers will see it in dark mode.
- **Why not light theme too?** Single asset preferred for consistency. Dark works on both backgrounds.
- **Why list metrics in the image?** Skim-readable. Reader sees evidence count without clicking.
- **Why include URL footer?** Helps shares from screenshot tools where the URL isn't auto-attached.
