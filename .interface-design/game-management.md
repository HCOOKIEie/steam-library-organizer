# Game management

User: owner of a large local Steam library who wants direct sorting, not promotional copy.
Task: find games, put them into folders, order them, batch-label them, optionally publish categories to Steam.
Feel: a quiet file browser; actual games and selection lead the screen.

Domain: game library, installed games, launch entries, playtime, folders, tags, selected games.
Color world: reuse the four existing themes—neutral paper, graphite, Steam blue, mint status, muted grey; one theme accent, no new palette.
Signature: a game row shows its actual Steam time separately from editable personal time; dragging from its grip to a folder appends it, dragging to a game reorders it. Persistent local edits and explicit Steam sync are distinct actions.
Avoid: marketing headlines → direct function labels; cards for every game → compact list; all batch actions always visible → actions appear after selection.

Layout: native dialog up to 1180×820; 196px folder sidebar; 24px outer padding; 76px game rows; 24px heading and 14px game titles. Surface shifts and subtle separators follow existing tokens.
States: loading, empty, filtered, selected, conflict, pending sync, save error; native focus trapping, keyboard ordering and editor cancellation; 180ms entry respecting reduced motion.
Copy: use action, object, result. No “下一场冒险”“心动”“一起”“让…”. Keep technical storage details in docs, not primary UI.

Series classification remains a normal rule in the existing left panel, with the same preview and confirmation controls. It never rearranges the user's manual folders. “Move to end” is available in all sort views and restores the manual view after a successful save, so the result is visible immediately.
