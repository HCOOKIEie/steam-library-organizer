# Game wheel

Owner: a Steam user arranging a large library. Browse actual games, filter, then open the selected game in the existing manager. Classification remains a separate reviewed operation.

Visual language: graphite / slate / pale blue, shared across sidebar, content and footer. Actual covers are the focal material; unavailable covers use title initials. No invented data panels, soundtrack, particle wallpaper or generated artwork.

Reference: local `D:/myskills/haloflux` preview, README and ring-motion source structure. Its concentric depth and deliberate rotation informed the direction. New DOM geometry, card layout, controls, timing and styles were written for this app; no HALOFLUX code, graphics or audio were copied.

Motion-web application: finite damped selection spring (stiffness 155, damping 22, delta time capped at 32 ms), direct pointer displacement at 120 px per slot with release detents, wheel threshold 60 px plus 440 ms momentum guard. Secondary ring rotation follows card position. No idle rAF. Reduced motion lands immediately; review, dialog, hidden page and pagehide cancel frames.

Radiance extension: 176 original radial filaments in four independent bands, roughly 30fps at rest, decaying selection burst and bounded pointer deflection. Canvas is decorative, behind the cards, clipped to the exhibit; it never blocks input. A persistent pause control and static CSS fallback accompany it. The carousel itself remains finite; radiance owns a separate cancellable animation clock.

Composition: seven covers on a shallow circular arc, selected cover forward, details to the right. Navigation and search sit below the arc; below 820 px details stack. Image cache failure leaves a usable typographic cover. Only real Steam app IDs become CDN URLs; hashed assets resolve through an account-bound read-only endpoint. No library write or game launch occurs on selection.

Validation: real library / cover loading, keyword and installed filters, keyboard wrap, direct drag, trackpad momentum, finite settling, modal handoff, hidden / review suspension, forced colors and reduced motion. Keep normal game-management and classification checks.
