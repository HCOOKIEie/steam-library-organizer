---
name: Collection — Steam Library Organizer
description: A native desktop organizer with a black/violet interactive square field and focused classification review.
colors:
  bg: '#08080a'
  sidebar: '#0d0d10'
  surface: '#141317'
  surface-2: '#1d1b22'
  surface-hover: '#28232f'
  stroke: '#e6d8ff16'
  stroke-strong: '#e6d8ff30'
  text: '#f3f0f7'
  muted: '#b5adbf'
  muted-2: '#a297af'
  primary: '#caa2f2'
  primary-hover: '#dfbcff'
  primary-soft: '#a45fe31c'
  success: '#b1c9bb'
  success-soft: '#b1c9bb14'
  warning: '#e2c391'
  warning-soft: '#392c20'
  danger: '#f1a8b9'
  danger-soft: '#3d2230'
  particle-fallback: '#a02cda'
  light-bg: '#f5f3f8'
  light-sidebar: '#f5f3f8'
  light-surface: '#fff'
  light-surface-2: '#ede9f2'
  light-surface-hover: '#e4deed'
  light-stroke: '#33244721'
  light-stroke-strong: '#33244740'
  light-text: '#241c30'
  light-muted: '#645a70'
  light-muted-2: '#73687f'
  light-primary: '#763cb2'
  light-primary-hover: '#602a98'
  light-primary-soft: '#e8def4'
  light-success: '#526c60'
  light-success-soft: '#e4eee7'
  light-warning: '#815c24'
  light-warning-soft: '#f4e9d8'
  light-danger: '#a83c56'
  light-danger-soft: '#f9e0e8'
  light-particle-fallback: '#7c3bb5'
  p5r-red: '#c90d25'
  p5r-ink: '#101010'
  p5r-paper: '#fff9ed'
  p5r-bg: '#121212'
  p5r-surface: '#1a1a1a'
  p5r-surface-2: '#262626'
  p5r-surface-hover: '#333'
  p5r-text: '#faf7f0'
  p5r-muted: '#c1bdb7'
  p5r-muted-2: '#aaa59e'
  p5r-stroke: '#3c3938'
  p5r-stroke-strong: '#686360'
  p5r-primary: '#ff6271'
  p5r-primary-hover: '#ff8d96'
  p5r-primary-soft: '#402028'
  p5r-warning: '#f4d494'
  p5r-warning-soft: '#3b301e'
  p5r-danger-soft: '#3a2026'
  p5r-light-red: '#e21d30'
  p5r-light-bg: '#f0ece4'
  p5r-light-surface: '#fffaf1'
  p5r-light-text: '#171313'
  p5r-light-primary: '#b70b23'
typography:
  display:
    fontFamily: -apple-system, BlinkMacSystemFont, "Segoe UI Variable Text", "Segoe UI", "Microsoft YaHei UI", sans-serif
    fontSize: clamp(24px, 2.6vw, 38px)
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: -0.02em
  headline:
    fontFamily: -apple-system, BlinkMacSystemFont, "Segoe UI Variable Text", "Segoe UI", "Microsoft YaHei UI", sans-serif
    fontSize: 23px
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: 0.5px
  title:
    fontFamily: -apple-system, BlinkMacSystemFont, "Segoe UI Variable Text", "Segoe UI", "Microsoft YaHei UI", sans-serif
    fontSize: 14px
    fontWeight: 500
  body:
    fontFamily: -apple-system, BlinkMacSystemFont, "Segoe UI Variable Text", "Segoe UI", "Microsoft YaHei UI", sans-serif
    fontSize: 13px
    lineHeight: 1.6
  label:
    fontFamily: -apple-system, BlinkMacSystemFont, "Segoe UI Variable Text", "Segoe UI", "Microsoft YaHei UI", sans-serif
    fontSize: 12px
    fontWeight: 500
  p5r-display:
    fontFamily: '''Royal Display'', ''Microsoft YaHei UI'', sans-serif'
    fontSize: clamp(64px, 7.7vw, 112px)
    fontWeight: 900
    lineHeight: 0.88
    letterSpacing: -0.025em
  p5r-message:
    fontFamily: -apple-system, BlinkMacSystemFont, "Segoe UI Variable Text", "Segoe UI", "Microsoft YaHei UI", sans-serif
    fontSize: clamp(22px, 2.4vw, 36px)
    fontWeight: 850
    lineHeight: 1.55
    letterSpacing: -0.02em
  p5r-metric:
    fontFamily: '''Royal Display'', ''Microsoft YaHei UI'', sans-serif'
    fontSize: 30px
    fontWeight: 900
    lineHeight: 1
  p5r-review-title:
    fontFamily: -apple-system, BlinkMacSystemFont, "Segoe UI Variable Text", "Segoe UI", "Microsoft YaHei UI", sans-serif
    fontSize: 26px
    fontWeight: 850
    letterSpacing: -0.02em
rounded:
  p5r-cut: 0px
  chip: 3px
  control: 5px
  choice: 6px
  panel: 8px
  dialog: 12px
spacing:
  tight: 4px
  control: 8px
  compact: 12px
  group: 16px
  inset: 20px
  section: 24px
components:
  button-primary:
    backgroundColor: '{colors.primary}'
    textColor: '{colors.bg}'
    rounded: '{rounded.control}'
    padding: 12px 24px
    typography: '{typography.label}'
  button-primary-hover:
    backgroundColor: '{colors.primary-hover}'
    textColor: '{colors.bg}'
  button-secondary:
    backgroundColor: '{colors.surface}'
    textColor: '{colors.text}'
    rounded: 7px
    padding: 9px 15px
  button-quiet:
    backgroundColor: transparent
    textColor: '{colors.muted}'
    rounded: 7px
    padding: 9px 15px
  search-field:
    backgroundColor: '{colors.bg}'
    textColor: '{colors.text}'
    rounded: '{rounded.control}'
    padding: 8px 10px
  review-panel:
    backgroundColor: '{colors.surface}'
    rounded: '{rounded.panel}'
  game-chip:
    backgroundColor: '{colors.bg}'
    textColor: '{colors.muted}'
    rounded: '{rounded.chip}'
    padding: 4px 8px
  p5r-button-primary:
    backgroundColor: '{colors.p5r-paper}'
    textColor: '{colors.p5r-ink}'
    rounded: '{rounded.p5r-cut}'
    padding: 12px 24px
    height: 44px
  p5r-search-field:
    backgroundColor: '{colors.p5r-bg}'
    textColor: '{colors.p5r-text}'
    rounded: '{rounded.p5r-cut}'
    padding: 8px 10px
  p5r-review-panel:
    backgroundColor: '{colors.p5r-surface}'
    textColor: '{colors.p5r-text}'
    rounded: '{rounded.p5r-cut}'
  p5r-rule-selected:
    backgroundColor: '{colors.p5r-paper}'
    textColor: '{colors.p5r-ink}'
    rounded: '{rounded.p5r-cut}'
    padding: 10px 12px 10px 36px
  particle-control:
    backgroundColor: '{colors.surface}'
    textColor: '{colors.muted}'
    rounded: '{rounded.control}'
    padding: 8px 10px
    height: 36px
---

# Design System: Collection

## Overview

**Creative North Star: "The Violet Square Workspace"**

Collection is a native desktop organizer framed by near-black surfaces, violet selections and a flat field of small square particles. The centered invitation leaves the controls legible and the library task immediately available. The user-pinned Code-Codex screenshot supplies the particle identity; the implementation is original, code-led Canvas2D, with no approved comp.

The ordinary operating frame carries rules, preview, search, selection and explicit confirmation. Generated review replaces the invitation and particle field. This replaces the rejected green landscape/serif gallery; its local Newsreader font and landscape SVGs are removed from shipping.

**Appearance scope:** Collection (`data-appearance="vault"`) is the default and owns unprefixed tokens and rules. The frontmatter records its dark palette and `light-*` mappings; theme follows saved or system preference. P5R (`p5r`) remains the selected alternate **“The Calling Card Collage”**; only `p5r-*` tokens and labeled paragraphs apply to it. RELOAD (`p3r`) and calm retain their existing scope. Saved `traces` preferences migrate to `p5r`.

**Key Characteristics:**
- Near-black and cool neutral layers with violet wayfinding.
- Native system typography across the default appearance.
- Right-dense, grid-aligned square particles with a quiet centered invitation.
- Flat review, clear selections, and a persistent next action.

## Colors

Cool violet supplies the interactive signal against near-black and cool neutral surfaces. Frontmatter is normative; `steam_ui/vault.css` owns the complete dark/light mappings.

### Primary
- **Violet Signal** (`primary`, `primary-hover`, `primary-soft`): actions, selected rules, current workflow step and focus.
- **Violet Squares** (`particle-fallback`): static field fallback. Canvas varies square opacity and violet channels with pointer/wave state; these artwork values do not introduce additional control accents.

### Neutral
- **Near Black** (`bg`, `sidebar`): stage, operating frame and rules column.
- **Cool Layers** (`surface`, `surface-2`, `surface-hover`): review containers and control states.
- **Cool White** (`text`) and **Soft Lavender Gray** (`muted`, `muted-2`): main and supporting text.
- **Veiled Violet** (`stroke`, `stroke-strong`): fine boundaries and selected outlines.
- Light mode maps the same roles to pale lavender surfaces, dark plum text and deeper violet action colors through `light-*`; it retains the square field.

Success, amber warning and rose danger retain their separate semantic roles in both modes.

**The Wayfinding Rule.** Reserve violet for action, selection, focus and the square field; keep operational surfaces within neutral layers.

### P5R alternate only

Signal Red (`p5r-red`) owns the stage, Calling Card Ink (`p5r-ink`) the frame and rules, and Cut Paper (`p5r-paper`) the poster strips and primary action. Review uses the `p5r-bg`, `p5r-surface*`, `p5r-text`, muted and stroke roles; rose `p5r-primary*` marks search focus, checkboxes and hover. It is intentionally distinct from the paper primary button. Amber warnings and rose danger retain semantic meaning. In dark mode success uses paper on a dark neutral; danger shares the primary-hover color. Light mode brightens the red stage and maps review to warm paper and dark ink through `p5r-light-*`; the frame and rules remain black. `steam_ui/p5r.css` owns the full dark/light mappings, including semantic status colors.

**The Alternate Boundary Rule.** Apply P5R red, paper cuts and display typography only inside the selected P5R appearance; Collection keeps its violet particle identity.

## Typography

**Display and Body Font:** the native system stack, including Segoe UI Variable Text, Segoe UI and Microsoft YaHei UI. Collection loads no separate display face. The user-pinned reference establishes native interface lettering.

### Hierarchy
- **Display:** regular-weight centered invitation; mobile uses (25px) and a (280px) text maximum.
- **Headline:** current workspace heading, reducing to (21px) in short windows and (19px) on mobile.
- **Title:** rules and review headings.
- **Body:** inherited reading baseline; **Label:** control names and primary actions.

Exact roles are in frontmatter; incidental small metadata is not a scale for new screens.

**The Native Type Rule.** Use the system stack throughout Collection, including its invitation and brand subtitle.

### P5R alternate only

Royal Display is locally hosted Barlow Condensed Black Italic (OFL), used in italic style for the English poster, signature and numeric metrics. It is not a game font. Native system typography carries Chinese copy, controls and review. The `p5r-display`, `p5r-message`, `p5r-metric` and `p5r-review-title` roles capture the reusable hierarchy. The signature uses (18px); confirmation metrics enlarge to (36px). Review titles are bold italic system text. Keep operational labels upright and legible.


## Layout

Desktop uses rows of (68px / 40px / flexible workspace / 24px / 76px), a (272px) rules column, and a stage with (28px 36px 20px) padding and (16px) gaps. The square field fills the stage behind its compact header, centered invitation, low-profile pause/shuffle toolbar and inline library counts. Particle density increases to the right; the invitation area is dimmed for legibility without a card.

Between (761px) and (1100px), rules narrow to (240px) and stage side padding to (24px). Desktop heights up to (780px) tighten rows to (60px / 36px / flexible / 22px / 68px), stage padding to (20px 28px 16px), and gaps to (12px).

At (760px) and below, header controls wrap and the stage precedes rules in a vertical flow. The invitation has a (310px) minimum height; particle controls wrap centrally, scope choices become a row, and classification choices stay in two columns. The action bar sticks to the bottom. Generated review uses a (380px) minimum and (550px) maximum panel height. This is primarily a desktop WebView2 tool; compact/mobile states preserve the complete workflow.

Review replaces the field and invitation after every generated preview, including empty results. Search, selection tools and grouped rows use the available stage with an independently scrolling list. Reset restores the collection view.

### P5R alternate only

The desktop frame uses rows of (64px / 40px / flexible workspace / 26px / 76px), a (272px) black rules column and red stage with (20px 28px 16px) padding and (12px) gaps. Its initial poster pairs staggered lettering with task copy; a single black horizontal scan strip replaces floating statistic cards. Generated previews replace the poster with a compact heading and a scrollable review sheet. This state is driven by `has-preview`, including a generated empty result; `has-plan` separately means there are selectable groups. Reset returns the poster.

From (761px) to (1100px), rules narrow to (240px), stage insets to (20px), and poster type to (76px). At (760px) and below, the header wraps and the workspace stacks with rules before the stage. The poster remains a two-column composition with (62px) display text and (19px) task heading; scan metrics wrap into two columns. Review scroll has a (280px) minimum and (55vh) maximum; the inherited bottom action bar remains sticky. Mobile is supplementary to the desktop WebView2 workflow.


## Elevation & Depth

Depth comes from cool tonal layers and fine borders. The field consists of flat squares with no landscape, relief or perspective. Review panels stay flat. Menus and confirmation use the overlay shadow; enabled primary actions gain a small hover shadow. The confirmation scrim blurs the workspace.

### Shadow Vocabulary
- **Overlay:** dark `0 24px 80px #0008`; light `0 24px 80px #20102f26`.
- **Primary hover:** `0 3px 14px #0002`.
- **Search focus:** `0 0 0 2px var(--primary-soft)` with a violet border.

Ordinary controls transition in (140ms); review arrives in (220ms) with `cubic-bezier(.22,1,.36,1)` when full motion is allowed. The original Canvas2D renderer caps DPR at (1.5) and paints at approximately (30fps). Initial twinkling lasts (4.8s); pointer, wave and shuffle input briefly restart it, then animation stops at idle. Review, other appearances and hidden documents stop frames. Page hide disposes listeners/observers and page show starts rendering again.

Reduced motion or manual pause leaves a still composition; shuffle remains available. Manual pause persists at `steam-organizer-particles-paused`. Canvas failure retains a generated static SVG of the same sampled square field; forced colors hides the decorative field and restores the interaction boundary.

**The Quiet Frame Rule.** Keep operational panels still; confine finite particle motion to the visible collection stage.

### P5R alternate only

Depth comes from overlapping rotated paper strips, black cuts and a clipped halftone field. Review stays flat; menus and confirmation use `0 18px 60px #0006`. The dark red-black scrim (`#0c0009b3`) does not blur. Focus uses a visible (2px) current-color outline at (4px) offset; search has a rose outline at (2px) offset.

Source choreography uses `cubic-bezier(.16,1,.3,1)`: a finite two-layer swipe (480ms, second layer delayed 40ms), staggered poster paste (460ms, delays 70/120/160ms), review arrival (300ms), rule slides (180ms) and action lift (160ms). Appearance and preview lifecycle classes clear after (840ms) and (640ms); the overlay never captures input. These timings are source-defined, not independently measured from screenshots. System or stored reduced motion disables animation and transitions and hides decorative cuts. Forced colors removes halftone/cuts and restores explicit system-color boundaries.


## Shapes

Practical small corners distinguish controls, choices, panels and dialogs through frontmatter radius roles. Thin borders and simple local line SVG icons carry structure. Particle squares stay square; their geometry does not dictate every control.

**P5R alternate:** square corners (`p5r-cut`) unify controls, menus, chips and sheets. Selected appearance labels tilt; poster strips alternate black and paper, while the action-bar primary uses a (−7deg) skew. Keep review rows and fields aligned for reading. Irregular geometry is original CSS decoration, not game imagery.


## Components

### Buttons
Primary actions use violet on the background color, the control radius and frontmatter padding; the action-bar primary has a (180px) minimum width, reduced to (140px) on mobile. Secondary actions use surface fill and stronger borders. Quiet actions stay transparent until hover. Keyboard focus is a visible (2px) primary outline; disabled controls reduce opacity to (.45), and enabled presses scale to (.98).

### Chips
Sample game chips use background fill, muted text, thin strokes and the chip radius. They wrap inside expanded review groups and communicate examples rather than selection.

### Cards / Containers
Review uses the panel radius, flat tonal fill and inset headers/rows. Scope choices gain a soft violet fill when selected; enabled classification choices gain a stronger border and violet text. Preserve explicit choice and pressed states.

### Inputs / Fields
Search uses background fill, a fine stroke, control radius, native text and a desktop maximum width of (440px). Focus adds the soft ring and violet border. Compact layouts hide the inline shortcut.

### Navigation
Collection/review controls use a thin violet active underline. Review stays unavailable until a preview has been generated; empty generated results still open review. Appearance controls use soft selected fills; workflow steps pair labels with outlined circles and fill the current index.

### Square Field and Particle Toolbar
The focusable invitation exposes a button role and a descriptive interaction label. Pointer movement wakes nearby cells; click, Enter and Space release a wave. Buttons, inputs, links and summaries do not trigger click waves. Touch omits pointer trails. Pause exposes pressed state, persists its preference and becomes disabled with an explicit reduced-motion label when required. Shuffle regenerates the field even while still. The toolbar and field disappear in generated review.

### Review and Confirmation
Review pairs native checkboxes, category names, counts and disclosure controls. Search and bulk selection act on the generated plan. Confirmation keeps selected counts, the SVG close control, backup/write language and the explicit write action; Collection hides the redundant kicker.

### P5R alternate components

- **Primary action:** paper fill, black bold text and a (2px) paper border. The action-bar version is at least (200px × 44px), skewed; hover lifts (2px) and turns dark red with white text/border, while press scales to (.98). At mobile widths its minimum width is (136px). Preserve inherited disabled treatment.
- **Rules and navigation:** selected scope cards invert to paper/ink and shift right (3px); classification toggles use red fill and a white diamond marker. Presets invert to paper/ink. The selected appearance label is a tilted paper tab; workflow indices are square, skewed stamps. Choice, pressed and keyboard-focus states remain explicit.
- **Review and search:** square tonal sheet with a (17px), heavy heading; rows are at least (46px), disclosure and bulk controls (36px). Hover uses soft rose; counts sit on the second surface tone. Search keeps system text, a (36px) minimum height, and the outlined focus treatment. Chips use square cuts. Light review changes material without recoloring the black rules column.
- **Confirmation:** square sheet with a (2px) paper border and (28px) padding, reduced to (20px) on mobile; bold italic system heading and Royal Display numbers. Keep the close control, selected counts, backup language and explicit write action. Appearance changes preserve search and selections.

### P3R / P5R interactive motion

P3R display text uses locally bundled upright Anton Regular (`Reload Block`), without italic slant or extruded shadows. The English title and secondary line share the same family; coordinate text, a vertical `RE:PLAY` word and header/footer microtype frame the composition. Keep the title background open. Do not restore centered concentric dials, radial tick marks, crosshairs or decorative bubble clusters. See `docs/p3r-motion-reference.md` for the observed menu transition.

P5R keeps its angled Barlow Condensed title but fills the composition with a black edition strip, an outlined comic emblem and a tilted paper calling card. The portrait adds a top paper label, scarlet star, edge speed lines and a bordered signature strip. These are decorative, hidden from assistive technology and never styled as extra actions. Hero rows grow from their content and use a compact type/spacing treatment below 760px height; illustration and controls must not overlap.

The homepage pairs large type with a simple flat character profile: blue/white Makoto Yuki and black/white/red Joker. These are locally bundled AI-generated fan illustrations (see `docs/persona-art-prompts.md`), not extracted game artwork. Avoid complex clothing, fine hair strands and painterly rendering.

The hero is a separate, clipped surface; portrait, water and effects cannot overlap rules, statistics, search or buttons. No blend modes are used. P3R reveals the whole hero through the union of two expanding circular SVG masks from opposite corners. Radius growth takes 460ms with a 55ms stagger; the mask is removed at 515ms, or immediately when interrupted. These are adaptation timings, not measurements of the original. Water light is calculated at 224×112 and stretched across the hero, with broad cyan surface patches fading into cobalt at approximately 30fps while visible. The portrait drifts by at most 4px vertically. Observe the unclipped stage rather than the masked portrait to avoid falsely stopping the transition when the initial circle has zero area. P5R keeps a black, white-bordered five-point comic impact and a sharp speed cut (580ms). Both retain shallow spring parallax (stiffness 110, damping 16) and explicit replay.

Motion tools have 36px minimum targets. Pause persists under `steam-organizer-persona-paused`, cancels replay and stops rendering. System/application reduced motion takes precedence. Pointer, Enter and Space activate only the illustration surface. Hidden windows, offscreen scenes, other themes, page hide and generated review stop all frames. P5R also stops at idle; P3R water continues only while visible and permitted. Review hides the entire hero and its motion controls, including for empty generated results. Canvas failure keeps the cutout and CSS composition. Assets are embedded as data URLs in the desktop and standalone preview; no runtime download, image service, sound or new runtime dependency is required.

## Do's and Don'ts

### Do:
- **Do** use violet for action, selection and visible keyboard focus.
- **Do** keep Collection typography native and its field flat, square and denser toward the right.
- **Do** preserve disabled states, semantic status colors and the explicit preview/write distinction.
- **Do** retain offline rendering, a static SVG fallback, pause/shuffle controls and reduced-motion behavior.
- **Do** scope P5R styling to its selected alternate, retain its local display font and show review after every generated result, including empty plans.

### Don't:
- **Don't** restore the rejected green landscape, serif invitation, relief or perspective to Collection.
- **Don't** copy Code-Codex or React Bits source or artwork assets.
- **Don't** retain particle animation behind generated review or run it continuously while idle or hidden.
- **Don't** promote tiny incidental labels into a reusable density standard.
- **Don't** require external services or a Node runtime for the desktop interface, or introduce game logos or extracted game assets. Keep requested fan portraits locally bundled with provenance.
