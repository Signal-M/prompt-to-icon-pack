# Publishing checklist

## Repository identity

- Repository: `Signal-M/prompt-to-icon-pack`
- Product display name: `Prompt to Asset Pack`
- Tagline: `One prompt or character reference in. A coherent, named, transparent, QA-ready visual asset pack out.`
- Suggested GitHub description:

```text
Turn one prompt or IP reference into a coherent visual asset pack. Agent Skills for style-anchored generation, non-grid splitting, white-safe transparency, closed-loop QA, stickers, SVG, and production export.
```

- Suggested topics:

```text
agent-skills codex-plugin claude-code qwen-code ai-icons sticker-generator
image-generation background-removal svg vectorization sprite-sheet design-tools
```

## Before release

1. Review all example assets and confirm redistribution rights.
2. Search for keys, tokens, personal paths, email addresses, caches, and generated bundles.
3. Run `PYTHON=<python-with-pillow-and-numpy> ./scripts/validate.sh`.
4. Run the Codex plugin validator from `plugin-creator`.
5. Confirm `.codex-plugin/plugin.json`, `.claude-plugin/plugin.json`, and `qwen-extension.json` use the intended semantic version.
6. Verify the old `generate-icon-batch` entry and `icons` schema still work.
7. Review the SVG limitation language; never imply that complex traced art is clean hand-authored vector source.

## Recommended next release

- Version: `v0.7.0`
- Title: `v0.7.0 — Library-first SVG and benchmarked semantic alpha QA`

Release highlights:

- library-first Iconify resolution with explicit semantic and license review;
- dry-run-first Recraft V4.1 native SVG generation and reviewed cost estimates;
- optional rembg BiRefNet/SAM alpha candidates plus conservative white-preserving fusion;
- hard deterministic gating for suspected white-detail removal;
- a reproducible CC0 1,000-icon alpha regression corpus;
- generated quality and 25-icon cost metrics in `BENCHMARKS.md`;
- reviewed mixed Iconify/Recraft SVG packaging;
- backward compatibility with the original raster sheet workflow.

## Launch copy

### Chinese

```text
Prompt to Icon Pack 升级成 Prompt to Asset Pack 了。

现在它不仅能生成 Icon，还能根据一张 IP 参考图批量生成表情包。大批量任务会先建立 Style Anchor，再拆成多张 Sheet，并通过跨批次 QA 检查角色身份、配色、比例、漏项和重复。

它会自动拆图、保护内部白色、透明抠图、命名、添加可靠字幕，并导出 PNG、WebP、雪碧图、工程映射和可选 SVG。Codex、Claude Code、Qwen Code 和 WorkBuddy 共用一套 Agent Skills 核心。
```

### English

```text
Prompt to Icon Pack has grown into Prompt to Asset Pack.

It now creates icons, emoji, character stickers, avatars, badges, and sprites from one prompt or reference. Large packs use style anchors and cross-batch QA; outputs can include transparent PNG/WebP, sprites, mappings, reliable sticker captions, and QA-validated SVG for eligible artwork.

The same Agent Skills core ships with Codex, Claude Code, Qwen Code, WorkBuddy, and QwenWork adapters.
```
