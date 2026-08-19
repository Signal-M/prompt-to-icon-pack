# Prompt to Asset Pack

> 一句 Prompt 或一张 IP 参考图，生成整套风格一致、自动命名、透明背景、经过 QA 的视觉资产。

![Agent Skills](https://img.shields.io/badge/Agent-Skills-111111)
![Codex Plugin](https://img.shields.io/badge/Codex-Plugin-111111)
![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB)
![License MIT](https://img.shields.io/badge/License-MIT-2EA44F)

[English](README.md) · [安装](#安装) · [支持的资产](#不只是-icon) · [平台兼容](#agent-平台兼容)

**Prompt to Asset Pack** 是从 `Prompt to Icon Pack` 升级而来的批量视觉资产生产流水线。它可以根据自然语言或角色参考图生成 Icon、Emoji、表情包、头像、徽章和游戏物品：先建立风格锚点并规划多张 Sheet，再进行非网格拆分、背景透明化、外部语义命名、单批与跨批 QA，最后输出 PNG、WebP、可选 SVG、工程映射和 ZIP。

仓库名和 `$generate-icon-batch` 兼容入口会继续保留，避免旧提示词和安装方式失效。

## 实际效果

| 一次生成 | 自动拆分、透明化、命名和质检 |
| --- | --- |
| ![3x3 网球吉祥物资产表](examples/tennis-mini-program/generated-sheet.png) | ![透明资产联系表](examples/tennis-mini-program/contact-sheet.png) |

这个真实示例第一次拆分时发现扩音器右侧留白不足。系统没有直接输出 ZIP，而是通过 QA 拦截、局部扩大裁剪框并重新验证，最终只包装通过门禁的结果。

## 它解决什么问题

1. 单张生成容易出现配色、透视、材质和角色身份漂移。
2. 每个资产分别调用模型会增加成本、等待时间和审核工作。
3. 一张 Sheet 生成后仍需手动切图、抠图、命名、缩放和打包。
4. 四五十个资产不适合挤在一张大图里，需要跨 Sheet 的一致性机制。
5. “切出来了”不等于“可发布”，还可能有语义错误、重复、漏项、白色误删或角色变脸。

## 核心亮点

### 四五十个资产也能保持一致

大批量请求会共享一份不可变的 Style Contract 和参考锚点，再拆成多张完整布局：

- `quality`：每张最多 9 个，适合 3D 角色和表情包；45 个会拆成 5 张 3×3。
- `balanced`：每张最多 15 个，适合大多数 Icon 系统。
- `economy`：每张最多 25 个，只适合简单扁平资产。

系统会检查跨批次的角色身份、色板、主体比例、留白、线条或材质，以及是否有重复和漏项。失败时只重做问题批次。

### 未指定内容时自动使用预设

内置通用 UI 24/48、Emoji 反应、IP 表情、商店和运动主题。App 请求默认使用通用 UI；上传角色参考图则默认进入表情包模式，不会把所有模糊需求都武断地变成 Emoji。

### 不依赖严格网格

拆分器检测真实前景对象并聚类成阅读顺序，不会把 AI 生成图简单平均切成固定小格。

### 不误删内部白色

只移除与局部裁剪边界连通的亮色中性背景。眼白、衣服、帽子、网线、播放按钮和高光等内部白色仍保持不透明。

### 名称来自需求，而不是重新猜图

有序资产清单是唯一命名真值。生成图中禁止出现标签和文件名，也不会让 OCR 猜一个生成前已经知道的名称。

### QA 会诊断失败原因

- 生成、数量、语义、角色身份、重复或风格错误：重生成对应批次。
- 检测、裁切、分离细节或透明度错误：重新拆分或局部修正。
- 命名错误：修正外部映射。
- SVG 过于复杂或回渲染不一致：保留 PNG/WebP。

最终 ZIP 必须同时通过确定性 QA、视觉语义 QA 和全局跨批次 QA。

### SVG 不是简单描摹一切

扁平、线性、纯色 Icon 可以使用原生语义 SVG；颜色较少的位图可以选择 VTracer 描摹。SVG 会被清理主动内容、限制路径数量和文件体积，再回渲染成 PNG 与原图对比。3D、毛发、玻璃、柔和阴影和复杂渐变如果不适合矢量化，就诚实保留位图。

### 表情包文字不会再拼错

模型只负责生成无字角色。拆分后再用真实字体添加“收到”“谢谢”“冲鸭”等文字，既可靠，也能单独切换语言。

## 不只是 Icon

```yaml
asset_kind: icon | emoji | sticker | avatar | badge | item-sprite
```

仓库包含六个可组合 Skill：

- `generate-asset-pack`：通用资产规划、预设、风格锚点、多 Sheet、QA 和打包。
- `generate-sticker-pack`：Character Bible、反应清单、身份一致性和后置字幕。
- `split-icon-sheet`：非网格拆分、旧图 OCR、内部白色保护和裁切 QA。
- `vectorize-asset-pack`：原生/描摹 SVG、安全清理和回渲染 QA。
- `export-asset-pack`：多尺寸 PNG/WebP、雪碧图、CSS、TypeScript 和 ZIP。
- `generate-icon-batch`：兼容旧版 Icon 调用方式。

## 使用示例

```text
使用 $generate-asset-pack，为网球小程序生成 48 个产品 Icon。
采用统一的青柠绿色与黄色 3D 风格，balanced 密度，中文命名，
输出透明 PNG 和 WebP，跨批次 QA 全部通过后再打包。
```

```text
使用 $generate-sticker-pack 和我上传的小猫参考图。
生成默认 24 个反应表情，保持脸型、耳朵、围巾和配色一致，
拆分后添加可靠的中文文字，最后输出透明 ZIP。
```

## 安装

```bash
git clone https://github.com/m2290526022-boop/prompt-to-icon-pack.git
cd prompt-to-icon-pack

python3 scripts/install-platform.py codex
python3 scripts/install-platform.py claude-code
python3 scripts/install-platform.py qwen-code
python3 scripts/install-platform.py workbuddy
```

`./scripts/install.sh` 仍然是 Codex 的快捷安装命令。默认不会覆盖已有 Skill，只有显式添加 `--force` 才会替换。

生成千问办公可审查上传包：

```bash
python3 scripts/install-platform.py qwenwork
```

这一步只生成 ZIP，不会自动发布。详情见 [平台适配说明](docs/platforms.md)。

## Agent 平台兼容

- Codex：提供 `.codex-plugin/plugin.json` 和标准 Agent Skills。
- Claude Code：提供 `.claude-plugin/plugin.json` 和共享 `skills/`。
- Qwen Code：提供 `qwen-extension.json`。
- WorkBuddy：支持当前验证过的 `~/.workbuddy/skills` 目录，不同版本可能需要调整。
- 千问办公：可以生成上传包；是否能上传或公开发布取决于账号和企业权限。

生成新图仍要求目标 Agent 具备图片生成工具。没有图片生成能力时，规划、已有 Sheet 拆分、QA、矢量化和导出仍可使用。

## 输出

```text
final-assets/
├── assets/
├── asset-map.json
├── assets.ts
├── contact-sheet.png
├── qa-summary.json
└── asset-pack.zip

exported/
├── png/{64,128,256}/
├── webp/{64,128,256}/
├── svg/                    # 仅适合矢量化的资产
├── sprite/
├── assets.css
├── assets.ts
├── export-manifest.json
└── asset-export.zip
```

## 依赖与测试

```bash
python3 -m pip install -r requirements.txt
python3 -m pip install -r requirements-vector.txt  # 可选 SVG QA
./scripts/validate.sh
```

测试覆盖预设规划、45 个质量模式分批、48 个跨 Sheet 规划、表情文字渲染、PNG/WebP/雪碧图导出、SVG 安全清理、旧版兼容和多平台清单解析。

## 已知限制

- 图片生成仍具有随机性，偶尔需要定向重试。
- 风格锚点能提高一致性，但无法数学保证角色几何完全相同。
- 毛发、烟雾、玻璃、半透明材质和共享场景仍是抠图难点。
- 自动描摹 SVG 不等同于设计师手工制作的干净矢量源文件。
- 第三方平台规范会变化，正式提交商店前应重新核对官方要求。

如果它帮你省掉了一轮生成、切图、命名或 QA，欢迎点一个 Star，让更多开发者发现这个项目。

## License

[MIT](LICENSE)
