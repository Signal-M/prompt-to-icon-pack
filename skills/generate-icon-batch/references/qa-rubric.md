# Closed-loop QA rubric

Evaluate every batch against both the ordered specification and the source sheet. A visually polished sheet can still fail.

## Publish gate

All checks must pass:

1. `count`: detected output count equals the planned count.
2. `order_and_semantics`: each reading-order position clearly represents its planned label and description.
3. `style_consistency`: palette, rendering style, viewpoint, scale, padding, and detail level form one coherent set.
4. `no_duplicates_or_omissions`: every planned concept appears exactly once with no near-duplicate replacing another item.
5. `crop_and_alpha`: no subject is clipped or merged with a neighbor; exterior background is transparent; internal white and intentional embedded details remain opaque.
6. `naming`: every PNG filename and manifest label matches the external ordered specification.

Inspect the original sheet at full resolution when judging small detached details. Use the checkerboard contact sheet for alpha damage, but do not use it alone to judge semantic correctness.

## Failure routing

- Regenerate the sheet for count, semantic, duplicate, omission, order, or style failures.
- Re-split or apply a source-box override for localized crop, merged-neighbor, or alpha failures.
- Reduce batch size if the same generation or detection failure recurs twice.
- Stop after three attempts and report `needs_review`; never create a final package by bypassing a failed gate.

## `semantic-qa.json`

Create one file inside each `batch-NN` directory:

```json
{
  "status": "pass",
  "batch": 1,
  "expected_count": 12,
  "observed_count": 12,
  "checks": {
    "count": true,
    "order_and_semantics": true,
    "style_consistency": true,
    "no_duplicates_or_omissions": true,
    "crop_and_alpha": true,
    "naming": true
  },
  "notes": []
}
```

Set `status` to `needs_review` and explain every failed position in `notes` when any check is false. The packaging script rejects missing or failed semantic QA.
