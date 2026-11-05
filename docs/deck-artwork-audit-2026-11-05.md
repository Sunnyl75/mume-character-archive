# Deck artwork check — 5 November 2026

The October 14 Mac audit recorded three untracked portrait images beside the
GitHub archive at `700e32f`: `Implementor.png`, `Maia.png` and `Vala.png`.
Lewis supplied those exact named files for integration. They have been copied
without altering their pixels or transparency, and added to the source archive.

No other missing artwork was identified in that audit or the available project
records. The earlier `deck-of-chars-current.zip` contains only HTML, CSS and
JavaScript, so it supplies no additional artwork. The standalone title logo
has a corresponding transparent logo in the source already.

The original WordPress plugin included every image available in its GitHub
source. All 33 explicit HTML/CSS image references resolve. With the three
restored images, the source has 17 recognised portraits and 62 PNG/SVG images
in total, including card backgrounds and site decorations. Every source asset
was compared byte for byte with the rebuilt 1.0.1 plugin ZIP.

The actual frontend portrait selector was run against all 919 immortal records:

| Selected portrait | Character records |
| --- | ---: |
| Maia.png | 834 |
| Vala.png | 81 |
| Implementor.png | 4 |

All selected files exist. More specific optional rank/role images are supported
by the fallback code, but their absence does not demonstrate lost artwork.

The plugin now derives its available portrait list from its installed files.
This allows a plugin update to add artwork even when an older separately
published character dataset is retained. A contract test covers this case.

This check covers the saved audit, available project records, supplied files,
and repository/package assets. It cannot inventory later additions on Lewis's
Mac that have not been shared or pushed.
