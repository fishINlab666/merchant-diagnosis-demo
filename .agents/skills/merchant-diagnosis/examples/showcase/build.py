"""Rebuild the presentation fixtures from this repository's recorded Codex runs.

This is an example-maintenance script, never an analysis step for a new merchant.
The exported bundle includes ready-to-use snapshots and needs no repository runs.
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def read(path):
    return json.loads(path.read_text())


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def snapshot(source, name):
    target = HERE / "runs" / name
    source = ROOT / source
    for report in sorted(source.glob("S*/report.md")):
        output = target / report.parent.name / "report.md"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(report.read_bytes())
        material_path = report.parent / "materials.json"
        if material_path.exists():
            materials = read(material_path).get("materials", [])
            write(output.parent / "materials.json", {"materials": [
                {"name": item["name"], "sha256": item["sha256"]} for item in materials
            ]})
    execution_path = source / "execution.json"
    if not execution_path.exists():
        execution_path = source / "S5" / "execution.json"
    original = read(execution_path)
    metadata = {key: original[key] for key in ["executor", "model_id"] if key in original}
    metadata.update({"snapshot_only": True, "source_record_sha256": hashlib.sha256(execution_path.read_bytes()).hexdigest(),
                     "note": "历史实际执行记录的脱路径展示副本；复制与导出不是新推理。完整报告原字节未改。"})
    write(target / "execution.json", metadata)


def highlight(label, value, unit, note, evidence):
    return dict(label=label, value=value, unit=unit, note=note, evidence=evidence)


def point(label, value, **kwargs):
    return dict(label=label, value=None if value is None else float(value), **kwargs)


def chart(id, type, title, unit, caption, series, evidence):
    return dict(id=id, type=type, title=title, unit=unit, caption=caption, series=series, evidence=evidence)


def build():
    baseline_path = ROOT / "runs/merchant-diagnosis-v1.2/S3/calculations.json"
    revised_path = ROOT / "runs/merchant-diagnosis-v1.2/revised/S3/calculations.json"
    messy_path = ROOT / "runs/merchant-messy-weekly-2026-11-06/calculations.json"
    base, revised, messy = map(read, [baseline_path, revised_path, messy_path])
    snapshot("runs/merchant-diagnosis-v1.2", "chain-original")
    snapshot("runs/merchant-diagnosis-v1.2/revised", "chain-revised")
    snapshot("runs/merchant-messy-weekly-2026-11-06", "messy-weekly")
    finance = "经营周报.xlsx／sheet:周报!D4:F7；S3/calculations.json／monthly_30_day_baseline；S5/report.md／预期改善。"
    channel = "经营周报.xlsx／sheet:渠道!E4:J5；S3/calculations.json／channel；definitions.md／DEF03。"
    old_scenario = "S3/calculations.json／monthly_scenarios、first_7_day_scenario；S5/report.md／预期改善；definitions.md／DEF05–DEF06。"
    new_scenario = "negative_trial.csv／N01–N03／row:2-4；S3/calculations.json／continued_reallocation_scenarios；S5/report.md／预期改善。"
    m = base["monthly_30_day_baseline"]
    scenarios = base["monthly_scenarios"]
    old = {"highlights": [
        highlight("30 天规划广告总额", float(m["ads"]), "元", "30 店；由 28 天账单折算", finance),
        highlight("A 渠道历史费用占比", float(base["channel"][0]["spend_share"])*100, "%", "占比不能单独证明投放低效", channel),
        highlight("月度基准情景贡献差额", float(scenarios[0]["contribution_difference"]), "元", "条件测算；额外执行费已扣", old_scenario),
        highlight("首轮 7 天调拨上限", float(base["first_7_day_scenario"]["shift"]), "元", "推广总额不增；先验证再继续", old_scenario)
    ], "charts": [
        chart("budget", "stacked", "预算总额不变，先验证组合", "元", "30 天规划结构；整月调整须在小额试行后另行决定。执行费 6,000 元另扣，不包含在推广费中。", [
            point("A", 270000, group="当前规划"), point("B", 30000, group="当前规划"),
            point("A", 210000, group="月度条件方案"), point("B", 90000, group="月度条件方案")], old_scenario),
        chart("scenarios", "bars", "月度价值：同时看正向和负向", "元", "30 店、30 天；相对 660,000 元规划基线的固定成本前贡献差额。尚未执行，不能称净利润或实际增收。", [point(row["name"]+"情景", row["contribution_difference"]) for row in scenarios], old_scenario),
        chart("bridge", "waterfall", "基准情景的贡献从哪里来", "元", "贡献＝净收入－变动成本－推广－额外执行费。历史观察非随机；两动作可加、成本率 60% 稳定及未饱和均为假设。", [point("规划基线",m["contribution"],role="total"), point("收入变化",scenarios[0]["revenue_difference"]),point("成本变化",-float(scenarios[0]["variable_cost_difference"])),point("执行费",-float(scenarios[0]["execution_fee"])),point("条件结果",scenarios[0]["adjusted_contribution"],role="total")], old_scenario),
        chart("marginal", "bars", "比较边际观察，不照平均 ROI 搬预算", "元/元", "分别减少 A 或增加 B 的对照调整后收入变化幅度；非净贡献，也不是已证明的组合因果效应。", [point("减 A 收入损失",base["marginal_estimates"]["A_loss"]), point("增 B 收入增加",base["marginal_estimates"]["B_gain"])], "经营周报.xlsx／sheet:边际试行!D4:K6；S3/calculations.json／marginal_estimates。")
    ]}
    r = revised["continued_reallocation_scenarios"][0]
    new = {"highlights": [
        highlight("30 天规划广告总额", float(m["ads"]), "元", "暂保持原配置；只涉及 30 店", finance),
        highlight("A 渠道历史费用占比", 90, "%", "历史占比未变，决策依据已变", channel),
        highlight("继续旧方案的月度差额", float(r["contribution_difference"]), "元", "条件情景；并非已发生损失", new_scenario),
        highlight("本次新启动调拨", 0, "元", "撤回待启动计划；已发生费用待核", "S5/report.md／现在／建议／A1。")
    ], "charts": [
        chart("marginal", "bars", "新材料改变了调拨依据", "元/元", "新表替换旧观察。减 A 的收入损失高于增 B 的收入增加，继续旧调拨已不符合贡献目标。两动作可加及成本率稳定仍是假设。", [point("减 A：旧观察",base["marginal_estimates"]["A_loss"],group="原始观察"),point("减 A：更正后",revised["current_marginal_estimates"]["A_loss"],group="更正观察"),point("增 B：旧观察",base["marginal_estimates"]["B_gain"],group="原始观察"),point("增 B：更正后",revised["current_marginal_estimates"]["B_gain"],group="更正观察")], new_scenario),
        chart("scenario", "bars", "继续旧方案，贡献情景转负", "元", "30 店、30 天相对规划基线的固定成本前贡献差额，已扣执行费。旧正向预测已撤回；-18,000 元不等于实亏或已节省。", [point("原基准（失效）",scenarios[0]["contribution_difference"],group="历史版本"),point("更正后情景",r["contribution_difference"],group="当前版本")], old_scenario + new_scenario),
        chart("budget", "stacked", "当前动作：保留配置，核清执行", "元", "30 天规划仍为 A 270,000 元、B 30,000 元。若旧计划已执行，先停追加，由预算负责人核清剩余额度和费用。", [point("A",270000,group="当前规划配置"),point("B",30000,group="当前规划配置")], "S5/report.md／现在／建议／A1；执行状态待补 D4。"),
        chart("bridge", "waterfall", "若仍执行旧方案，贡献如何变化", "元", "仅是继续原月度调拨的条件情景，固定成本前；成本率 60%、历史非随机、两动作可加的限制保留。", [point("规划基线",r["baseline_contribution"],role="total"),point("收入变化",r["revenue_difference"]),point("成本少发生",-float(r["cost_difference"])),point("执行费",-float(r["execution_fee"])),point("条件结果",r["adjusted_contribution"],role="total")],new_scenario)
    ]}
    evidence = "拾味饭堂_模拟原始周报.xlsx／sheet:财务横表!B3:I5、sheet:营运拼表!A5:G15；calculations.json／stores、totals；S4/report.md／事实与计算。"
    w = messy["totals"]["W1"]
    stores = [("M01","国贸"),("M02","大学城"),("M03","社区"),("M04","园区")]
    weekly = {"highlights": [
        highlight("四店本周完成订单", w["completed_orders_all4"], "单", "W1 对比 W0：增加 200 单", evidence),
        highlight("四店本周净结算", w["net_receipts_all4"], "元", "W1 对比 W0：减少 10,000 元", evidence),
        highlight("已知三店本周贡献", w["contribution_known3"], "元", "固定成本前；W0 为 100,000 元", evidence),
        highlight("园区店本周贡献", None, "元", "成本缺失；不纳入三店合计", evidence)
    ], "charts": [
        chart("stores", "bars", "贡献下滑集中在大学城", "元", "W0：10/12–10/18；W1：10/19–10/25。各店固定成本前周贡献；园区两期均缺成本。", [point(name+' '+week,messy["stores"][id][week]["contribution"],group=week) for id,name in stores for week in ["W0","W1"]], evidence),
        chart("volume", "bars", "增单未必增贡献，先分店处理", "单", "同店 W0→W1 完成单变化。社区多 500 单却少贡献 3,000 元；国贸改善，园区尚不能判断贡献。", [point(name,messy["changes"][id]["orders_change"]) for id,name in stores], evidence),
        chart("mix", "waterfall", "社区：销量增加，被单位收益吞没", "元", "W0→W1 固定成本前周贡献的顺序分解：销量、结构、单位收益。广告不变；这是会计分解，不是对原因的因果证明。", [point("W0 贡献",30000,role="total"),point("销量",messy["M03_contribution_bridge"]["volume"]),point("商品结构",messy["M03_contribution_bridge"]["mix"]),point("单位收益",messy["M03_contribution_bridge"]["unit"]),point("W1 贡献",27000,role="total")], "拾味饭堂_模拟原始周报.xlsx／sheet:菜品菜单!D3:F9；calculations.json／M03_contribution_bridge。"),
        chart("sku", "bars", "社区：先核商品收益，再改展示", "元/单", "各 SKU 广告前单位贡献＝净入账－变动成本；未分摊广告及固定成本。鸡腿占比提升同时单位收益下降，双拼是否可售须先核。", [point(row["sku"]+' '+week,row["pre_ad_contribution_unit"],group=week) for week in ["W0","W1"] for row in messy["menu"][week]], "拾味饭堂_模拟原始周报.xlsx／sheet:菜品菜单!D3:F9；calculations.json／menu。")
    ]}
    for name,view in [("chain-original",old),("chain-revised",new),("messy-weekly",weekly)]:
        write(HERE / "views" / (name+".json"),view)
    cases = [
        {"id":"chain","title":"榕味小馆 · 30 店预算决策","label":"30 店 · 预算决策","synthetic":True,"active_version":"revised","versions":[
            {"id":"original","label":"原始分析 · 已更正","run_dir":"runs/chain-original","view_file":"views/chain-original.json","superseded":True},
            {"id":"revised","label":"补数更新 · 当前结论","run_dir":"runs/chain-revised","view_file":"views/chain-revised.json"}]},
        {"id":"messy","title":"拾味饭堂 · 四店经营复盘","label":"四店 · 乱格式周报","synthetic":True,"active_version":"current","versions":[
            {"id":"current","label":"周报诊断 · 待补成本","run_dir":"runs/messy-weekly","view_file":"views/messy-weekly.json"}]}
    ]
    write(HERE / "catalog.json", {"title":"商户经营诊断 · 经营看板","cases":cases})
    calc_sources = []
    for p, name in zip([baseline_path,revised_path,messy_path],["chain-original","chain-revised","messy-weekly"]):
        target = HERE / "calculations" / (name+".json")
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(p.read_bytes())
        calc_sources.append({"source":str(p.relative_to(ROOT)),"snapshot":str(target.relative_to(HERE)),"sha256":hashlib.sha256(p.read_bytes()).hexdigest()})
    reports = [{"snapshot":str(p.relative_to(HERE)),"sha256":hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted((HERE/"runs").glob("*/S*/report.md"))]
    write(HERE / "calculation-sources.json", {"presentation_only":True,"sources":calc_sources,"reports":reports,"note":"图表取自上述既有计算与阶段报告，build.py 只组装展示，不调用模型。"})
    print("已生成 3 组报告快照、视图和 2 案例目录；未执行新分析。")


if __name__ == "__main__":
    build()
