# GitHub publishing checklist

## Recommended repository identity

- Repository name: `prompt-to-icon-pack`
- Display name: `Prompt to Icon Pack`
- Tagline: `One prompt in. A consistent, named, transparent icon pack out.`
- GitHub About description:

```text
Turn one prompt into a consistent, named, transparent icon pack. Codex skills for sheet-first generation, non-grid splitting, white-safe background removal, closed-loop QA, and production-ready PNG + ZIP export.
```

- Suggested topics:

```text
codex-skill ai-icons icon-generator image-generation sprite-sheet
background-removal computer-vision mini-program developer-tools design-tools
```

## Before publishing

1. Confirm the repository URL uses `m2290526022-boop/prompt-to-icon-pack`.
2. Confirm the MIT license attribution. It currently uses `Xiaohao`.
3. Review the demo sheet and confirm you are comfortable publishing it under the repository license.
4. Search the repository for API keys, tokens, personal paths, email addresses, and generated cache files.
5. Run `./scripts/validate.sh`.
6. Decide whether the first public version is `v0.1.0` (recommended while interfaces may still change) or `v1.0.0`.

## Create the repository

Create an empty public repository on GitHub named `prompt-to-icon-pack`. Do not add a README, `.gitignore`, or license in the GitHub form because this directory already contains them.

Then run locally:

```bash
cd /path/to/prompt-to-icon-pack
git init
git add .
git commit -m "feat: publish Prompt to Icon Pack"
git branch -M main
git remote add origin https://github.com/m2290526022-boop/prompt-to-icon-pack.git
git push -u origin main
```

These commands publish externally. Review `git status` and `git diff --cached` before committing.

## Configure the GitHub page

1. Paste the recommended About description.
2. Add all suggested topics.
3. Set the website field only when a demo or documentation site exists.
4. Enable Issues for bug reports and difficult test sheets.
5. Consider enabling Discussions for prompts, examples, and feature ideas.
6. Upload a social preview image showing “generated sheet → transparent named pack.”
7. Pin the repository on your GitHub profile.

## First release

Create a `v0.1.0` release with:

- the two skill folders;
- the tested 3×3 example;
- installation instructions;
- a note that prompt-to-pack generation needs Codex ImageGen;
- a note that macOS Vision OCR is optional and only used for captioned legacy sheets.

Suggested release title:

```text
v0.1.0 — From one prompt to a QA-checked icon pack
```

## Launch copy

### Chinese

```text
我开源了 Prompt to Icon Pack：一句 Prompt，生成整套风格一致、背景透明、自动命名的 Icon。

它不是只负责“生成图”，而是把 Icon Sheet 生成、非网格拆分、背景透明化、中文命名、内部白色保护和闭环 QA 串成一条流水线。生成错误会重画，裁切错误会重拆，没通过 QA 就不会输出最终 ZIP。

适合小程序、App、游戏和 AI 编程项目。欢迎试用，也欢迎贡献难拆分的 Icon Sheet。
```

### English

```text
I open-sourced Prompt to Icon Pack: one prompt in, a consistent, named, transparent icon pack out.

It connects sheet-first generation, non-grid detection, white-safe background removal, semantic naming, and closed-loop QA. Generation mistakes are regenerated, extraction mistakes are re-split, and failed batches are never silently shipped.

Built for apps, mini-programs, games, and AI coding workflows. Hard icon sheets and contributions are welcome.
```

## What earns trust and stars

- Keep the real before/after demo near the top of the README.
- Publish honest limitations instead of claiming perfect generation or guaranteed savings.
- Add reproducible failure examples showing QA catching real defects.
- Respond to the first few Issues quickly and turn hard sheets into regression fixtures.
- Use small releases with clear notes instead of silently changing the skill contract.
- Add screenshots or short clips before adding more marketing copy.
