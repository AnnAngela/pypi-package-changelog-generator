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
│   └── pypi-package-changelog/
├── src/
│   └── pypi_package_changelog_generator/
└── tests/
```

关键目录说明：

- [src/pypi_package_changelog_generator](src/pypi_package_changelog_generator)：CLI 与分析逻辑实现
- [skills/pypi-package-changelog](skills/pypi-package-changelog)：OpenClaw Skill 本体
- [scripts/build_skill_bundle.py](scripts/build_skill_bundle.py)：构建可发布的 self-contained Skill bundle
- [.github/workflows/publish-clawhub.yml](.github/workflows/publish-clawhub.yml)：ClawHub 校验与发布流程

## 环境要求

- Python 3.14+
- Linux、macOS 或 Windows（CLI 本身为纯 Python）
- 如果要发布 Skill：
  - Node.js 24+
  - `clawhub` CLI
  - 有效的 `CLAWHUB_TOKEN`

## Ubuntu 24.04 使用 pyenv 安装 Python 3.14

Ubuntu 24.04 的系统 `python3` 默认指向 3.12，因此如果本机没有现成的 `python3.14`，推荐使用 `pyenv` 安装一个独立的 3.14 解释器，而不要替换系统 `/usr/bin/python3`。

### 0. 安装编译依赖

```bash
sudo apt update
sudo apt install make build-essential libssl-dev zlib1g-dev \
  libbz2-dev libreadline-dev libsqlite3-dev curl git \
  libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev
```

### 1. 安装 pyenv

```bash
curl -fsSL https://pyenv.run | bash
```

### 2. 配置 pyenv

```bash
echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc
echo '[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc
echo 'eval "$(pyenv init - bash)"' >> ~/.bashrc
if [[ -s ~/.profile ]]; then
  echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.profile
  echo '[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.profile
  echo 'eval "$(pyenv init - bash)"' >> ~/.profile
fi
if [[ -s ~/.bash_profile ]]; then
  echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bash_profile
  echo '[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bash_profile
  echo 'eval "$(pyenv init - bash)"' >> ~/.bash_profile
fi
source ~/.bashrc
```

如果你使用的是 zsh，请把上面的 `~/.bashrc` 改成 `~/.zshrc`。

### 3. 安装 Python 3.14 并绑定到当前仓库

```bash
pyenv install 3.14.4
cd /data/pypi-package-changelog-generator
pyenv local 3.14.4
python -V
```

执行完后，仓库根目录会生成 `.python-version`，此目录下的 `python` 将优先指向 `pyenv` 管理的 3.14.4。

## 创建 venv

推荐在仓库根目录使用本地虚拟环境：

如果仓库里已经有旧的 `.venv`，尤其是它曾经由 Python 3.12 创建过，请先停用并删除或备份旧目录，再重新创建。不要直接在一个旧 `.venv` 上原地覆盖创建新的虚拟环境。

```bash
deactivate 2>/dev/null || true
mv .venv ".venv.bak-$(date +%Y%m%d-%H%M%S)" 2>/dev/null || true
```

如果你已经按上文使用 `pyenv local 3.14.4`，直接运行下面这组命令即可：

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
```

如果你本机已经有系统级 `python3.14`，也可以继续使用显式解释器：

```bash
python3.14 -m venv .venv
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

如果你使用 pyenv：

```bash
cd /data/pypi-package-changelog-generator
pyenv local 3.14.4
rm -rf .venv
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
```

如果你使用系统级 `python3.14`：

```bash
rm -rf .venv
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
```

如果你切换了 Python 次版本，优先使用重建方式。

### 常见报错：`ensurepip` 非零退出

如果执行 `python -m venv .venv` 时看到类似下面的报错：

```text
Error: Command '[.../.venv/bin/python', '-m', 'ensurepip', '--upgrade', '--default-pip']' returned non-zero exit status 1.
```

通常说明当前 `.venv` 里混入了旧版本 Python 的残留文件，例如 `.venv/bin/python` 仍然指向旧的 3.12 解释器。

修复方式：

```bash
cd /data/pypi-package-changelog-generator
deactivate 2>/dev/null || true
pyenv local 3.14.4
python -V
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
```

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
pypi-package-changelog \
  --package requests \
  --version-range 'latest-1'
```

### 可选 GitHub Token

如果设置了 `GITHUB_TOKEN`，GitHub compare 路径会更稳定：

```bash
export GITHUB_TOKEN=ghp_xxx
pypi-package-changelog \
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
python scripts/build_skill_bundle.py --output /tmp/pypi-package-changelog-skill
```

构建结果会包含：

- Skill 文件本体
- 运行时 Python 源码
- `packaging` 依赖的 vendored 副本

这是为了保证发布后的 Skill 不依赖仓库外部源码，也不依赖运行时机器上预装的 editable 包。

## 验证 self-contained Bundle

可以用隔离模式验证 bundle 是否可独立运行：

```bash
python -S /tmp/pypi-package-changelog-skill/scripts/invoke.py --help
```

`-S` 会禁用 site-packages 自动加载，这样可以更早发现“只在本地开发环境能跑、发布后会挂”的问题。

## OpenClaw / ClawHub

Skill 源目录位于 [skills/pypi-package-changelog](skills/pypi-package-changelog)。

Skill 的执行入口是：

- [skills/pypi-package-changelog/SKILL.md](skills/pypi-package-changelog/SKILL.md)
- [skills/pypi-package-changelog/scripts/invoke.py](skills/pypi-package-changelog/scripts/invoke.py)

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
