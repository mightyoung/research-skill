# research-workflow

<!-- Modified 2026-10-01: local field-entry, evidence screening and safe acquisition extension. -->

基于 [skJack/research-workflow](https://github.com/skJack/research-workflow) 的本地改造，固定上游
`14c882df49a7991b9833f2ff416e4dfd38668827`，保留 Apache-2.0 [LICENSE](LICENSE)；来源及原文件 SHA-256 见 [UPSTREAM.json](UPSTREAM.json)。
上游数据/实验/评测模板保持原样。本版本增加领域入门与研究方向筛选，再进入原复现、实验、交接流程。
不会自动安装技能、配置账户、运行论文代码或写凭证。

领域发现与具体想法审查分开：先写一页field-judgment、解释路线演进与优先瓶颈，再生成不同实质贡献候选。决定性近邻优先精读关键正文，资源未知转成数据/标注探查而非预定机制；详见[field-discovery](references/field-discovery.md)。targeted_body记reading_scope，不冒充整篇通读。检查器仍不认证科研质量。

## 第二版：快速入门与可靠方向

当前本地交付还提供Claude Code兼容入口：同一SKILL.md与脚本核心，Claude用 `/research-workflow`，Codex用 `$research-workflow`。
跨cwd请明确skill root和研究project root，路径加引号；`init-project.sh <project> --claude-guide`可补建轻量CLAUDE.md，默认不生成、不覆盖已有文件。
宿主与工具缺失降级见 [hosts](references/hosts.md)。适配交付未自动安装到Claude，也未同步既有Codex副本；静态/本地验证不表示真实Claude加载已验证。

五种入口不变，优先交付 A核心/最新论文与阅读路线、B关键问题/方法/证据/趋势地图、C少量可行候选方向。新增契约服务这些产物，不把填日志当作研究。

检索覆盖与来源能力显式记录；未知总数不称穷尽，零命中/访问失败不证明创新。阅读深度与定位可靠度分开，原述/推断/假设分开；可选本地UTF-8摘录匹配与原始字节hash，结果不认证论断或页码。方向卡补关键矛盾、why-now、竞争解释、判别计划、条件失败与重开条件。交接重新核对输入产物hash及依赖。

新行显式 `schema_version:2`；旧行兼容并显示 legacy提示。`--strict-v2` 要求当前活跃快照迁移。人工追加完整新修订，未知不能自动补真；已迁移不可降版绕过。新初始化补建 searches/tensions/experiments/failures/handoffs 日志、tensions和研究流程评估模板。

```bash
python3 <skill>/scripts/check-research.py <project> --strict-v2
python3 <skill>/scripts/check-research.py <project> --strict-v2 --mark-review
python3 <skill>/scripts/check-research.py <skill>/examples/v2-case/discover --strict-v2
python3 <skill>/scripts/check-research.py <skill>/examples/v2-case/review --strict-v2
python3 <skill>/scripts/check-research.py <skill>/examples/v2-case/update --strict-v2
```

可读合成案例：`examples/v2-case/{discover,review,update}/REPORT.md`，原始包 `raw-materials.md`。全部材料虚构，展示进入领域到筛选、更新，**不是实际领域研究或实时查新**，判别实验没有执行。

仅新增小模块 `scripts/research_v2.py`，由 check-research 内部调用，不是下载器或商业搜索器。无账号、联网搜索自动化和额外依赖。生成与审查按需分开；等预算评估模板没有执行结果，不宣称提高研究质量。哈希只标识字节一致性，不是不可抵赖真伪证明。

## 本地使用与依赖

Python **3.10+** 标准库、bash；文件锁使用 POSIX `fcntl`（macOS/Linux）。无需 pip、curl、perl、数据库、向量库。
下载需可访问 arxiv.org；离线测试不访问网络。下载脚本不做 PDF 渲染或论文代码执行。
将 `<skill>` 替换为此目录绝对路径，直接引用本地 SKILL.md 即可，不必放到全局技能目录。

```bash
bash <skill>/scripts/init-project.sh /path/to/my-research
python3 <skill>/scripts/check-research.py /path/to/my-research
bash <skill>/scripts/fetch-paper.sh 2301.11305v1 detectgpt --project /path/to/my-research
```

五种路由：进入领域、梳理前沿、寻找方向、审查想法、增量更新；按需加载 references。
先填 research-brief，再分层覆盖综述/经典/强基线/近期/争议负结果，建证据地图，查最近似工作反证，
过硬性可行性关卡，通常保留约 3 个方向（可更少或零个），设计最小可证伪实验。
复现前允许候选假设，正式实验前核验关键强基线。
创新只是所查范围内的暂定判断，检索零命中/访问失败不得写成已证实创新。

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

## 证据与更新

格式、稳定 ID、完整行追加修订、外键、DOI/arXiv 版本关系见 [evidence schema](references/evidence-schema.md)。
摘要不能充全文；主张必须定位实际版本和页码/图表。发表状态与实际阅读深度必须记录。
同一 work_id 的多版只计一个独立工作。脚本可匹配显式 DOI/arXiv，标题别名/扩展论文关系仍由 Agent 核实。

```bash
python3 <skill>/scripts/check-research.py /path/to/my-research --mark-review
```

新增版本、撤稿、更正、关键证据更新后追加日志，再用上命令标记传递依赖。
有陈旧证据返回 **1**，即使标记成功；结构错误时不修改日志。
人工复核后追加新结论并重设明确依赖，不能自动 repin。保留旧版本需全文比较并写 `reviewed_against`；
不再使用的证据可带理由退役 `active:false`，退役机会须 rejected。历史保留，不再阻断没有活跃依赖的项目。

`ready` 强制 data/compute/time/baseline/ethics 全 pass、全文证据、最近似工作审查字段、最小实验和停止条件。
脚本只校验**结构、所声明状态和依赖新鲜度**；PASS 不证明内容真实、科学结论已证实、原创、搜索充分或预算真实。
Agent 负责查原文、经典与近期覆盖、语义相似、关卡依据、反证权重、趋势跨时间可比性和方向排名。

## 下载规则

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

## 当前边界

V6.2新增按需[关键论文精读](references/critical-reading.md)：候选形成后、最终新颖性/可行性判断前优先最强近邻、拟采用方法和反证边界；领域早期决定性理解缺口也可触发。每篇先写读后决策，分筛选、结构理解、关键机制与证据重建、必要验证，读到能作当前决定可停。机制→数据协议→固定commit代码链→图表/公平性/误差→结论范围影响保留/修改/撤销/暂停。基础较弱时按阻塞理解/实施前/周边分层，术语首用中文解释。没有代码、受限数据或论文/当前main配置差异不自动判论文无效/复现失败；unknown的影响须具体说明。

新项目或已有项目重跑init只补缺paper-reading.md，不覆盖笔记。复用现有paper/claim和reading_scope/version/needs_review，**不增schema、必填日志或依赖**。静态阅读、局部逻辑验证、作者权重评估、重训、独立实现/新数据复验分别记录；单demo不称论文已复现。外部执行仍须审查具体来源/代码/命令/环境/授权，本次精读流程不会自动执行。示例提示词：“精读决定我是否采用的这篇关键论文；先写决策和缺口，核机制、数据协议、固定版本实现及关键图表，明确保留/修改/撤销/暂停；未执行如实记，不运行论文代码。”仅入门则说明学习目标/预算，在结构理解足够时停止，不强制实施链。

125项既有回归保留，新增参考可达/初始化保护测试；实际新上下文六类边界回答与独立比较记录在交付工作区verification/v6.2。它们是局部材料样例，不是完整论文复验或新领域研究；格式测试不能认证行为改善。

V6 的领域发现先建立现象、过程、解释条件、已解与未知的问题链，再构造具有知识增量的候选。若候选只剩下载/标注检查，按需读 [问题构造](references/problem-construction.md)，把资源探查与科学判别分开，并共同设计验证系统及外推边界。最近似工作覆盖后允许一次有证据的修正；不强迫算法、候选数量或原创结论。对应指导进入新项目的一页判断、候选和 brainstorm 模板；已有项目文件仍不会被覆盖。
V6.1 在原路径按条件融入[工程与跨域思考](references/transfer-and-engineering.md)：brief偏好可选、领域图先行；有工程失效或明确迁移依据才加载；近邻查同义方法/已有迁移，实验比较强目标基线/直接移植/适配及成本，证据清楚后投稿匹配。仅入门时跳过这些分支、首次展开术语；阅读工件与作品发表状态分别核对。案例与方法是有限启发，不认证创新或分区。

多来源扩展提供 Crossref、DataCite、OpenAlex locations、Europe PMC、PMC 当前公开数据集、Zenodo、HAL、bioRxiv/medRxiv 的有界身份/版本解析，宿主插件结果导入及通用公开候选下载。
用 `python3 scripts/acquire-paper.py --help` 开始；完整命令、配置缺失状态、来源权限和实际验证边界见 [获取说明](references/acquisition.md)。
不调用退役 PMC OA 接口、Unpaywall 关键词搜索或需要 key 的 OpenAlex hosted content。
凭据不由 CLI 接收或存储。公开元数据/候选 URL 不等于全文；取得结构校验通过的正文不等于已读、身份已认证或可再分发。
登记先生成待审草稿，不自动改 JSONL；现有 schema_version=2 保持不变，新增可选来源材料/manifest hash 绑定可触发依赖复核。

MVP 不含数据库、向量库、调度监控或外部 API 账户。JSONL 写入仍由 Agent/人工完成；下载 manifest 不自动等于已阅读。
内容真伪和科学质量无法由格式校验认证。身份迁移和复杂 DOI 关联需人工处理；全项目校验是保守的。
不会自动跑复现代码，真正的复现/实验另需审查目标代码、环境和资源。
