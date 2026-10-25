---
name: 光域 — Steam Library Organizer
description: A native desktop organizer with three interactive spatial environments and a focused classification review.
colors:
  bg: '#090d10'
  sidebar: '#101819'
  surface: '#141d20'
  surface-2: '#1b282a'
  surface-hover: '#263638'
  stroke: '#c1e4d819'
  stroke-strong: '#c1e4d83a'
  text: '#edf5ef'
  muted: '#a7bcb4'
  muted-2: '#95aca2'
  primary: '#c1efd6'
  primary-hover: '#dcf9e7'
  primary-soft: '#b3eccb18'
  success: '#a1cfb4'
  success-soft: '#a1cfb414'
  warning: '#e5c28a'
  warning-soft: '#3a3020'
  danger: '#efa5af'
  danger-soft: '#3c242b'
  field-seaglass: '#73b8b5'
  field-pearl: '#c4d9d4'
  field-copper: '#b0784a'
  light-bg: '#eef2f1'
  light-sidebar: '#e8eeec'
  light-surface: '#fff'
  light-surface-2: '#e5ece9'
  light-surface-hover: '#dce6e2'
  light-stroke: '#24453820'
  light-stroke-strong: '#24453845'
  light-text: '#1e312d'
  light-muted: '#536b63'
  light-muted-2: '#60736c'
  light-primary: '#286b53'
  light-primary-hover: '#1d5742'
  light-primary-soft: '#dcebe3'
  light-success: '#346b50'
  light-success-soft: '#e2eee5'
  light-warning: '#8b601c'
  light-warning-soft: '#fff0d5'
  light-danger: '#b24650'
  light-danger-soft: '#fae7e9'
  light-field-seaglass: 'rgb(31,112,111)'
  light-field-pearl: 'rgb(80,91,158)'
  light-field-copper: 'rgb(145,85,56)'
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
    fontSize: clamp(36px, 3.8vw, 52px)
    fontWeight: 550
    lineHeight: 1.22
    letterSpacing: -0.035em
  headline:
    fontFamily: -apple-system, BlinkMacSystemFont, "Segoe UI Variable Text", "Segoe UI", "Microsoft YaHei UI", sans-serif
    fontSize: 18px
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: "0"
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
  control: 8px
  search: 5px
  choice: 9px
  panel: 14px
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
    rounded: '{rounded.control}'
    padding: 9px 15px
  button-quiet:
    backgroundColor: transparent
    textColor: '{colors.muted}'
    rounded: '{rounded.control}'
    padding: 9px 15px
  search-field:
    backgroundColor: '{colors.bg}'
    textColor: '{colors.text}'
    rounded: '{rounded.search}'
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
  field-control:
    backgroundColor: transparent
    textColor: '{colors.muted}'
    rounded: '{rounded.control}'
    padding: 8px 10px
    height: 36px
---

# Design System: 光域

## Overview

**Creative North Star: "A Library You Can Step Into"**

光域 (formerly Collection) uses a full-window spatial world under a legible graphite operating shell. Three distinct original geometries — triangular mineral relief, braided particles and a resonant mesh — respond to pointer, click and keyboard. The user rejected the isolated ribbon; this source revision replaces it. No reference shader, glyph atlas or image was copied.

Rules, library counts and the next action stay available around the field. Generated review replaces the invitation, artwork and motion controls with a searchable, selectable plan. The latest user decision retains the dark interactive atmosphere and supersedes the earlier Code-Codex square-grid reference with a new name, composition and geometry.

**Appearance scope:** 光域 (`data-appearance="vault"`) is the default and owns unprefixed tokens and rules. Frontmatter records its dark palette and `light-*` mappings; theme follows saved or system preference. P5R (`p5r`) remains the selected alternate **“The Calling Card Collage”**; only `p5r-*` tokens and labeled paragraphs apply to it. RELOAD (`p3r`) and calm retain their existing scope. Saved `traces` preferences migrate to `p5r`. This revision ships with v1.1.2; the old v1.1.0/v1.1.1 releases were withdrawn.

**Key Characteristics:**
- Blue-black and slate layers with sea-glass wayfinding.
- Native system typography with a large, left-aligned two-line invitation.
- Three persistent scene choices with actual projected depth and different mesh / point / line topology.
- Independent review, explicit selections and a persistent next action.

## Colors

Mineral green supplies the operating signal against graphite surfaces. Pearl, mineral and copper belong to decorative materials, not data states. `steam_ui/vault.css` maps foreground roles; `steam_ui/vault.js` owns the spatial materials.

### Primary
- **Sea-glass Signal** (`primary`, `primary-hover`, `primary-soft`): actions, selected rules, current appearance and keyboard focus.
- **Mineral** (`field-seaglass`): the cool material of facets, particles and mesh.

### Secondary
- **Pearl** (`field-pearl`): fine etching and particle highlights.

### Tertiary
- **Copper** (`field-copper`): occasional warm material variation.

### Neutral
- **Blue Black** (`bg`) and **Quiet Slate** (`sidebar`): the open stage and rules column.
- **Slate Layers** (`surface`, `surface-2`, `surface-hover`): review containers and control states.
- **Cool White** (`text`) and **Mist Gray** (`muted`, `muted-2`): main and supporting text.
- **Veiled Sea-glass** (`stroke`, `stroke-strong`): fine boundaries and selected outlines.
- Light mode uses pale cool surfaces, dark teal text, deeper sea-glass controls and darker versions of the corresponding three material inks through `light-*`.

Success, amber warning and rose danger retain their separate semantic roles in both modes.

**The Wayfinding Rule.** Use sea-glass for action, selection and focus; keep iris and copper within the decorative light field.

### P5R alternate only

Signal Red (`p5r-red`) owns the stage, Calling Card Ink (`p5r-ink`) the frame and rules, and Cut Paper (`p5r-paper`) the poster strips and primary action. Review uses the `p5r-bg`, `p5r-surface*`, `p5r-text`, muted and stroke roles; rose `p5r-primary*` marks search focus, checkboxes and hover. It is intentionally distinct from the paper primary button. Amber warnings and rose danger retain semantic meaning. In dark mode success uses paper on a dark neutral; danger shares the primary-hover color. Light mode brightens the red stage and maps review to warm paper and dark ink through `p5r-light-*`; the frame and rules remain black. `steam_ui/p5r.css` owns the full dark/light mappings, including semantic status colors.

**The Alternate Boundary Rule.** Apply P5R red, paper cuts and display typography only inside the selected P5R appearance; 光域 keeps its sea-glass light-field identity.

## Typography

**Display and Body Font:** the native system stack, including Segoe UI Variable Text, Segoe UI and Microsoft YaHei UI. 光域 loads no separate display face; the retained native lettering is an explicit user preference for this application.

### Hierarchy
- **Display:** the left-aligned, two-line invitation; compact desktop uses (40px), mobile (38px).
- **Headline:** current workspace heading, reducing to (17px) on mobile.
- **Title:** review headings; rule headings and control labels use the compact native hierarchy.
- **Body:** inherited reading baseline; the invitation's supporting line uses (13px), (1.8) line height and (26ch) maximum width, reducing to (12px) and (20ch) on mobile.
- **Label:** control names and primary actions.

Exact reusable roles are in frontmatter; incidental small metadata is not a scale for new screens.

**The Native Type Rule.** Use the existing system stack throughout 光域, including its invitation and brand subtitle.

### P5R alternate only

Royal Display is locally hosted Barlow Condensed Black Italic (OFL), used in italic style for the English poster, signature and numeric metrics. It is not a game font. Native system typography carries Chinese copy, controls and review. The `p5r-display`, `p5r-message`, `p5r-metric` and `p5r-review-title` roles capture the reusable hierarchy. The signature uses (18px); confirmation metrics enlarge to (36px). Review titles are bold italic system text. Keep operational labels upright and legible.


## Layout

Desktop uses rows of (64px / 0 / flexible workspace / 24px / 76px), a 252px rules column and stage padding (28px 36px 20px), with 20px gaps. The decorative canvas is fixed behind the entire window. Rules, header and actions have opaque tonal protection; the text area is dimmed locally. A 36–52px native invitation anchors the main region. Scene controls precede inline scan counts.

From 761px through 1100px, rules narrow to 230px, stage side padding becomes 26px and display uses 38px. Desktop heights up to 730px compact stage and rules spacing. At 760px and below the stage precedes settings, the invitation uses 34px, scene tools wrap and the primary action remains sticky.

At (760px) and below, header controls wrap and the stage precedes rules in a vertical flow. Stage and rules use (24px 20px) padding. The invitation has a (330px) minimum height and top-aligned text; its copy maximum is (75%). The field uses a vertical fade. Scope choices become a row and classification choices remain two columns. The action bar sticks to the bottom. Generated review uses a (380px) minimum and (550px) maximum panel height. Compact/mobile states preserve the complete workflow.

Every generated preview, including empty results, enters review and hides the field, invitation, toolbar and library counts. Search and grouped selections use an independently scrolling list. Returning to 光域 restores the field; rules, search and selections remain available.

### P5R alternate only

The desktop frame uses rows of (64px / 40px / flexible workspace / 26px / 76px), a (272px) black rules column and red stage with (20px 28px 16px) padding and (12px) gaps. Its initial poster pairs staggered lettering with task copy; a single black horizontal scan strip replaces floating statistic cards. Generated previews replace the poster with a compact heading and a scrollable review sheet. This state is driven by `has-preview`, including a generated empty result; `has-plan` separately means there are selectable groups. Reset returns the poster.

From (761px) to (1100px), rules narrow to (240px), stage insets to (20px), and poster type to (76px). At (760px) and below, the header wraps and the workspace stacks with rules before the stage. The poster remains a two-column composition with (62px) display text and (19px) task heading; scan metrics wrap into two columns. Review scroll has a (280px) minimum and (55vh) maximum; the inherited bottom action bar remains sticky. Mobile is supplementary to the desktop WebView2 workflow.


## Elevation & Depth

Depth comes from projected geometry in the background and tonal surfaces in the foreground. Default mineral plates have their own thickness and etched faces; particle currents have perspective; the resonant mesh is continuous. Review is an opaque reading surface. No decorative glow halo is used.

### Shadow Vocabulary
- **Overlay:** dark `0 24px 80px #0008`; light `0 24px 80px #20102f26`.
- **Primary hover:** `0 3px 14px #0002`.
- **Search focus:** `0 0 0 2px var(--primary-soft)` beside a sea-glass border.

Ordinary controls transition in 140ms. Native scene choices use a cancellable 240ms canvas fade. Visible full-motion WebGL spaces keep slow ambient movement, drawing at approximately 32ms intervals when idle and 15ms during interaction windows; these are scheduling targets, not hardware performance guarantees. Canvas2D stops at idle. Both cap DPR at 1.5 and backing pixels at 2,000,000. Review, pause, reduced motion, another appearance, hidden documents or context loss stop frame scheduling; pagehide releases GPU buffers, programs and listeners.

Reduced motion and pause keep a still scene; static scene choice and recomposition remain available. Saved keys are `steam-organizer-space-scene` and existing `steam-organizer-particles-paused`. Canvas2D/SVG fallbacks preserve projected compositions with lower material fidelity and density. Context loss displays the SVG still and can rebuild on restoration. Forced colors hides decoration and marks selected controls with system outlines.

**The Quiet Frame Rule.** Keep operating panels stationary, respect explicit pause/reduced motion, and freeze and dim scenery during review.

### P5R alternate only

Depth comes from overlapping rotated paper strips, black cuts and a clipped halftone field. Review stays flat; menus and confirmation use `0 18px 60px #0006`. The dark red-black scrim (`#0c0009b3`) does not blur. Focus uses a visible (2px) current-color outline at (4px) offset; search has a rose outline at (2px) offset.

Source choreography uses `cubic-bezier(.16,1,.3,1)`: a finite two-layer swipe (480ms, second layer delayed 40ms), staggered poster paste (460ms, delays 70/120/160ms), review arrival (300ms), rule slides (180ms) and action lift (160ms). Appearance and preview lifecycle classes clear after (840ms) and (640ms); the overlay never captures input. These timings are source-defined, not independently measured from screenshots. System or stored reduced motion disables animation and transitions and hides decorative cuts. Forced colors removes halftone/cuts and restores explicit system-color boundaries.


## Shapes

Compact corners distinguish controls, scope choices, review and dialogs. Native controls, 8px choices, 9px primary actions, 12px scene groups and 14px review surfaces separate operations from free spatial geometry.

**P5R alternate:** square corners (`p5r-cut`) unify controls, menus, chips and sheets. Selected appearance labels tilt; poster strips alternate black and paper, while the action-bar primary uses a (−7deg) skew. Keep review rows and fields aligned for reading. Irregular geometry is original CSS decoration, not game imagery.


## Components

### Buttons
Primary actions use sea-glass fill and background-colored text; the action-bar primary has a (180px) minimum width, reduced to (140px) on mobile. Secondary actions use surface fill and stronger borders. Quiet and light-field actions stay transparent until hover. Buttons use the control radius; keyboard focus is a visible (2px) primary outline. Disabled controls reduce opacity to (.45), and enabled presses scale to (.98).

### Chips
Sample game chips use background fill, muted text, thin strokes and the chip radius. They wrap inside expanded review groups and communicate examples rather than selection.

### Cards / Containers
Review uses the panel radius, flat tonal fill and inset headers/rows. Scope choices use the choice radius and gain a soft sea-glass fill when selected; enabled classification choices gain a stronger border and sea-glass text. Preserve explicit choice and pressed states.

### Inputs / Fields
Search uses background fill, a fine stroke, the search radius, native text and a desktop maximum width of (440px). Focus adds the soft ring and sea-glass border. Compact layouts hide the inline shortcut.

### Navigation
光域/review controls use a thin sea-glass active underline. Review stays unavailable until a preview has been generated; empty generated results still open review. Appearance controls use soft selected fills. The redundant workflow rail is hidden in this appearance.

### Spatial Worlds and Motion Controls
The invitation is a named keyboard button for click / Enter / Space waves. Three native pressed-state buttons select 棱阵 / 游流 / 回响 without changing the plan, search or selection. Operating controls do not trigger scene pulses. Pause persists; reduced motion overrides it. Recomposition changes only decoration. Generated review freezes the world and reduces it to 16% opacity.

### Review and Confirmation
Review pairs native checkboxes, category names, counts and disclosure controls. Search and bulk selection act on the generated plan. Confirmation keeps selected counts, the SVG close control, backup/write language and the explicit write action; 光域 hides the redundant kicker. See [the light-field implementation record](lightfield-interface.md) for geometry, lifecycle and local validation scope.

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
- **Do** use sea-glass for action, selection and visible keyboard focus.
- **Do** keep native UI lettering and legible foreground surfaces over the full-window world.
- **Do** preserve disabled states, semantic status colors and the explicit preview/write distinction.
- **Do** retain offline rendering, a matching SVG still, pause/change-field controls and reduced-motion behavior.
- **Do** scope P5R styling to its selected alternate, retain its local display font and show review after every generated result, including empty plans.

### Don't:
- **Don't** restore the superseded centered square-grid composition as 光域's identity.
- **Don't** copy Code-Codex or React Bits source or artwork assets.
- **Don't** retain light-field animation behind generated review or schedule continuous idle or hidden frames.
- **Don't** promote tiny incidental labels into a reusable density standard.
- **Don't** require external services or a Node runtime for the desktop interface, or introduce game logos or extracted game assets. Keep requested fan portraits locally bundled with provenance.

### Calm alternate — unreleased revision

Calm uses white and gray surfaces in light mode, charcoal surfaces in dark mode, and blue for actions and selected controls. The source revision removes the card composition and background canvas, shortens repeated copy, and keeps the workspace focused on rules, library counts and review. Shared helper copy is also reduced; Collection and Persona retain their own illustration and motion systems.

Following the `apple-design` and `emil-design-eng` principles, motion communicates input and layout changes: interruptible, critically damped selection sliders, a small button press response, and a finite 240ms preview FLIP with a 220ms content fade. Keyboard and reduced-motion interactions settle immediately; idle and hidden states schedule no slider frames. See [the calm interface specification](calm-interface.md) for lifecycle, responsive behavior and validation. This revision ships in the v1.1.2 Windows packages.
