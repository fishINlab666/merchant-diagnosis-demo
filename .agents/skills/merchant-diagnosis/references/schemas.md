# 标准字段与输出结构

## AI 表格映射

每个文件／工作表返回：

- `file_name`、`sheet_name`。
- `grain`：`store_week`、`store_week_tools` 或 `unknown`。
- `fields`：标准字段名 → 原表头。允许：
  - 身份时间：`store_id`、`week_start`、`exported_at`。
  - 经营：`orders`、`net_gmv`、`merchant_subsidy`、`platform_subsidy`、`exposure`、`visits`、`repeat_customer_rate`、`member_share`。
  - 工具：`tool_name`、`spend`、`attributed_gmv`、`roi`、`attribution_window_days`、`attribution_definition`。
- `missing_fields`：无法可靠映射的标准字段。
- `notes`：粒度、单位和歧义说明。

程序只接受这些标准字段。模型不得返回列值，只能返回列名和解释。

## 公开初诊

- `headline`：有业务判断的标题。
- `observations`：最多 3 项，每项含 `title`、`evidence`、`why_it_matters`、`next_check`。
- `data_request`：`summary`、`items`、`boundary_note`。

## 完整方案

- `headline`。
- `issues`：最多 3 项，每项含 `title`、`evidence`、`why_it_matters`。
- `recommendation`：`mode`、`source_tool`、`target_tool`、`amount`、`gross_margin`、`marginal_factor`、`merchant_subsidy_delta`、`period`。
- `client_talk_tracks`：3 句。
- `follow_ups`：3 项，每项含 `action`、`owner`、`metric`、`review_date`、`stop_condition`。
- `boundary_note`：全篇唯一边界提醒。

程序另外生成 `mapping_preview`、`canonical_report`、`calculation`、`warnings` 和 `run_metadata`，不由模型伪造。
