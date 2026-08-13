# Game asset pack

The renderer automatically looks for local WebP files using these paths:

- `buildings/{building-id}/level-{level}.webp`
- `walls/level-{level}.webp`
- `scenery/{scenery-id}.webp`

Example:

```text
assets/game/buildings/1000001/level-10.webp
assets/game/buildings/1000008/level-13.webp
assets/game/walls/level-10.webp
assets/game/scenery/classic.webp
```

Building sprites should have a transparent background, be centered, and use a consistent isometric camera. A square canvas such as 256x256 or 512x512 works well. Missing files safely fall back to the built-in procedural building renderer.

Only add assets that you are permitted to use. When using Supercell assets, follow the Supercell Fan Content Policy and keep the unofficial fan-content notice visible in the application.

## Included scenery catalog

The `scenery` folder contains 69 Home Village scenery previews downloaded from
the Clash of Clans Wiki at a maximum width of 1920 pixels. Legendary artwork is
kept in full form, while editor rendering uses the available close-up variant
for a clearer and more accurate playable grid.

`tools/calibrate_scenery.py` regenerates `assets/js/scenery-catalog.js`. Each
catalog entry contains four normalized playable-field corners (`top`, `right`,
`bottom`, and `left`) used by the canvas renderer to transform grid coordinates
without stretching the source artwork.
