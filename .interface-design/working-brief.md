# 光域 spatial redesign — 2026-10-25

Intent: someone with a large Steam library wants a striking, playable-feeling environment while choosing rules, inspecting a plan and explicitly writing it. The previous small ribbon failed the requested immersive atmosphere.

Domain: game collections, saved journeys, grouping, discovery, shelves, branching paths, spatial play.
Color world: graphite, obsidian, pearl, cool mineral green, oxidized copper, moonlit blue.
Signature: fractured triangular relief, braided particulate currents and a resonant mesh share a full-window stage and the same restrained operating shell. These are decorative spatial studies, never data visualizations.
Alternatives resolved: an isolated hero illustration becomes a full-window world; the reference's ASCII rectangular bricks become triangular mineral facets; camera movement and local lift replace RGB glitch/shader copying. No reference source or assets are copied into the application.

Hierarchy: real operating controls remain readable above the world. No animation blocks inputs. The initial invitation gives the main region an anchor, but does not monopolize its background.
Palette: graphite foreground surfaces hold pearl text; mineral green identifies choices and actions; copper and ice are materials in the scene.
Depth: tonal foreground surfaces, actual projected geometry behind them. Existing dialogs keep their real focus and overlay behavior.
Surfaces: a shared cool ground; rules are 88% opaque, review is solid, scenery recedes during review.
Typography: native Chinese/UI stack, 44–52px invitation, 12–14px operations and 11px metadata. No additional font download.
Spacing: 4px base; 16px within groups, 24–32px between operating regions.

Three native scene buttons persist their selection. Pause, system/application reduced motion, visibility, review, context loss and idle rendering are explicit lifecycle states: GPU draws a slow ambient scene; Canvas stops when idle. WebGL2 renders the spatial geometry; Canvas2D and a generated static SVG provide offline fallbacks. No new dependency or packaged asset.

Publication is authorized for v1.1.2; the earlier v1.1.0/v1.1.1 releases and public history references are withdrawn.
