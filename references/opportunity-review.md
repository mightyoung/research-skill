# 方向筛选与想法审查

模式review围绕用户明确主张；模式discover必须先有field-judgment与地图，先列候选池再筛选出不同实质贡献（算法、数据/标注、测量评测、实证边界、系统观测或跨域迁移均可），见[field-discovery](field-discovery.md)。决定性近邻优先正文定向阅读，摘要不足改变受影响结论；最强替代解释、数据适配分类和具体首个区分动作不得只写proposed mechanism。

## 最近似工作反证

对每个候选写可被已有工作覆盖的精确主张：任务、方法、假设、评价、资源、贡献粒度。
主动搜索主张的同义表达、关键组件组合、同设定强基线、消融、失败结果；沿最近似工作前后向引用。
工程/跨域候选同时查目标领域的同义方法、已有直接移植和适配先例；名称不同不意味着没有先例。按需用[transfer and engineering](transfer-and-engineering.md)比较供体条件与目标冲突，审查知识贡献、非平凡适配和成本，而非把组合交付当创新。
记录查询/日期、最相似工作的 work_id、实际版本、claim 定位和差异表，不只罗列标题。
最终判决/关卡前，如决定性主张仍未追通正文机制、数据协议或拟用实现，按需读[关键精读](critical-reading.md)。每篇先写它将怎样改变保留/修改/撤销/暂停；追通需要的证据，不强制训练。代码/数据不可得不直接判论文无效，但会降低相应差异或实施判断；版本/config/checkpoint冲突先核身份与协议，不能据动态main判复现失败。

判决为 covered（淘汰）、revised（缩小或改变主张后重新检查）、distinct（在已查范围暂未覆盖）、unknown。
已有工作覆盖时不以改名保留 idea。新颖性只能写检索边界内的暂定判断，不保证原创。
检索零命中、网络/访问失败、只查近期不能证明创新：记录为 unknown 和缺口，不能写“已证实原创”。
没有全文可暂留 candidate；摘要、标题和缺少反例的搜索不能支撑 ready。决定性近邻只读到摘要的机会不能标 continue/revise，只能 park，见 evidence schema 的 `decisive_neighbors`。可能覆盖主张却还没读的工作不能只写进 `critical_unknown` 的文字绕过门槛：登记为 paper 并写成 `{paper,gap}`，读到正文前同样只能 park。

## 硬关卡先于排名

每个机会记录 data / compute / time / baseline / ethics 的 pass、fail、unknown：

- data：能合法获得目标数据及必要标签/划分，访问已验证；不可得则 fail，阻断 ready。
- compute：内存、设备、成本和软件环境可满足最小实验，不能用愿望替代预算。
- time：阅读、关键基线核验、最小实验、分析能在截止日期内完成。
- baseline：已核验版本、数据设定、强基线结果/实现和评测契约；尚未复现可候选，正式实验前必须 pass。
- ethics：数据许可、隐私、使用限制等适用条件已核验；不适用也写核验理由。

未知资源不阻断入门阅读，但 ready 的五项必须全 pass。每项在 `opportunities.md` 附依据、负责人和解决 unknown 的动作。
未知或失败不能用高创新分抵消。原数据无法获得时仅可明确修正主张和评测，重新审查替代数据，不能悄悄换数据。

## 排序与最小实验

在硬关卡之后比较证据强度、问题价值、差异可检验性、资源匹配、成功/失败都能带来的信息、风险。
表格说明权重和依据，不把主观分数伪装成精度。通常保留约 3 个方向；可只保留 1 个或 0 个，但每个停放项都写可执行化路径和一个可立即动手的构造动作（见 field-discovery 的产出下限）。
同时保留淘汰项和理由，以免后续重复提出。

每个保留方向写：可测量假设、最小数据与 split、关键强基线、单一主要变量、指标与不确定性、预算、
可证伪阈值（falsifier）、停止条件。不要先做大实验再找主张。
核验关键基线 → 小实验 → 固定 evaluation → 记录所有结果；效果突增先查泄漏。
涉及迁移时，在同目标信息/数据/调参预算下比较强目标域基线、直接移植、必要适配；负对照/消融针对具体解释选择，报告收益来源、额外成本及失效边界，不能只证明复杂版胜过弱基线。证据清楚后才作投稿匹配：题目/读者/贡献与评测要求、分区口径/年份及适用官方信息另核，不以目标分区倒推模块或保证录用。

## 变更复核

新版本、撤稿、更正或关键证据改变后：追加日志并运行校验，传递标记依赖；暂停旧 ready 机会，
比较原文、更新 claim/反证/差异表，重新跑硬关卡与排序。保留曾经的决定及变化原因。
通过结构校验不是通过内容审查；Agent 必须实际检查引用、最近似工作和关卡依据。

## 第二版：决策卡与竞争解释

每个方向补 critical_unknown、decision（continue/revise/park/abandon）、change_decision_if、next_search（query、priority=strongest_falsifier/coverage_gap、budget、state）、importance、why_now、attackability、search_refs、tension_refs。已耗尽预算必须 unresolved=true；仍有未解决关键检索不得 ready。已有基线可能足够是竞争解释，不是默认排除项。

最小判别计划单独记录 phase=planned，依次写：原始观察、自己的解释、最强竞争解释、baseline_sufficiency、会让两个解释预测分叉的条件/干预、实验单位、指标、不确定性、泄漏风险、预算与停止条件、discrimination_limit（有意义阈值/边界及所需精度）。不能只说“变规模”就假定会分叉；精度不足的阴性仍不确定。controls 按 ml/theory/observational/wet_lab/other 适配并说明依据，不一律强制湿实验 negative-control；理论任务可用边界反例或替代证明条件。

计划不是执行。实际运行另建 experiments 行，固定 plan_ref，记录 executed_at、measured_values、budget_spent、execution_state、result=supporting/refuting/inconclusive、discriminating 和 reason。未执行不得填 actual；本地脚本也无法独立证明运行真的发生。低辨别力结果必须 inconclusive；技术失败不反驳科学假设。三分判决不是“阴性就否定”，也不把支持写成证明。

失败记忆在 failures：technical/non_discriminating/hypothesis_refuted/resource_infeasible，固定证据、cause、conditions（data/scale/evaluation/method_version）、generalization_scope 和 reopen_conditions。一个场景失败只适用于记录的边界；重新开放须指出新条件怎样解除原失败因素。hypothesis_refuted 必须关联声明具备辨别力的实际反驳记录；因测量不足或资源不可行停下不能冒充科学反驳。

## 生成与审查分离

按任务需要使用单 Agent 自查或独立审查，不默认多 Agent。独立 lane 从同一原始材料、研究问题、资源和等预算出发，先独立记录证据/反例/竞争解释，暂不提供生成 lane 的偏好、理由或排名。具体 idea 审查可提供要核验的最小主张，但不提供其预期判决。各自完成后再比较引用与分歧，核查原文后汇总；多数票不是科学证据。固定审查时机、清单与结果记录位置见 [reviewer](reviewer.md)。

确定性校验与语义科学审查分开汇报。预留 research-evaluation.md 比较等预算 single-agent、重复采样、独立检索核验、multi-agent；记录预算、输入/产物、真实运行状态、评价标准与混杂因素。不宣称这些机制已提高研究质量，只有实际公平评估后才形成结论。

判别预测需要机制或理论依据，不能把两个分数区间当作原因已被识别；正残差可能只挑战当前基线充分性。改变规模须逐条件核算调优力度与资源，以免引入新混杂。
