# 本机游戏导入

Intent: the same person organizing Steam wants to bring independently installed
games and live-service games into one launch list, without repeatedly browsing
for EXEs. The flow should feel calm, quick, and recoverable.

Domain: installed games, launchers, launch arguments, Steam shortcuts, collections,
removable drives, duplicate entries. Color world: the current theme's graphite,
pearl, Steam blue, mineral green and quiet warning amber; no new palette.

Signature: each row pairs the exact launch path with a three-state decision:
recognized, needs review, already in Steam. The list chooses known games only;
uncertain candidates require a deliberate choice. Launch information and name
editing fold underneath the row, not into another settings page.

One row represents one game. Alternative shortcuts/launchers/binaries belong in
that row's launch-information disclosure, with one choice submitted to the server.
Keep unrelated games sharing a launcher separate. Scan coverage is an optional
disclosure; incomplete locations are labelled instead of implying a full-disk scan.

Avoid a new dashboard, decorative statistics, or an automatic all-EXE import.
Use the existing sidebar entry and one native modal dialog with focus containment.
The selected count and single import action stay in its footer. Final confirmation
replaces the list within that dialog; no nested modal or competing action.

Hierarchy: 26px/650 heading, 14px/600 game name, 12px muted path and source.
Depth: theme surface and low-contrast separators. Spacing: 4px base, 12px rows,
20–28px sections, 40px buttons and 44px selection targets. Reuse semantic tokens,
native Chinese type and the existing button styles. Entry is 180ms opacity/8px
translation; reduce-motion removes movement. No background animation is added.
