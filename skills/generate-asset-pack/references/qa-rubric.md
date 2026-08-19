# Closed-loop asset QA

## Per-batch publish gate

Require all checks in `semantic-qa.json`:

```json
{
  "status": "pass",
  "batch": 1,
  "expected_count": 9,
  "observed_count": 9,
  "checks": {
    "count": true,
    "order_and_semantics": true,
    "style_consistency": true,
    "identity_consistency": true,
    "no_duplicates_or_omissions": true,
    "crop_and_alpha": true,
    "naming": true
  },
  "failure_class": null,
  "notes": []
}
```

Set `identity_consistency` to true for non-character assets unless identity requirements apply.

## Global visual gate

After deterministic cross-batch QA, write `global-visual-qa.json`:

```json
{
  "status": "pass",
  "checks": {
    "style_anchor_adherence": true,
    "cross_batch_palette": true,
    "cross_batch_scale_and_padding": true,
    "character_identity": true,
    "global_semantic_coverage": true
  },
  "notes": []
}
```

## Failure routing

- `generation_error`: wrong count, concept, duplicate, omission, identity, or style; regenerate that batch with one targeted correction.
- `detection_error`: merged, missing, or extra region; reduce density or rerun detection.
- `crop_error`: clipped edge or detached detail; expand the local source box.
- `alpha_error`: exterior residue or lost internal white; adjust boundary background sampling.
- `naming_error`: correct the external ordered mapping, never the pixels.
- `style_drift`: regenerate only the drifting batch with the same style anchor.
- `vector_error`: keep the raster source and do not publish an inferior SVG.

Stop after three attempts for one batch and report `needs_review`.
