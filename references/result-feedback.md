# 实验结果回流：改主张、改方向

实验结果回来（本机跑完，或从别的设备、workbench 结果包带回）时加载。目标只有一个：根据实际结果决定每条**我们的主张**保留、调整还是撤回，再决定方向是否继续。

## 三类记录分开

- **论文说了什么** → `claims.jsonl`，必须挂在一篇论文的固定版本下。
- **我们准备论证什么** → `assertions.jsonl`。不挂论文；状态只能由它引用的证据撑起。
- **实际做了什么** → `experiments.jsonl` 的 executed 记录。程序跑成功（`execution_state`）和结果支持主张（`result`）是两件事，分开填。

## 回流步骤

1. **先落实测。** 每次运行一条 executed 记录，指向固定的计划修订（plan_ref）。同一计划修订可以有多次运行。导入的结果先核对任务身份、计划修订、来源与附件 hash，再写入；未经人确认接纳的结果不写 executed。
2. **逐条改主张。** 对受影响的 assertion 追加下一 rev，在 `evidence` 里给每条证据标 `role`：
   - `supports` / `refutes` 必须与运行结果一致；低辨别力或技术失败只能标 `context`。
   - `supported`：至少一次具辨别力、完成且支持的运行；纯文献主张可以用一条全文阅读、材料可用（material_access=available）的论文原述（paper_statement），但要在 does_not_support 里写清没有实测。
   - `refuted`：至少一次具辨别力、完成且反驳的运行；同时写 failures（hypothesis_refuted）及重开条件。
   - `inconclusive`：跑了但分不开，或明确支持与明确反驳的证据互相冲突（冲突时不得标 supported/refuted）；写 failures（non_discriminating），说明缺的精度或对照。
   - `untested`：还没有能定状态的证据。一旦引用了足以判定支持或反驳的证据，就必须改状态；只作背景的证据标 `context`。
   - `withdrawn`：不是被实验推翻，而是近邻已覆盖、问题重构等原因不再主张；必须写 review_note。旧 rev 保留。
   - `does_not_support` 每次重写：这次结果仍然不能支持的更强说法。
3. **再改方向。** opportunity 追加 rev：decision 在 continue / revise / park / abandon 中选，并更新 critical_unknown 与 change_decision_if。一次阴性不否定整个方向，除非它正好测的是方向成立的必要条件。
4. **跑校验。** `check-research.py --mark-review`：被移动或待复核的证据会把依赖它的主张、方向和交付物引用一起标为待复核。
5. **写进交付物。** 报告、提纲中的结论句引用 `[assertions/id@rev]`，数字引用 `[experiments/id@rev]`；交接写明哪些主张状态变了、为什么。

## 不做的事

- 不因结果好看就把 `inconclusive` 改成 `supported`；先查泄漏、对照和统计单位。
- 不删除或覆盖被推翻的主张；撤回也是追加 rev。
- 校验通过只说明引用结构与状态一致，不说明实验设计正确或结论成立。
