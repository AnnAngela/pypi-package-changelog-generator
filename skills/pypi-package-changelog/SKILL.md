---
name: pypi-package-changelog
description: 分析 PyPI 包在不同版本之间的变动，并生成结构化的变更日志证据。适用于用户需要查看升级说明、版本差异、依赖变更或破坏性变更分析的场景。
metadata: {"openclaw":{"homepage":"https://github.com/AnnAngela/pypi-package-changelog-generator","primaryEnv":"GITHUB_TOKEN","requires":{"bins":["python3"]}}}
user-invocable: true
---

# PyPI 包变更日志

当用户需要查看某个 PyPI 包两个版本之间的变更日志或升级摘要时，使用这个技能。

## 必要输入

- 包名。
- 显式版本对，或一个版本范围。

如果用户没有提供包名，或者既没有提供版本范围也没有同时提供起止版本，在执行前先补充询问。

## 可选输入

- GitHub 令牌，可由 OpenClaw 通过 `skills.entries.pypi-package-changelog.apiKey` 或 `skills.entries.pypi-package-changelog.env` 注入为 `GITHUB_TOKEN`。

## 执行步骤

1. 确认包名和版本范围。
2. 运行 `{baseDir}/scripts/invoke.py`，传入 `--package`，以及 `--version-range` 或同时传入 `--from-version` 和 `--to-version`。
3. 如果用户提供了 GitHub 令牌，让包装脚本从 `GITHUB_TOKEN` 读取，不要在聊天响应中回显令牌内容。
4. 读取 JSON 结果，并按以下固定章节归类结论：
   - `[新功能]`
   - `[修复]`
   - `[破坏性变更]`
   - `[依赖调整]`
5. 如果结果中报告了截断、压缩包回退或证据较弱，需要明确说明。

## 输出规则

- 所有结论都必须基于 JSON 证据。
- 优先使用简洁的 Markdown 列表。
- 如果某个分类没有结论，就省略该分类。
- 如果包解析或版本解析失败，概括错误原因，并只追问最小缺失输入。

## References

- JSON 输出结构：[output-schema](./references/output-schema.md)
- 失败处理说明：[failure-modes](./references/failure-modes.md)
- OpenClaw 配置说明：[openclaw-config](./references/openclaw-config.md)
