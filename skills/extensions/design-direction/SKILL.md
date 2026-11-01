---
name: design-direction
description: Route visual work (landing pages, screens, UI mockups, posters, social visuals, ads, pitch decks, printed reports, brand kits) to the right Claude Design surface and pick the visual direction FROM THE TASK — restrained, bold/unusual, or hyperrealistic — instead of defaulting to a generic HTML page. Covers the Design / Design System / Slides artifact types, the standalone claude.ai/design product, an honest account of what "hyperrealistic" can and cannot mean here, and a short quality bar. Use before producing any visual deliverable.
Triggers: /design-direction, claude design, сделай дизайн, дизайн лендинга, дизайн постера, макет интерфейса, UI mockup, landing page design, design a landing page, design a poster, дизайн-система, design system, гиперреалистичный, hyperrealistic, необычный дизайн, визуальный стиль, питч-дек.
argument-hint: [what to design]
---

# Design Direction

Visual work has two decisions that are easy to skip: **which surface** produces it, and **which
look** fits the job. Skipping both yields the same generic page every time. This skill makes both
decisions explicit, in that order. The artifact types ship their own detailed authoring instructions;
this skill does not restate them (a second copy would drift) — it only records the routing consequences.
Where the type's instructions and this skill disagree, the type wins. Sources and their evidence level are
listed at the end; Step 3's direction table is design judgment, not documented fact.

## Not for
- Charts of data → the built-in `dataviz` skill when available, else a plain inline SVG chart with honest axes.
- Scientific figures for a paper → `figure-generation`. Architecture diagrams → `diagram-generator`.
- Paper → Beamer slides or an academic poster → `slide-generation`.
- Memos and briefs with no visual layer → the Docs artifact type, else a plain document.
- Open-ended alternatives for a technical or architectural solution → `brainstorming`.

## Step 1 — Route the deliverable

| Deliverable | Surface | Why |
|---|---|---|
| Landing page, screen, UI mockup, poster, social visual, ad, invite — static layout, tweakable | Artifact type **Design** (canvas of artboards) | Live artboards, comments, tweak properties, export |
| Multi-page designed document for print or PDF (impact report, brochure) | **Design** with print-mode artboards (the type carries print/paper options) | Charts: follow the `dataviz` guidance above, embed as static SVG [INFERRED] |
| Deck to present | Artifact type **Slides** | 16:9, downloadable |
| Brand kit, style guide, "a look reused by several deliverables" | Artifact type **Design System**, created once | Later Design and Slides artifacts pick up the user's default automatically |
| Interactive prototype, WebGL / shader / 3D, heavy motion, data-driven page | Plain HTML artifact (built-in `artifact-design` skill first, if available; else Step 4) | The Design canvas format bars script-built UI and network beyond Google Fonts and uploads [DOCS: the type's format rules]; hence plain HTML here [INFERRED] |
| Long iterative visual work: comment on elements, drag-edit, export to PDF/PPTX/HTML/Canva, handoff bundle to Claude Code | Standalone `claude.ai/design` (run by the user) | Research preview / beta on Pro, Max, Team, Enterprise; Enterprise is off by default |

**Tie-break.** A deliverable that fits two rows goes to the row of its *hardest* requirement (interactivity,
3D, WebGL → plain HTML; print or many pages → Design; a talk to an audience → Slides). A mixed case splits:
an investor deck with an interactive ore-body model is a Slides deck plus a separate plain-HTML model linked
from one slide; a printed report with interactive charts is a Design document plus a plain-HTML companion.
Name the choice and the runner-up in one line. A deliverable that fits no row defaults to a plain HTML
artifact; say so rather than ask something nobody can answer.

**No Artifact tool in this runtime?** Produce a self-contained HTML file — everything inline, no CDN — and
state which Claude Design surfaces were unavailable.

Before building on an artifact surface:
1. Call `Artifact` with `action: "quickstart"` (`intent: "design"` or `"slides"`) — the tool's own contract.
2. List Design Systems (`action: "list"`, `type: "Design System"`). One marked default → use it without
   asking, unless the user asked for a different look for this task (Step 3, precedence 1). Some but no default → name them and ask. None → choose your own look.
3. The create call returns that type's instructions; follow them for the artifact's content.

Creating a Design System: an explicit request for a brand kit, style guide or design system *is* the
permission. Without such a request, offer once when the list is empty and this is the first visual
deliverable of a brand or project; do not create one unasked.

## Step 2 — Brief in five lines, before any pixel

Audience · What the viewer must do or believe within five seconds · Constraints (format, language, brand,
accessibility, print) · Tone · Evidence (which real content, numbers and images actually exist).

- Missing facts become visible placeholders such as `[YOUR PRICE]` — never invented metrics, testimonials,
  logos or lorem ipsum. A page for an external audience with a made-up number is a defect, not a draft.
- Decide and build. State assumptions in one line; ask only what nobody present can answer.

## Step 3 — Choose the direction from the task

| Task | Direction | Levers | Avoid |
|---|---|---|---|
| Investor pitch, official briefing, report to an authority | **Restrained editorial** | Ivory or dark ground, one accent, large numerals with source captions, generous whitespace | Decoration; any number without a traceable source |
| Scientific or lab page, data story | **Editorial, data-forward** | Annotated charts, monospaced values, consistent units | Ornament that competes with the data |
| Product or launch landing page | **Bold and unusual** | One memorable device: oversized type, asymmetric grid, a surprising crop, scroll-driven reveal (plain HTML only); the rest calm | Five devices at once |
| Poster, campaign hero, cover-like visual | **Hyperrealistic or cinematic** | See below | Presenting a render as documentary evidence |
| Internal tool, dashboard | **Utilitarian** | Density, neutral palette, explicit states | Marketing flourish |
| Invite, social post, playful piece | **Expressive** | Colour blocks, collage, textures | Low-contrast text on texture |

**Commit to one nameable direction** ("cold museum catalogue", "sunlit brutalist") and write it in a line
before building. "Unusual" means one distinctive idea executed with discipline; unusual everywhere is noise.

**Precedence, highest first — so nothing silently loses:**
1. An **explicit user style request for this task** outranks everything below, including a default Design
   System (a default is a standing choice, not an instruction for this task). If it clashes with the task
   (hyperreal decoration on an evidence page), state the risk once, then do it — under the truthfulness rules. It does not waive the truthfulness rules,
   the Step 4 accessibility floor, or the type's shipped instructions; on such a clash, say so and keep the floor.
2. A **Design System** (the default, or the one the user names) governs the *look*: colour, type, spacing,
   radius. The task's direction governs *composition, density and energy*. Both apply; on a clash (a playful
   brand system, an investor pitch) keep the system and take the calmest composition it allows. If the
   deliverable is for a different brand than the default system's, say which look you applied and why.
3. Two rows of the table fit: pick the row whose audience is the primary viewer; name the runner-up.

### Hyperrealism — what is honestly achievable
- **Real photography or renders** come only from assets the user supplies or produces elsewhere; upload
  them as assets. If the session has no image-generation tool, do not imply one.
- **Procedural realism** is available in code: layered soft shadows, gradients from a single consistent light
  source, SVG lighting filters (`feTurbulence`, `feDiffuseLighting`, `feSpecularLighting`), grain overlays,
  depth via blur layers. True 3D or shaders need the plain HTML surface; use libraries only from the CDNs
  the Artifact tool allows, or inline them in a self-contained file.
- **Believability checklist:** one light direction · a material (rough or glossy) · contact shadows ·
  scale cues · a little imperfection (grain, dust) · restrained colour. The more photographic a render, the
  more the truthfulness rule below matters.
- **Truthfulness — an image must be true to what it claims.** A generated image or an artist's render is an
  *illustration*, not evidence; a real photograph of somewhere else is not a photograph of "our" site,
  product, sample or person. Label every illustration that could be read as a photograph of something real, and burn the label into the exported image itself
  (a separate caption is lost when the image is exported alone) — for example "Illustration — not a
  photograph of the site". On a page that makes claims about a real place, product or result the label is
  mandatory. Also, by construction: no crop or selection that changes what a photograph shows; a composite is
  labelled "composite", never passed off as one photograph; before/after pairs only under the same conditions;
  charts with honest axes and full ranges; a hand-drawn map area is labelled "schematic". When a supplied
  photo's origin matters to the claim, ask where it came from before using it.
- **Cost:** ship a static fallback for WebGL, honour `prefers-reduced-motion`, stay under the 16 MB page limit.

## Step 4 — Quality bar

This bar is for plain HTML and no-Artifact output. On Design, Design System and Slides the type's shipped
instructions govern and override it.

- One focal point per view. One to three type families, a distinctive display face over a refined body face.
  Avoid the AI tropes: gradient washes, emoji as icons, left-border cards, default Inter / Roboto / Arial.
- Text contrast 4.5:1, or 3:1 for large text (24px, or about 18.7px bold) — WCAG 2.x SC 1.4.3; colours that
  must be told apart differ in lightness, not hue alone.
- Real `<button>` and `<a href>`, never clickable `div`s; touch targets ≥ 44px (the Design type's bar).
- Phone 390×844 and desktop 1280–1440. Plain HTML artifacts also need light and dark themes.
- **Re-read the finished piece for two things:** invented numbers (Step 2) and unlabelled illustrations,
  composites, charts and maps (Step 3) — the images and charts themselves, not only the text.
- **Verify by rendering** plain HTML artifacts: desktop and mobile widths, console clean. The Design type
  instructs not to render or screenshot a canvas unless the user asked — ask first. Where rendering is not
  allowed or no browser tool exists, do not claim it was verified: say "not rendered", read the markup, and
  compute contrast ratios from the colour values rather than judging by eye.

## Step 5 — Ship

Artifacts are private by default; share a link only on the user's word. Sending a design to another service
(Canva, a chat, a deck host) is an outward action needing an explicit yes. When a design becomes a real
site: from the standalone `claude.ai/design`, use its handoff bundle to Claude Code; from an in-session
artifact, hand the markup to the code task directly. Some environments also expose
`import-claude-design-from-url` MCP tools for the reverse direction (not exercised here).

## Known limits

- **Router:** the static keyword map in `hooks/keyword_router.py` sends the bare word "design" to
  `brainstorming`, so a prompt like "design a landing page" may suggest `/brainstorming`. The longer triggers
  above win when the live trigger index contains them; otherwise invoke this skill explicitly.
- **Judgment, not proof:** the truthfulness rules cannot detect a misleading image; they tell the author what
  to check. A reviewer still has to look at the images.
- **Surface facts are point-in-time** (Artifact tool and Claude Design are in flux); re-read the type's
  instructions at use time.
- **Never run on a real task** (below).

## Anti-patterns

| Anti-pattern | Fix |
|---|---|
| A plain HTML page in system fonts although a Design System exists | Step 1, item 2 |
| Hyperreal decoration on a data or evidence page | Restrained or data-forward direction; or label and accept the risk once stated |
| Two directions blended | Name one, delete the rest (a Design System plus a direction is not a blend: Step 3, precedence) |
| Invented statistics to make a slide "look complete" | Placeholder, Step 2 |
| A stock photo of another company's site captioned as "our site" | Step 3, truthfulness |
| Restating the type's authoring rules (file shapes, format) here | Defer to the type's shipped instructions; only routing consequences live in this skill |

## Sources

- Artifact tool contract (quickstart, listing Design Systems, private by default, 16 MB, allowed CDNs, light/dark,
  phone and desktop sizes) — the tool's own description, read 2026-09-28 [DOCS].
- Design / Design System type instructions (print options, no script-built UI, 44px, AI tropes, accessibility) —
  shipped with each type at creation; read 2026-09-28, release `1790365954-8d66` [DOCS].
- Claude Design product (research preview, plans, exports, handoff) —
  https://support.claude.com/en/articles/14604416-get-started-with-claude-design and
  https://www.anthropic.com/news/claude-design-anthropic-labs [DOCS].
- Contrast thresholds — W3C WCAG 2.x SC 1.4.3 (Contrast, Minimum) [DOCS].
- Step 3 direction table and the hyperrealism techniques — design judgment [WEAK]; no source.

## Status

`described`: written 2026-09-28 from the sources above; **never yet run on a real task**. After the first
real use, record what was friction and change this file only for that — not from design taste.
