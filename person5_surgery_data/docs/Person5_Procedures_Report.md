# Person 5：五位患者手术数据处理与答辩指南

> **项目：BMI5207 Group 1a｜Procedures｜OMOP CDM 5.4**  
> **状态：Draft / 待最终整合**  
> 本文根据现有 `surgery patient1-5.xlsx`、`surgery_OMOP_Result.xlsx` 和 `convert_surgery_omop.py` 编写。数字反映当前草稿运行结果，不代表最终已匿名化、已通过 OMOP 质量验证的数据。

## 1. 结果怎么看

| 指标 | 当前结果 | 解释 |
|---|---:|---|
| 原始手术数据行 | 8 | 整理表中有 8 行，其中组合手术重复展示了两个映射组成部分 |
| 唯一原始手术事件 | 7 | 按源记录字段去重后有 7 条事件 |
| 不同原始手术代码 | 6 | 六种不同 `Surgical_Code` |
| OMOP 草稿行 | 8 | 组合手术 `ZSD714H` 暂时拆成两条候选操作 |
| 需要映射复核的草稿行 | 2 | `XSC718T` 和 `ZSD714H` 的 angioplasty 部分 |
| 组合手术复核标记行 | 2 | 均来自 `ZSD714H` |
| 最终可公开的 OMOP 数据 | **尚未生成** | 统一匿名 ID、日期偏移、来源类型和最终验证仍待完成 |

**重要解释：** 7 条原始事件和 8 条草稿行不矛盾。`DSIC004` 在不同原始事件中出现两次，必须保留；`ZSD714H` 包含冠状动脉造影与血管成形术两个组成部分，目前在草稿中展开为两行。是否应保留两条正式 `PROCEDURE_OCCURRENCE` 记录仍需审定。

## 2. 具体做了什么，为什么这样做

### 2.1 整理和检查原始数据

合并五名患者的 Surgical 数据，并保留原始字段：`Surgical_Code`、`Surgical_Desc`、`Operation_Table_Code`、`Case_No`、`Patient_No`、`operation_date`。使用 Python 清理字段名、空白值和编号格式；按完整源记录识别事件，避免仅按手术代码去重造成漏记。

### 2.2 使用 Athena 进行标准概念映射

对六种原始手术代码建立 `Athena_Mapping`，主要检查 Athena 的 **Domain = Procedure、Concept = Standard、Validity = Valid**，同时检查医学含义、同义词与映射局限。原始 `Surgical_Code` 保存在 `procedure_source_value`；标准概念编号写入 `procedure_concept_id`。目前未确认本地手术代码对应的 Athena 来源概念，故草稿的 `procedure_source_concept_id` 为 0。

### 2.3 转换为 OMOP CDM 5.4 草稿

Python 将手术事件与映射表连接，生成 `procedure_occurrence_id`、`procedure_concept_id`、`procedure_date`、`procedure_datetime`、`procedure_source_value`、`procedure_source_concept_id` 等字段。`person_id`、`visit_occurrence_id` 和 `procedure_type_concept_id` 尚未最终填入，当前结果**不是完整的 CDM 5.4 可发布表**。正式导出还须检查该版本的完整字段集、必填字段、数据类型及跨表关联。

### 2.4 全组匿名化和就诊关联规则（待接入）

按照组员统一方案，使用组内私有的 `person_registry.csv` 将 `Patient_No` 映射到一致的 `person_id`；使用 `Patient_No + Case_No` 与 `visit_registry.csv` 精确关联 `visit_occurrence_id`；从 `person_registry.csv` 读取同一患者的 `date_offset_days`，对手术日期统一偏移。不能自行创建另一套患者编号或密钥。上述私有文件和未匿名化数据**不上传公开 GitHub**。

## 3. 六种手术的 Athena 映射结果

| 原始手术代码 | 标准概念名称（当前选择） | Concept ID | 当前核查结论 |
|---|---|---:|---|
| `ESF701I` | Esophagogastroduodenoscopy | 4294382 | 已核查候选；原始描述含 with/without biopsy，需注意是否涉及独立活检操作 |
| `XSC718T` | Biopsy of thorax | 4308384 | **待复核**：未体现 percutaneous 经皮方式 |
| `ZSD714H`（造影部分） | Angiography of coronary artery | 4142645 | 已核查此组成部分 |
| `ZSD714H`（成形术部分） | Transluminal angioplasty of blood vessel | 40489873 | **待复核**：未明确冠状动脉，且腔内操作方式来自候选概念 |
| `DSIC004` | Dilation of cervical canal | 4337799 | 已核查；两条不同源事件使用相同映射 |
| `CSM700N` | Nasendoscopy | 37153412 | 已核查 |
| `SSB705F` | Intramedullary nailing of femur | 4231432 | 已核查；未保留 multifragmentary 与 locking 的全部细节 |

这里“已核查”表示根据现有 Athena 页面完成了概念层面的人工核对，不等于老师认可或最终 CDM 数据通过验证。当前 Excel 的 `vertified` 拼写应统一为 `Verified`；现有脚本已兼容该拼写。

## 4. 数据质量、限制与待办

| 问题 | 当前状态 | 下一步 |
|---|---|---|
| 胸部经皮活检 | `4308384` 是较宽泛概念 | 确认是否接受较宽泛映射，并记录信息损失 |
| 冠状动脉成形术 | `40489873` 未指明 coronary | 复核更准确概念；不能为了匹配而添加支架、单支血管、旋磨等未经证实的细节 |
| 组合手术拆分 | 草稿为两条记录 | 审核是否按两个独立操作或组合概念输出，防止重复计数 |
| 患者编号 | `person_id` 尚未接入 | 使用组内 `person_registry.csv` |
| 就诊编号 | `visit_occurrence_id` 尚未接入 | 按 `Patient_No + Case_No` 使用 `visit_registry.csv` |
| 日期匿名化 | 尚未执行 | 按患者的 `date_offset_days` 偏移且仅执行一次 |
| 操作记录来源类型 | `procedure_type_concept_id` 为空 | 确认数据是否按 EHR 来源处理，再核对相应 Type Concept |
| 数据发布 | 仍含未完成事项 | 完成字段验证、记录数核对、跨表关联与隐私检查后才公开 |

## 5. 答辩时可能被问到的问题

**Q1：为什么 7 条原始手术事件生成 8 行草稿？**  
A：有一条原始记录同时描述 coronary angiography 和 angioplasty，草稿暂时将其表示为两个候选操作。最终是否拆分尚需审定，不能将草稿行数直接等同于已确认的独立手术数量。

**Q2：为什么有些 Concept 仍然需要 Review？**  
A：Athena 中找到的概念虽然是 Standard 和 Valid，但未必完整表达原始操作的部位或方法。我们保留候选并明确记录缺失的信息，避免夸大映射准确性。

**Q3：为什么 `procedure_source_concept_id` 为 0？**  
A：原始本地 `Surgical_Code` 尚未匹配到可确认的 Athena 来源概念。原始代码仍保留在 `procedure_source_value`，标准化概念另存于 `procedure_concept_id`。

**Q4：为什么 `procedure_type_concept_id` 为空？**  
A：原始作业说明仅说明是合成数据，没有明确 EHR 或 Claims 来源。必须确认数据来源类型，才能选择合适的 OMOP Type Concept。

**Q5：如何保证五张表中同一个患者能关联？**  
A：全组复用同一份患者与就诊 registry，并对同一患者使用一致的日期偏移。最终检查 `person_id`、`visit_occurrence_id` 的跨表一致性。

## 6. 文件说明与 GitHub 提交建议

| 文件 | 用途 | 是否可直接公开 |
|---|---|---|
| `convert_surgery_omop.py` | 转换和草稿校验脚本 | **可在检查无硬编码敏感信息后上传** |
| `procedure_mapping.csv` | 手术概念映射与复核说明 | **清除原始患者/就诊标识后可上传；待复核项应保留标记** |
| `procedure_occurrence.csv` | 最终 OMOP 手术表 | **当前尚未完成，不能上传草稿冒充最终表** |
| `surgery_OMOP_Result.xlsx` | 本地草稿与内部复核 | **不公开**，其中复核 Sheet 含原始编号 |
| `surgery patient1-5.xlsx` | 原始输入 | **不公开** |
| `person_registry.csv`、`visit_registry.csv`、`group_key.hex` | 私有对照与密钥 | **不公开** |

建议将本文保存为 `docs/person5_procedures.md`，与组员的 Person 4 文档并列。代码与最终数据按小组仓库既有目录安排，不必擅自更改整体结构。

## 7. 参考资料

- OMOP CDM 5.4 官方结构：https://ohdsi.github.io/CommonDataModel/cdm54.html
- Athena OHDSI：https://athena.ohdsi.org/
- 本组内部数据来源：老师提供的 `Sample data for 5 patients_v2.zip`（不在公开仓库发布原始记录）。

---

**状态总结：** Person 5 已完成原始手术整理、初步 Athena 映射及 OMOP 草稿转换；最终匿名化、来源类型确认、两项待复核映射、组合手术决策和 CDM 5.4 完整验证尚待完成。
