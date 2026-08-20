# Closed-loop improvement policy

Improve from failures without allowing a single noisy QA verdict to change production behavior.

## Online loop

1. Generate at least two candidate masks for an uncertain icon: the normal boundary-connected mask and a localized corrected mask.
2. Render each candidate beside the same source crop on checkerboard and navy/magenta backgrounds.
3. Give a fresh QA agent only those raw artifacts and the rubric. Require per-icon JSON with `failure_type`, `source_region`, and `retry_action`.
4. Route `crop_error` to a source-box change and `white_removed` to a tightly traced protected polygon or an available semantic-matting backend.
5. Retry at most three times. Never publish an `unsure` result.

## Failure memory

Store one JSONL record per reviewed failure outside the skill package:

```json
{"case_id":"sha256:...","failure_type":"white_removed","asset_kind":"icon","source_region":[118,96,301,183],"strategy":"protected_polygon","result":"pass","reviewer":"visual_qa"}
```

Hash the source crop and keep artifact paths, parameters, QA verdict, and final outcome. Do not store private source images in a public repository.

## Offline promotion

1. Turn confirmed failures into anonymized or synthetic regression fixtures.
2. Measure false publish rate first, then recovery rate, edge quality, and runtime.
3. Promote a new default only when it fixes the target cases without regressing the full corpus.
4. Version the splitter policy and keep a rollback path.

Prefer learned parameter selection from accumulated cases over live code rewriting. Human feedback and independent QA are labels; they are not permission to silently mutate global thresholds.
