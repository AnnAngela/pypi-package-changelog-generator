# pypi-package-changelog-generator

一个用于分析 PyPI 包两个版本之间变化的工具与 OpenClaw Skill。

它会综合以下证据生成结构化结果：

- PyPI 元数据
- 源码归档差异
- GitHub compare 结果（如果能从 PyPI 元数据定位到公开 GitHub 仓库）
- 项目依赖与 Python 版本要求变化

仓库同时包含两部分内容：

- Python CLI：本地运行、测试和调试分析逻辑
- OpenClaw Skill：发布到 ClawHub 后供 OpenClaw 调用

## 功能概览

- 支持显式版本对比：`--from-version` + `--to-version`
- 支持版本范围解析：例如 `>=1.0,<2.0`、`latest-1`
- 优先使用 GitHub compare 获取提交、PR 和文件变化
- 无法使用 GitHub compare 时回退到 PyPI sdist 归档比较
- 提取依赖变更、元数据变化和潜在破坏性升级信号
- 输出稳定的 JSON 结构，适合被 Skill 或其他自动化流程消费

## 仓库结构

```text
.
├── .github/workflows/publish-clawhub.yml
├── pyproject.toml
├── scripts/
│   └── build_skill_bundle.py
├── skills/
│   └── pypi-package-changelog-generator/
├── src/
│   └── pypi_package_changelog_generator/
└── tests/
```

关键目录说明：

- [src/pypi_package_changelog_generator](src/pypi_package_changelog_generator)：CLI 与分析逻辑实现
- [skills/pypi-package-changelog-generator](skills/pypi-package-changelog-generator)：OpenClaw Skill 本体
- [scripts/build_skill_bundle.py](scripts/build_skill_bundle.py)：构建可发布的 self-contained Skill bundle
- [.github/workflows/publish-clawhub.yml](.github/workflows/publish-clawhub.yml)：ClawHub 校验与发布流程

## 环境要求

- Python 3.12+ & python3.12-venv 包（Debian/Ubuntu）
- Linux、macOS 或 Windows（CLI 本身为纯 Python）
- 如果要发布 Skill：
  - Node.js 24+
  - `clawhub` CLI
  - 有效的 `CLAWHUB_TOKEN`

## 创建 venv

推荐在仓库根目录使用本地虚拟环境：

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
```

说明：

- `-e` 表示 editable install，修改源码后无需重新安装整个包
- `.[dev]` 会安装测试所需依赖，包括 `pytest-cov`
- 这个仓库默认 pytest 配置依赖 `pytest-cov`，所以如果没有安装 `dev` extra，直接运行 `pytest` 会失败

## 更新 venv

依赖变更后，通常有两种更新方式。

### 方式一：原地更新

适合依赖变更较小的情况：

```bash
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e '.[dev]' --upgrade
```

### 方式二：重建 venv

适合 Python 版本变更、依赖冲突或你想得到一个干净环境的情况：

```bash
rm -rf .venv
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
```

如果你切换了 Python 次版本，优先使用重建方式。

## 本地运行 CLI

安装完成后，可以直接运行模块或入口脚本。

### 方式一：通过模块运行

```bash
python -m pypi_package_changelog_generator.cli \
  --package requests \
  --from-version 2.31.0 \
  --to-version 2.32.0
```

### 方式二：通过 console script 运行

```bash
pypi-package-changelog-generator \
  --package requests \
  --version-range 'latest-1'
```

### 可选 GitHub Token

如果设置了 `GITHUB_TOKEN`，GitHub compare 路径会更稳定：

```bash
export GITHUB_TOKEN=ghp_xxx
pypi-package-changelog-generator \
  --package httpx \
  --from-version 0.27.0 \
  --to-version 0.28.0
```

## CLI 参数

主要参数：

- `--package`：PyPI 包名，必填
- `--from-version`：起始版本
- `--to-version`：目标版本
- `--version-range`：版本范围表达式，例如 `>=1.0,<2.0` 或 `latest-1`
- `--github-token`：可选 GitHub Token，默认也会读取环境变量 `GITHUB_TOKEN`
- `--json-indent`：JSON 输出缩进，默认 `2`

约束：

- 不能同时传 `--version-range` 与 `--from-version/--to-version`
- 必须在“显式版本对”与“版本范围”之间二选一

## 输出说明

CLI 输出为 JSON，包含以下高层字段：

- `package`
- `resolved_versions`
- `mode`
- `source`
- `commits`
- `reviews`
- `file_changes`
- `metadata_changes`
- `dependency_changes`
- `breaking_signals`
- `warnings`
- `errors`

当 GitHub compare 不可用时，`mode` 可能回退为 `archive`；当两种证据都无法提供有效结果时，`mode` 会是 `error`。

## 运行测试

在已安装 `dev` extra 的前提下：

```bash
pytest
```

如果你当前环境里没有 `pytest-cov`，但仍想临时跑测试，可以覆盖默认 addopts：

```bash
pytest --override-ini addopts=''
```

## 构建可发布 Skill Bundle

这个仓库发布到 ClawHub 的不是原始 `skills/` 目录，而是一个 self-contained bundle。

构建命令：

```bash
python scripts/build_skill_bundle.py --output /tmp/pypi-package-changelog-generator
```

构建结果会包含：

- Skill 文件本体
- 运行时 Python 源码
- `packaging` 依赖的 vendored 副本

这是为了保证发布后的 Skill 不依赖仓库外部源码，也不依赖运行时机器上预装的 editable 包。

## 验证 self-contained Bundle

可以用隔离模式验证 bundle 是否可独立运行：

```bash
python -S /tmp/pypi-package-changelog-generator/scripts/invoke.py --help
```

`-S` 会禁用 site-packages 自动加载，这样可以更早发现“只在本地开发环境能跑、发布后会挂”的问题。

## OpenClaw / ClawHub

Skill 源目录位于 [skills/pypi-package-changelog-generator](skills/pypi-package-changelog-generator)。

Skill 的执行入口是：

- [skills/pypi-package-changelog-generator/SKILL.md](skills/pypi-package-changelog-generator/SKILL.md)
- [skills/pypi-package-changelog-generator/scripts/invoke.py](skills/pypi-package-changelog-generator/scripts/invoke.py)

包装脚本会优先从发布 bundle 自身加载 `vendor` 和 `src`，因此发布后的 Skill 可以在隔离环境中运行。

## 发布到 ClawHub

GitHub Actions workflow 位于 [.github/workflows/publish-clawhub.yml](.github/workflows/publish-clawhub.yml)。

发布前会执行：

- 安装依赖
- 运行测试
- 检查 CLI help
- 构建 self-contained skill bundle
- 用 `python -S` 验证 bundle 内的 `invoke.py`

触发方式：

- `workflow_dispatch`
- 推送 `v*` tag

发布时需要仓库 Secret：

- `CLAWHUB_TOKEN`

## 常见问题

### 1. `pytest` 提示 `unrecognized arguments: --cov=...`

原因通常是当前 venv 没有安装 `pytest-cov`。

修复：

```bash
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

### 2. 本地能跑，bundle 里不能跑

先用隔离模式检查：

```bash
python -S /path/to/bundle/scripts/invoke.py --help
```

如果这里失败，说明运行仍然依赖 site-packages 或仓库外部路径。

### 3. GitHub compare 没有返回结果

常见原因：

- PyPI 元数据里没有可识别的 GitHub 仓库地址
- GitHub tag 与版本号不匹配
- 命中 API 限流

这时程序会尽量回退到 sdist 归档比较。

## 许可证

本仓库使用 MIT License，见 [LICENSE](LICENSE)。
