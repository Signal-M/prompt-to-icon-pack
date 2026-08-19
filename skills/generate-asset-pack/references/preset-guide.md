# Preset selection

Use the smallest preset that covers the request. The bundled catalog lives in `assets/presets.json`.

- `universal-ui-24`: default for an app, website, mini-program, or product with no explicit item list.
- `universal-ui-48`: broader product navigation and actions.
- `emoji-reactions-24`: simple face-like reactions that remain legible at small sizes.
- `character-reactions-24`: expressive sticker poses based on an uploaded character or IP reference.
- `commerce-24`: storefront, cart, order, payment, delivery, and support flows.
- `sports-24`: activities, venue, schedule, participants, ranking, and results.

When neither product context nor character reference exists, use `universal-ui-24` and expose the interpreted list during execution. Never invent semantic names from an unlabeled generated image.

Density profiles:

- `quality`: at most 9 assets per sheet; use for 3D characters, stickers, detailed objects, or identity-sensitive work.
- `balanced`: at most 15 assets per sheet; use for most icon systems.
- `economy`: at most 25 assets per sheet; use only for visually simple assets.
