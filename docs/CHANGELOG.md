# 版本历史

README 只保留当前用法；各版本的改动说明与验证记录按原文移到这里。

## 未发布：我们的主张与结果回流

起因：claims 必须挂在论文固定版本下，研究者自己准备论证的主张没有记录位置；"结论 → 支持它的运行 → 计划 → 论文"接不上，实验结果回来后也没有改判断的路由。

新增 V2 日志 `assertions`：不挂论文，`assertion_state` 为 untested/supported/refuted/inconclusive/withdrawn，证据带 `role`（supports/refutes/context）。校验器只检查状态与所引证据一致：role 不得与运行结果矛盾，supported/refuted 需具辨别力的完成运行（supported 也可用全文论文原述），inconclusive 需结果为 inconclusive 的已执行运行或冲突的决定性证据（冲突时不得标 supported/refuted），withdrawn 需理由，untested 不得带有足以定状态的支持或反驳证据；证据变化沿依赖传递待复核；主张以不固定修订的 `opportunity_id` 关联方向，方向用 `assertion_review:[{id,rev}]` 确认据以决定的主张修订（不进依赖图），曾关联过的方向未确认主张最新修订、确认过的主张已更新（含移走或解除关联）或主张待复核（含继承，传给关联过或确认过它的每个方向）时，方向在同一次校验中进入待复核，固定依赖与反向关联合并成环则报错；计划内置的方向固定引用不再向下传递待复核（显式 depends_on 照常）（此前任何方向修订都会让已执行的运行和主张失效，回流第 3 步因此无法收敛）；交付物可引用 `[assertions/id@rev]`。新增 references/result-feedback.md 与 SKILL.md 路由"实验结果回来"；results 与 handoff 模板各加一栏。旧项目缺该日志不报错；新初始化建空文件。

## 未发布：未读近邻门槛

起因：v6.6 不点名对照运行里，唯一 continue 的候选列出了三篇已读正文的近邻、通过了近邻正文门槛，但最可能覆盖它的工作（2025 视频入库配置论文）只以"未读"文字写在 `critical_unknown` 和 `change_decision_if`，没有登记为论文，门槛被绕过。

`critical_unknown` 条目可写成 `{paper:{id,rev},gap}`，钉住的论文参与外键与复核传播；continue/revise/ready 的当前快照中这些论文须读到正文，否则报错。文字条目或 `change_decision_if` 承认某篇文献未读时默认提示、`--strict-v2` 报错：未读字样必须紧挨着文献词（英文 `unread … paper` 或 `not/n't … read … paper` 相隔不超过 3 个词，`paper … was/has not read` 文献词与助动词之间不超过 2 个词；中文"专利正文未读""未读的论文"这类最多隔 1 个字），这样研究对象本身就是"未读消息"之类的领域用语不会被误判。文字检查是启发式，只能拦下诚实的写法，挡不住刻意改写，也会漏掉只带"方法"等通用词的写法（如"Chameleon 未读的在线适应方法"）和更远距离的表述；关键词规则的边角误判/漏判记为已知局限，不再逐条追加规则；它的作用是把结构化登记变成最省力的路径。park/abandon 不受限，只检查当前有效快照。153 项离线测试通过，三个 examples/v2-case 在 `--strict-v2` 下通过。

## V6.6 发现产出与近邻正文门槛

起因：human-count 一次 discover 运行通过了 `--strict-v2`，但 19 次检索里多数是按名字核对已知论文，C 只有 2 个元问题候选、全部停放、五关卡全 unknown，正文大半是免责与模板标签。结构合规成了低产出的最省力路径。

先生成后筛选（#10）：field-discovery 要求选题前先列 5–8 个原始想法的候选池（至少 3 种贡献类型，仅 discover；review 只审用户那一条主张）；全部停放合法，但每项要写可执行化路径和一个可立即动手的构造动作。检索区分 known_item / exploratory / snowball（searches 可选 `intent`），默认至少 5 次探索检索、从 ≥2 篇核心论文做引用追溯；预算未用完而关键子问题未解决时继续检索；核心近邻读到正文后再精读专利、产品页等外围材料。check-research 新增 `discovery yield` 提示（缺 intent、探索检索不足、无 snowball、超过一半论文只读摘要），只提示不判失败。

可读与通用（#10）：opportunities 模板改为"候选池 + 问句小节"，handoff 与 brainstorm 的斜杠标签清单压成问句，并明确不把标签抄进正文；reviewer 新增产出层清单。数据适配增加"需构造测量"一类（模拟用户、小规模试标、受控合成材料，例如交互式分割的点击次数）。problem-construction 去掉装配研究专属的 trial/triplet 与错误接受分母细节，保留通用的统计单位与弃权分母规则。

近邻正文门槛（#12）：opportunities 新增 `decisive_neighbors`（固定修订的论文引用，参与外键与复核传播）。decision=continue/revise 或 ready 必须列出，且所列论文须读到正文（targeted_body/full_text），否则报错；缺字段在默认模式只提示、`--strict-v2` 报错。只检查当前有效快照，历史修订可通过追加正文阅读与新修订修复。park/abandon 不受限。examples 的 o1 已补该字段。

对照运行（grok-4.7 xhigh，human-count，每组一次）：同一提示词下换用新版 skill，候选池从无到 7 条，候选从全部停放变为继续/修订/淘汰各有决定，照抄模板标签从 28 处降到 1 处；再去掉提示词里点名的论文，找到 6 篇本地文献表之外的工作（旧版为 0 篇论文）。只读摘要的论文仍占 45%–50%，这是增加近邻正文门槛的原因。点击次数迁移来自 skill 自身的例子，不算作发现；单次运行有随机性，只说明方向。

`intent` 与 `decisive_neighbors` 都是可选字段，无新必填日志或依赖；老项目里 continue/revise 的机会在 `--strict-v2` 下需要补列近邻。152 项离线测试通过，三个 examples/v2-case 在 `--strict-v2` 下通过；结构校验不认证研究质量。

## V6.5 查询分析与委派合同

查询分析与委派合同（#6）：借鉴 Claude Research 的查询分析：research-brief 增加问题形态（straightforward/breadth/depth）、子问题拆分、术语变体、投入档位、饱和停止与先宽后窄的检索；searches.jsonl 可选 `subq` 标签（非空字符串）。确需委派时，每个子任务写委派合同（目标/子问题、检索层、来源范围、排除项、写入日志、预算），子任务只交证据与缺口，判断由主流程汇总。

结构整理（#7）：check-research 的 validate 按职责拆分为辅助函数，行为不变；SKILL.md 与 README 重排，版本历史移到本文件。

规则补回（#8）：重排时遗漏的“每条新写入记录（含向旧项目增量追加的新 ID）显式 `schema_version: 2`”补回 SKILL.md；默认模式把缺省版本当 V1 只提示放行，会绕过 V2 契约。

无新必填日志或依赖；`subq` 为可选字段。150 项离线测试通过，三个 examples/v2-case 在 `--strict-v2` 下通过；结构校验不认证研究质量。

## V6.4 定向自查

V6.4定向自查短补：经典任务定义需正文定位，缺失降低严格入门验收；装配trial统计单位与triplet条件切片分开；真值缺失、负预测拒绝及弃权覆盖分别计量。有界运行完成不等于严格验收通过；这些Agent自查不由结构脚本自动认证，不改变schema或要求新增日志。

## P0/P1：交付物追溯、实验溯源、审查与批准

交付物追溯：项目根 `*.md` 与 `experiment/*.md` 用 `[kind/id@rev]` 引用日志，引用不存在或陈旧即 FAIL，未引用的小数/百分比提示 untraced number；已执行实验可写 `actual.provenance`（代码 commit、命令、环境与输出 hash 绑定），`--strict-v2` 对 completed 实验必需。实现见 `scripts/research_trace.py`。
审查与批准：固定时机与清单见 [reviewer](../references/reviewer.md)；已执行实验须引用带人工 `approval` 的计划，超预算另需 `overrun_approval`（缺失提示，`--strict-v2` 报错）。

## V6.3 可执行探查

V6.3基于真实装配研究的有界复查，在既有问题构造与候选卡补充可执行变量/一步更新/配对行为例，以及能改变去留的关键条件小核查。无新schema、依赖或自动科学认证；未取得视频/目标真值保持candidate，标注一致性探查不算科学实测。提示词：“先说明候选怎样逐步判断，核最强近邻已有能力，再用公开材料检查关键条件是否出现；不能测目标就停止或收窄，不强迫留3个方向。”同材料前后交付和真实访问边界在工作区verification/v6.3，研究质量改善不是离线测试通过即可证明。

## V6.2 关键论文精读

V6.2新增按需[关键论文精读](../references/critical-reading.md)：候选形成后、最终新颖性/可行性判断前优先最强近邻、拟采用方法和反证边界；领域早期决定性理解缺口也可触发。每篇先写读后决策，分筛选、结构理解、关键机制与证据重建、必要验证，读到能作当前决定可停。机制→数据协议→固定commit代码链→图表/公平性/误差→结论范围影响保留/修改/撤销/暂停。基础较弱时按阻塞理解/实施前/周边分层，术语首用中文解释。没有代码、受限数据或论文/当前main配置差异不自动判论文无效/复现失败；unknown的影响须具体说明。

新项目或已有项目重跑init只补缺paper-reading.md，不覆盖笔记。复用现有paper/claim和reading_scope/version/needs_review，**不增schema、必填日志或依赖**。静态阅读、局部逻辑验证、作者权重评估、重训、独立实现/新数据复验分别记录；单demo不称论文已复现。外部执行仍须审查具体来源/代码/命令/环境/授权，本次精读流程不会自动执行。示例提示词：“精读决定我是否采用的这篇关键论文；先写决策和缺口，核机制、数据协议、固定版本实现及关键图表，明确保留/修改/撤销/暂停；未执行如实记，不运行论文代码。”仅入门则说明学习目标/预算，在结构理解足够时停止，不强制实施链。

125项既有回归保留，新增参考可达/初始化保护测试；实际新上下文六类边界回答与独立比较记录在交付工作区verification/v6.2。它们是局部材料样例，不是完整论文复验或新领域研究；格式测试不能认证行为改善。

## V6 / V6.1 领域发现、问题构造、工程与跨域

领域发现与具体想法审查分开：先写一页field-judgment、解释路线演进与优先瓶颈，再生成不同实质贡献候选。决定性近邻优先精读关键正文，资源未知转成数据/标注探查而非预定机制；详见[field-discovery](../references/field-discovery.md)。targeted_body记reading_scope，不冒充整篇通读。检查器仍不认证科研质量。

V6 的领域发现先建立现象、过程、解释条件、已解与未知的问题链，再构造具有知识增量的候选。若候选只剩下载/标注检查，按需读 [问题构造](../references/problem-construction.md)，把资源探查与科学判别分开，并共同设计验证系统及外推边界。最近似工作覆盖后允许一次有证据的修正；不强迫算法、候选数量或原创结论。对应指导进入新项目的一页判断、候选和 brainstorm 模板；已有项目文件仍不会被覆盖。
V6.1 在原路径按条件融入[工程与跨域思考](../references/transfer-and-engineering.md)：brief偏好可选、领域图先行；有工程失效或明确迁移依据才加载；近邻查同义方法/已有迁移，实验比较强目标基线/直接移植/适配及成本，证据清楚后投稿匹配。仅入门时跳过这些分支、首次展开术语；阅读工件与作品发表状态分别核对。案例与方法是有限启发，不认证创新或分区。

## 多来源获取

多来源扩展提供 Crossref、DataCite、OpenAlex locations、Europe PMC、PMC 当前公开数据集、Zenodo、HAL、bioRxiv/medRxiv 的有界身份/版本解析，宿主插件结果导入及通用公开候选下载。
用 `python3 scripts/acquire-paper.py --help` 开始；完整命令、配置缺失状态、来源权限和实际验证边界见 [获取说明](../references/acquisition.md)。
不调用退役 PMC OA 接口、Unpaywall 关键词搜索或需要 key 的 OpenAlex hosted content。
凭据不由 CLI 接收或存储。公开元数据/候选 URL 不等于全文；取得结构校验通过的正文不等于已读、身份已认证或可再分发。
登记先生成待审草稿，不自动改 JSONL；现有 schema_version=2 保持不变，新增可选来源材料/manifest hash 绑定可触发依赖复核。

## 第二版：快速入门与可靠方向

当前本地交付还提供Claude Code兼容入口：同一SKILL.md与脚本核心，Claude用 `/research-workflow`，Codex用 `$research-workflow`。
跨cwd请明确skill root和研究project root，路径加引号；`init-project.sh <project> --claude-guide`可补建轻量CLAUDE.md，默认不生成、不覆盖已有文件。
宿主与工具缺失降级见 [hosts](../references/hosts.md)。适配交付未自动安装到Claude，也未同步既有Codex副本；静态/本地验证不表示真实Claude加载已验证。

五种入口不变，优先交付 A核心/最新论文与阅读路线、B关键问题/方法/证据/趋势地图、C少量可行候选方向。新增契约服务这些产物，不把填日志当作研究。

检索覆盖与来源能力显式记录；未知总数不称穷尽，零命中/访问失败不证明创新。阅读深度与定位可靠度分开，原述/推断/假设分开；可选本地UTF-8摘录匹配与原始字节hash，结果不认证论断或页码。方向卡补关键矛盾、why-now、竞争解释、判别计划、条件失败与重开条件。交接重新核对输入产物hash及依赖。

新行显式 `schema_version:2`；旧行兼容并显示 legacy提示。`--strict-v2` 要求当前活跃快照迁移。人工追加完整新修订，未知不能自动补真；已迁移不可降版绕过。新初始化补建 searches/tensions/experiments/failures/handoffs 日志、tensions和研究流程评估模板。

仅新增小模块 `scripts/research_v2.py`，由 check-research 内部调用，不是下载器或商业搜索器。无账号、联网搜索自动化和额外依赖。生成与审查按需分开；等预算评估模板没有执行结果，不宣称提高研究质量。哈希只标识字节一致性，不是不可抵赖真伪证明。
