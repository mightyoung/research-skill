# research-workflow

<!-- Modified 2026-10-01: local field-entry, evidence screening and safe acquisition extension. -->

基于 [skJack/research-workflow](https://github.com/skJack/research-workflow) 的本地改造，固定上游
`14c882df49a7991b9833f2ff416e4dfd38668827`，保留 Apache-2.0 [LICENSE](LICENSE)；来源及原文件 SHA-256 见 [UPSTREAM.json](UPSTREAM.json)。
上游数据/实验/评测模板保持原样。本版本增加领域入门与研究方向筛选，再进入原复现、实验、交接流程。
不会自动安装技能、配置账户、运行论文代码或写凭证。

## 它做什么

五种路由：进入领域、梳理前沿、寻找方向、审查想法、增量更新；按需加载 references。
先填 research-brief，再分层覆盖综述/经典/强基线/近期/争议负结果，建证据地图，查最近似工作反证，
过硬性可行性关卡，通常保留约 3 个方向（可更少或零个），设计最小可证伪实验。
复现前允许候选假设，正式实验前核验关键强基线。
创新只是所查范围内的暂定判断，检索零命中/访问失败不得写成已证实创新。

优先交付三份可读产物：A 核心/最新论文与阅读路线，B 关键问题/方法/证据/趋势地图，C 少量可行候选方向。领域发现（discover）与具体想法审查（review）分开。Claude Code 用 `/research-workflow`，Codex 用 `$research-workflow`，共用同一 SKILL.md 与脚本；宿主差异见 [hosts](references/hosts.md)。

## 快速开始

Python **3.10+** 标准库、bash；文件锁使用 POSIX `fcntl`（macOS/Linux）。无需 pip、curl、perl、数据库、向量库。
下载需可访问 arxiv.org；离线测试不访问网络。下载脚本不做 PDF 渲染或论文代码执行。
将 `<skill>` 替换为此目录绝对路径，直接引用本地 SKILL.md 即可，不必放到全局技能目录。

```bash
bash <skill>/scripts/init-project.sh /path/to/my-research
python3 <skill>/scripts/check-research.py /path/to/my-research
bash <skill>/scripts/fetch-paper.sh 2301.11305v1 detectgpt --project /path/to/my-research
```

跨cwd请明确skill root和研究project root，路径加引号；`init-project.sh <project> --claude-guide`可补建轻量CLAUDE.md，默认不生成、不覆盖已有文件。

## 项目结构

```text
AGENTS.md                 总纲，每窗口先读
handoff.md                交接，每窗口结束更新
research-brief.md          领域/目标/截止/预算/未知
landscape.md               分层阅读/问题/方法/假设/证据/瓶颈地图
opportunities.md           最近似工作/关卡/排名/淘汰历史/最小实验
paper-reading.md          按需精读决策笔记，允许引用已有证据、不强制填满
brainstorm.md              候选假设、对话、复现观察和反证
research/
  sources.jsonl papers.jsonl claims.jsonl opportunities.jsonl
related_work/<slug>/versions/vN/
  paper.pdf manifest.json
  source/download.bin     原始下载包（源码可得时）
  source/raw/             未清洗材料
  source/clean/           阅读辅助，不含 .orig 和旧稿目录
复现/                     基线核验与复现报告
experiment/results.md     每版实验，包括失败
experiment/evaluation.md  固定评测
DataSet/ + dataset.md      数据与处理说明
```

初始化用 exclusive creation 补缺，不覆盖任何现有文件，不合并 `.gitignore`。
现有 ignore 会明确提示人工复核：在任何 `git add` 前加入 `related_work/`、`DataSet/`、checkpoints 等排除；
本脚本不执行 git 操作，新项目默认排除文献、数据和大模型文件。拒绝指向外部的项目内目录 symlink。

V2 项目另有 `research/searches.jsonl tensions.jsonl experiments.jsonl failures.jsonl handoffs.jsonl`。

## 证据、追溯与审查

格式、稳定 ID、完整行追加修订、外键、DOI/arXiv 版本关系见 [evidence schema](references/evidence-schema.md)。
摘要不能充全文；主张必须定位实际版本和页码/图表。发表状态与实际阅读深度必须记录。
同一 work_id 的多版只计一个独立工作。脚本可匹配显式 DOI/arXiv，标题别名/扩展论文关系仍由 Agent 核实。

```bash
python3 <skill>/scripts/check-research.py /path/to/my-research --strict-v2
python3 <skill>/scripts/check-research.py /path/to/my-research --mark-review
```

新增版本、撤稿、更正、关键证据更新后追加日志，再用上命令标记传递依赖。
有陈旧证据返回 **1**，即使标记成功；结构错误时不修改日志。
人工复核后追加新结论并重设明确依赖，不能自动 repin。保留旧版本需全文比较并写 `reviewed_against`；
不再使用的证据可带理由退役 `active:false`，退役机会须 rejected。历史保留，不再阻断没有活跃依赖的项目。

`ready` 强制 data/compute/time/baseline/ethics 全 pass、全文证据、最近似工作审查字段、最小实验和停止条件。

- **交付物追溯**：项目根 `*.md` 与 `experiment/*.md` 用 `[kind/id@rev]` 引用日志；引用不存在或陈旧即 FAIL，未引用的小数/百分比提示 untraced number（`scripts/research_trace.py`）。
- **实验溯源**：已执行实验写 `actual.provenance`（代码 commit、命令、环境与输出 hash 绑定），输出文件改变则该实验待复核；`--strict-v2` 对 completed 实验必需。
- **批准**：已执行实验须引用带人工 `approval` 的计划，超预算另需 `overrun_approval`；缺失提示，`--strict-v2` 报错。
- **审查**：固定时机与清单见 [reviewer](references/reviewer.md)。
- 新行显式 `schema_version:2`；旧行兼容并提示 legacy，`--strict-v2` 要求当前活跃快照已迁移。字段详见 [evidence schema](references/evidence-schema.md)。

## 论文获取

必须传 `vN`，不自动解析 latest。PDF 与源码请求使用完全相同固定 ID。
HTTP 状态、长度、媒体类型、PDF 首尾标记校验；最多 3 次有界重试（30 秒 socket 超时），请求间礼貌间隔。
source 404/410 或 e-print 返回 PDF 时明确 `PDF-only`；其他错误中止，不发布不完整资料。
下载/解包/清洗全在临时目录，校验通过才以同文件系统 rename 发布不可变版本；重复抓取验证 hash 后直接复用。
缓存变坏报错，不静默覆盖。不同版本分目录，清洗绝不从旧 `.orig` 恢复正文。

下载体上限 32 MiB、gzip 展开总上限 128 MiB、单文件 32 MiB、最多 2000 项、路径最多 20 层。
仅支持原始 tar、gzip tar、gzip/plain TeX；拒绝 traversal、绝对/Windows 路径、链接、设备、重复文件和超限包。
不调用 tar 解包命令，不编译 LaTeX，不执行材料中的任何命令。
清洗只为阅读辅助：启发式剥行注释、排除已知旧稿目录，复杂 TeX/verbatim 可能误删，关键引用回看 PDF/raw。
PDF 验证是轻量字节/HTTP 校验，不是完整 PDF 解析器；杀进程/断电可能留下隐藏 stage，下次不会复用，旧版本不被覆盖。

多来源（Crossref、DataCite、OpenAlex、Europe PMC、Zenodo、HAL、bioRxiv/medRxiv 等）身份/版本解析与公开候选下载：`python3 <skill>/scripts/acquire-paper.py --help`，完整说明见 [acquisition](references/acquisition.md)。凭据不由 CLI 接收或存储；登记只生成待审草稿，不自动改 JSONL。

## 示例

```bash
python3 <skill>/scripts/check-research.py <skill>/examples/v2-case/discover --strict-v2
python3 <skill>/scripts/check-research.py <skill>/examples/v2-case/review --strict-v2
python3 <skill>/scripts/check-research.py <skill>/examples/v2-case/update --strict-v2
```

可读合成案例：`examples/v2-case/{discover,review,update}/REPORT.md`，原始包 `raw-materials.md`。全部材料虚构，展示进入领域到筛选、更新，**不是实际领域研究或实时查新**，判别实验没有执行。

## 验证

```bash
cd <skill>
python3 -m unittest discover -s tests -v
python3 -m py_compile scripts/*.py tests/*.py
bash -n scripts/init-project.sh scripts/fetch-paper.sh
python3 scripts/check-research.py examples/demo-project
```

测试使用自产固定响应、合成归档和临时项目；无实时论文批抓，无第三方代码执行。
`examples/demo-project` 是**合成结构示例**，不代表真实研究或已读真实论文。
测试与独立行为验证的实际记录见工作区 `DELIVERY.md`、`verification/`。

## 能力边界

- 脚本只校验**结构、所声明状态、可选本地字节/摘录绑定和依赖新鲜度**。PASS 不证明内容真实、科学结论成立、原创、检索充分或预算真实；查原文、覆盖、语义相似、关卡依据、反证权重、趋势跨时间可比性和排名由 Agent 与人负责；全项目校验偏保守。
- 创新只是所查范围内的暂定判断；检索零命中或访问失败不证明创新。
- hash 只标识字节一致性，不是真伪证明；摘录匹配不认证页码或论断；下载 manifest 与取得的全文都不等于已阅读。
- 不自动安装技能、配置账户、运行论文代码、执行材料中的命令或写凭证；真正的复现/实验另需审查代码、环境、资源与授权。
- MVP 不含数据库、向量库、调度监控或外部 API 账户；JSONL 由 Agent/人工写入；身份迁移和复杂 DOI 关联需人工处理。
- 示例与评估模板都是合成/预留材料，不代表真实领域研究，也不宣称提高研究质量。Claude 适配未自动安装，静态验证不等于真实宿主加载已验证。

版本历史与各版验证说明见 [docs/CHANGELOG.md](docs/CHANGELOG.md)。
