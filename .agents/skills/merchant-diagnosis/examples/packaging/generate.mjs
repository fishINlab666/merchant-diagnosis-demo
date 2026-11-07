import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

// Use the bundled Artifact Tool through a task-local node_modules symlink.
const runtime = process.env.MERCHANT_ARTIFACT_RUNTIME;
if (!runtime) throw new Error('Set MERCHANT_ARTIFACT_RUNTIME to a directory containing the bundled node_modules symlink.');
const requireRuntime = createRequire(path.join(runtime, 'package.json'));
const { Workbook, SpreadsheetFile } = await import(requireRuntime.resolve('@oai/artifact-tool'));
const caseDir = path.dirname(fileURLToPath(import.meta.url));
const rawDir = path.join(caseDir, 'raw');
const counterDir = path.join(caseDir, 'counterinputs');
const repoRoot = path.resolve(caseDir, '../../../..');
const checkDir = path.join(repoRoot, 'runs/merchant-v17-independent-checks/packaging');
await Promise.all([rawDir, counterDir, checkDir].map(p => fs.mkdir(p, { recursive: true })));

const day = (start, offset) => new Date(Date.parse(`${start}T00:00:00Z`) + offset * 86400000).toISOString().slice(0, 10);
const money = n => Math.round(n * 100) / 100;
const csv = rows => '\ufeff' + rows.map(row => row.map(v => {
  const s = v === null || v === undefined ? '' : String(v);
  return /[",\n\r]/.test(s) ? `"${s.replaceAll('"', '""')}"` : s;
}).join(',')).join('\n') + '\n';
const write = (name, contents, dir = rawDir) => fs.writeFile(path.join(dir, name), contents, 'utf8');
const writeCsv = (name, header, rows, dir = rawDir) => write(name, csv([header, ...rows]), dir);

const histHeader = ['记录号', '订单所属日', '观察窗', '包规', '履约单', '已结退款单', '凉餐退款单', '其他退款单', '退款前结算基数万元', '售后冲减元', '已结算到账万元', '广告实耗元'];
const trialHeader = ['记录号', '订单所属日', '包规', '履约单', '已结退款单', '凉餐退款单', '其他退款单', '退款前结算基数元', '售后冲减元', '已结算到账元'];
const costHeader = ['记录号', '订单所属日', '包规', '餐材及按单人工元', '包材实耗元'];
const tempHeader = ['抽样号', '关联试行记录', '包规', '测温份数', '出餐均温摄氏度', '到手均温摄氏度', '制作均时分', '出餐后待取均时分', '在途均时分', '配送距离均值公里', '环境均温摄氏度'];
const history = [], trial = [], costs = [], temperature = [];
for (let i = 0; i < 28; i++) {
  const old = i < 14, id = `H${String(i + 1).padStart(3, '0')}`, date = day('2026-09-28', i);
  const pack = old ? '保温款' : '薄盒款', refund = old ? 12 : 24;
  history.push([id, date, old ? '前窗' : '后窗', pack, 300, refund, old ? 6 : 18, 6, 1.05, refund * 35, money(10500 - refund * 35) / 10000, 0]);
  costs.push([id, date, pack, 5460, old ? 420 : 180]);
}
for (let d = 0; d < 7; d++) {
  for (let g = 0; g < 2; g++) {
    const old = g === 0, id = `T${String(d * 2 + g + 1).padStart(2, '0')}`, date = day('2026-10-26', d);
    const pack = old ? '保温款' : '薄盒款', refund = old ? 6 : 12;
    trial.push([id, date, pack, 150, refund, old ? 3 : 9, 3, 5250, refund * 35, 5250 - refund * 35]);
    costs.push([id, date, pack, 2730, old ? 210 : 90]);
    temperature.push([`Q${String(d * 2 + g + 1).padStart(2, '0')}`, id, pack, 20, 75, old ? [63, 62, 64, 63, 62, 64, 63][d] : [51, 53, 52, 54, 51, 53, 52][d], [10, 11, 9, 10, 10, 9, 11][d], [3, 4, 3, 3, 4, 3, 3][d], [15, 14, 16, 15, 15, 16, 14][d], 2.4, [18, 19, 18, 20, 18, 19, 18][d]]);
  }
}
const quotesHeader = ['凭证号', '项目', '数量或单价', '单位', '适用范围', '备注'];
const quotes = [
  ['P01', '保温款采购及到店价', 1.4, '元/套', '同规格餐盒+保温袋', '报价含税运；每天小批量供货，无最低采购量'],
  ['P02', '薄盒款采购及到店价', 0.6, '元/套', '薄壁餐盒+普通袋', '已发生实际进价，与包材实耗对应'],
  ['P03', '剩余薄盒退回费用', 0, '元', '原价退货', '供应商确认不收退货、报废、运输或违约费用'],
  ['E01', '恢复保温款额外核对工时', 0.5, '小时/营业日', '装箱复核及登记', '首日培训包含在当日工时内，无另计费用'],
  ['E02', '额外核对工时单价', 40, '元/小时', '现有兼职加班', '增量现金支出，不在历史按单人工中'],
  ['E03', '规划营业天数', 30, '天', '下一规划月', '计划值，不是未来实际执行'],
  ['E04', '规划履约单量', 300, '单/营业日', '同SKU与同价格', '老板按最近完整营业日的量级规划，需复盘实际量'],
  ['E05', '审慎规划全口径退款率', 0.05, '比例', '恢复包装后的规划情景', '老板指定的测算假设，不是实测结果或置信下界'],
  ['E06', '新增广告预算', 0, '元', '全部规划期', '当前与规划均无广告'],
];

const publicText = `# 暖禾热饭·望江店公开材料\n\n材料身份：完全合成、离线构造的店铺页及评价。商家、顾客、日期及页面均虚构，无真实商家执行。模拟采样日2026-11-05。\n\n## 店铺页\n\nP01：单店快餐外卖，主推招牌鸡腿热饭套餐，页面标价39元。页面写明单人份、米饭及主菜克重，配送与平台活动另在结算页展示。\nP02：配送页预计35–45分钟，日常营业10:30–21:00；页面未展示餐盒和保温袋配置。\nP03：老板：“近来退款多了，想先把热饭到手体验稳住，再看看哪些钱花错了。我没有投广告，也不准备加广告。”\n\n## 最近12条模拟评价中的摘录\n\n| 编号 | 日期 | 原文 |\n|---|---|---|\n| R01 | 2026-10-18 | 这次盒子薄了，到手饭是温凉的。 |\n| R02 | 2026-10-20 | 和上次送得差不多快，但打开就不热了。 |\n| R03 | 2026-10-22 | 鸡腿味道还是可以，就是饭到手凉了。 |\n| R04 | 2026-10-24 | 今天很热，分量够。 |\n| R05 | 2026-10-25 | 说明写得清楚，一个人吃正好。 |\n\n其余7条未提温度或包装。上述评价是体验线索，不能外推全店差评率，未与后续退款单逐笔关联。\n`;

const defs = [
  ['DEF00', '全部内容均为合成测试材料，模拟数据冻结于2026-11-06。单店单SKU，无其他门店、业态或品牌结果；历史分组试验也为构造事实，不是本Skill促成的商家执行。'],
  ['DEF01', '老板确认：到账就是按订单所属日归属、扣完退款、商家优惠、平台服务费和商家配送费后的商户净结算收入；含实际结算给商户的平台补助，不含广告和原料人工包材。退款前结算基数仅少扣退款这一项，其他扣费与到账相同。售后冲减是商户实际少到账金额，不是消费者支付金额。'],
  ['DEF02', '历史前窗2026-09-28至10-11，后窗10-12至10-25，各14个完整营业日。10-12开店起全量从保温款换为薄盒款。每日300份同SKU已履约订单，每单一份；退款单仍已制作和送达，餐材人工包材照常消耗，不可因退款再冲回成本。'],
  ['DEF03', '退款均为已结案的单次全额冲减，本材料每退款单实际冲减35元，无部分退款、重复退款、未决单、取消未制作单。凉餐和其他原因互斥且覆盖全部退款；截至11-06所有订单均完成5天售后观察窗。公开评价不与退款重复合并。'],
  ['DEF04', '老板确认：39元套餐菜单价、份量、食材、券、营业时长、人员、出餐及派单规则均未改变；只有包材采购与组合在10-12切换。按单餐材及人工每单18.20元，不含包材；售后处理由固定店长工资覆盖，无按退款新增计件支出。固定租金、固定薪资不因方案改变，本轮目标为固定成本前经营贡献，不补算净利润。'],
  ['DEF05', '10-26至11-01既有包装对照：全部同SKU订单在午/晚时段及近/远距离四个区组内，用预先洗牌的包装卡均衡分配两种包装；每日各150份。未按客户偏好、投诉、订单金额或骑手分配，无跨组换包。对照先于本次诊断，结束后恢复薄盒款；11-02起新订单不在此成熟包内。规划比较基线为后窗薄盒配置，不将混装周当全薄盒基线，各观察窗不混加。'],
  ['DEF06', '温度抽查每组每日20份，按事先名单均匀覆盖四个区组，经模拟顾客同意到手开盒即测同一位置；不是投诉后追加测量。两组使用相同测温器具、方法，出餐/待取/在途为对应抽样的阶段均值，配送距离为相应样本均值。温度只是感官体验证据，不作为食品安全合规结论。'],
  ['DEF07', 'CSV与XLSX是同一原始台账的不同封装：经营拼表有重复表头和小计；成本按记录号横排；工作簿出现万元和元。只按H或T记录号计一次，成本记录是这些订单的成本拆分，不能当新增订单。包材采购单价与各记录实耗对应，广告为实际0，空白不得解释成0。'],
  ['DEF08', 'P01/P02为供应商已确认含税含运进价；薄盒剩余库存可按原价退回且额外费用0，无沉没报废计入此次方案。恢复保温款与薄盒装箱的按单工时相同；额外每天半小时复核按40元/小时另付，含首日培训，不包含在原每单18.20元内。没有其他采购、物流、设备或一次执行费。'],
  ['DEF09', '老板要按30个营业日、每天300单比较是否恢复保温款。审慎情景按全口径退款率5%测，基准情景使用同窗保温款组的退款率；二者是规划假设。可据现场对照选择动作，但未来退款率与销量仍看回传，不把目标率记为已发生。'],
  ['DEF10', '店长可从11-09开始连续7天恢复保温款，采购负责补货退货，财务核到账与成本。11-16查执行，11-21按5天售后成熟窗口复盘。商家要求成本全扣后的可比经营贡献差额为正才继续，首周可接受损失上限500元；该线是老板承受范围，不是统计阈值。截至材料冻结尚未发布或执行本次建议。'],
];
const definitionsText = '# 暖禾热饭老板口径与随表记录\n\n' + defs.map(([id, value]) => `## ${id}\n\n${value}`).join('\n\n') + '\n';
await Promise.all([
  write('public.md', publicText), write('definitions.md', definitionsText),
  writeCsv('历史日表.csv', histHeader, history), writeCsv('同窗包装试行.csv', trialHeader, trial),
  writeCsv('成本拆分.csv', costHeader, costs), writeCsv('温度抽查.csv', tempHeader, temperature),
  writeCsv('采购与排班报价.csv', quotesHeader, quotes),
]);

// Counter-inputs replace source records. Independent answers are never written here.
const missingDir = path.join(counterDir, 'missing-cost');
await fs.mkdir(missingDir, { recursive: true });
const missingDefs = defs.filter(([id]) => id !== 'DEF08').map(([id, text]) => {
  if (id === 'DEF07') return [id, '本缺成本测试只使用本目录CSV与definitions.md，另可使用主目录公开页和温度抽查.csv。不要输入主工作簿、成本拆分.csv、采购与排班报价.csv或主definitions.md。CSV是按日包装聚合的完整交易记录，无重复订单。'];
  if (id === 'DEF09') return [id, '老板希望比较是否恢复保温款，仍按30日每天300单、审慎退款率5%及同窗保温款退款率规划。包材报价尚未收到；额外核对每天0.5小时、每小时40元，其他新增费用为0。'];
  return [id, text];
});
missingDefs.push(['DEF11', '两种包材实际采购价和金额都未提供，不能沿用任何其他案例或先前演示的价格。按单餐材人工18.20元已确认，包材不在其中。缺失成本只影响涉及包材的历史贡献、方案净额和是否满足经济性继续条件；温度、退款和其他已知收入数据继续使用。全部为合成材料。']);
await Promise.all([
  write('definitions.md', '# 缺包材成本材料（合成替换输入）\n\n' + missingDefs.map(([id, text]) => `## ${id}\n\n${text}`).join('\n\n') + '\n', missingDir),
  writeCsv('历史日表.csv', histHeader, history, missingDir), writeCsv('同窗包装试行.csv', trialHeader, trial, missingDir),
]);
const reverseTrial = trial.map(row => [...row.slice(0, 4), 12, 9, 3, 5250, 420, 4830]);
const reverseHeader = ['分层记录', '包规', '待取时段', '同窗履约单', '已结退款单', '凉餐退款单', '其他退款单', '测温份数', '出餐均温摄氏度', '到手均温摄氏度', '出餐后待取均时分', '在途均时分'];
const reverseStrata = [
  ['RS1', '保温款', '短待取', 525, 21, 10, 11, 70, 75, 63, 3, 15],
  ['RS2', '保温款', '长待取', 525, 63, 53, 10, 70, 75, 51, 18, 15],
  ['RS3', '薄盒款', '短待取', 525, 21, 10, 11, 70, 75, 63, 3, 15],
  ['RS4', '薄盒款', '长待取', 525, 63, 53, 10, 70, 75, 51, 18, 15],
];
await Promise.all([
  writeCsv('reverse_trial.csv', trialHeader, reverseTrial, counterDir),
  writeCsv('reverse_wait_strata.csv', reverseHeader, reverseStrata, counterDir),
  write('reverse_mechanism.md', '# 包装试行记录更正（全部合成）\n\n这是反向输入测试，不是真实商家反馈。仅替换以下内容，其余历史结算与成本保留。\n\nC1：reverse_trial.csv逐记录替换同窗试行T01–T14的整条交易记录。旧工作簿及CSV的对应T记录失效，不追加、不双计。成本拆分中T01–T14的餐材人工、包材及所属日期保持不变。\n\nC2：主输入温度抽查Q01–Q14全部撤回，改用reverse_wait_strata.csv的4条同窗分层记录。这4条是同一批2100单的另一种分组，不能与T表再加总；其中测温份数只是各层的温度样本量。\n\nC3：更正DEF04中“出餐及派单规则未改变”：10-12开始为配合骑手集中取餐，部分订单在未加热的待取台停留更久。原访谈遗漏该变化；现在保留的分层表按实际待取区分，其他价格、份量、食材、成本和广告口径未变。两包装仍在同窗分配。\n\nC4：老板撤回退款率5%的包装改善假设。该撤回同时覆盖主definitions.md的DEF09、工作簿“采购与排班”E05整条记录（B12:F12，其中C12=0.05）、镜像“采购与排班报价.csv”的row:9；这些是同一项旧假设的不同载体，不是独立有效证据。根据更正后的同窗记录重新判断，不能用任何载体中的旧5%作为本次包装收益依据。只撤回这项退款改善假设，30天、每天300单、包材报价及额外核对工时等其他口径保留。截至本次更正，诊断方案仍未执行。\n', counterDir),
]);

const wb = Workbook.create();
const sheetNames = ['随表说明', '经营拼表', '成本横排', '同窗试行', '温度抽查', '采购与排班'];
const sheets = Object.fromEntries(sheetNames.map(name => [name, wb.worksheets.add(name)]));
const rectangles = [];
function put(name, rows, widths = {}) {
  const sheet = sheets[name], cols = Math.max(...rows.map(r => r.length));
  const matrix = rows.map(r => [...r, ...Array(cols - r.length).fill(null)]);
  sheet.getRangeByIndexes(0, 0, matrix.length, cols).values = matrix;
  const used = sheet.getRangeByIndexes(0, 0, matrix.length, cols);
  used.format.font = { name: 'Arial', size: 10, color: '#24313D' };
  used.format.rowHeight = 23;
  used.format.columnWidth = 13;
  used.format.verticalAlignment = 'center';
  sheet.showGridLines = false;
  sheet.getRangeByIndexes(0, 0, 1, cols).format.rowHeight = 28;
  sheet.getRange('A1').format.font = { name: 'Arial', size: 14, bold: true, color: '#24313D' };
  Object.entries(widths).forEach(([col, width]) => { sheet.getRange(`${col}1:${col}${matrix.length}`).format.columnWidth = width; });
  rectangles.push({ sheet: name, rows: matrix.length, cols, values: matrix });
  return sheet;
}
function header(sheet, row, cols) {
  const range = sheet.getRangeByIndexes(row - 1, 0, 1, cols);
  range.format = { fill: '#E8EDF1', font: { name: 'Arial', size: 10, bold: true }, wrapText: true, rowHeight: 40, verticalAlignment: 'center' };
}
const noteSheet = put('随表说明', [['暖禾热饭·望江店原始台账（全部合成）'], ['模拟冻结日：2026-11-06；表内记录均非真实商家执行。'], [], ['编号', '老板已确认的口径与记录'], ...defs], { A: 16, B: 105 });
header(noteSheet, 4, 2);
noteSheet.getRange(`B5:B${4 + defs.length}`).format.wrapText = true;
noteSheet.getRange(`A5:B${4 + defs.length}`).format.rowHeight = 78;
const historyRows = [['历史日结导出（合成）'], ['金额列混用万元/元；小计与重复表头不是新订单。'], [], histHeader];
for (let w = 0; w < 2; w++) {
  if (w) historyRows.push([], histHeader);
  const part = history.slice(w * 14, w * 14 + 14);
  historyRows.push(...part.map(r => [r[0], new Date(`${r[1]}T00:00:00Z`), ...r.slice(2)]));
  historyRows.push([w ? '后窗小计' : '前窗小计', null, null, null, ...[4, 5, 6, 7, 8, 9, 10, 11].map(i => money(part.reduce((n, r) => n + r[i], 0)))]);
}
const hSheet = put('经营拼表', historyRows, { A: 18, B: 15, C: 12, D: 12, I: 18, J: 17, K: 18 });
header(hSheet, 4, 12); header(hSheet, 21, 12); hSheet.freezePanes.freezeRows(4);
hSheet.getRange(`B5:B${historyRows.length}`).setNumberFormat('yyyy-mm-dd');
hSheet.getRange(`I5:K${historyRows.length}`).setNumberFormat('0.0000');
const costRows = [['订单成本导出（合成；横排）'], ['按H/T记录号与经营拼表/同窗试行连接，不增加订单。'], []];
const costHeaderRows = [];
for (let block = 0; block < 3; block++) {
  const slice = costs.slice(block * 14, block * 14 + 14);
  costHeaderRows.push(costRows.length + 1);
  costRows.push(['记录号', ...slice.map(r => r[0])]);
  costRows.push(['包规', ...slice.map(r => r[2])]);
  costRows.push(['餐材按单工时元', ...slice.map(r => r[3])]);
  costRows.push(['包材实耗元', ...slice.map(r => r[4])]);
  costRows.push([]);
}
const cSheet = put('成本横排', costRows, { A: 22 });
costHeaderRows.forEach(row => header(cSheet, row, 15));
const tRows = [['同一周包装分组试行（合成）'], ['10-26至11-01；同SKU分层分配；历史试行先于本次诊断。'], [], trialHeader, ...trial.map(r => [r[0], new Date(`${r[1]}T00:00:00Z`), ...r.slice(2)])];
const tSheet = put('同窗试行', tRows, { A: 16, B: 15, C: 13, H: 19, I: 17, J: 19 });
header(tSheet, 4, 10); tSheet.getRange('B5:B18').setNumberFormat('yyyy-mm-dd'); tSheet.freezePanes.freezeRows(4);
const qRows = [['到手温度及履约抽查（合成）'], ['同窗抽样均值；非食品安全阈值；样本不能重复计入订单。'], [], tempHeader, ...temperature];
const qSheet = put('温度抽查', qRows, { A: 16, B: 18, D: 14, E: 18, F: 18, H: 20, J: 20, K: 18 });
header(qSheet, 4, 11);
qSheet.getRange('E5:K18').setNumberFormat('0.0');
const pRows = [['采购及排班报价（合成）'], ['事实报价和老板规划参数；没有未来经营结果。'], [], quotesHeader, ...quotes];
const pSheet = put('采购与排班', pRows, { A: 13, B: 31, C: 17, D: 18, E: 33, F: 63 });
header(pSheet, 4, 6); pSheet.getRange('E5:F13').format.wrapText = true; pSheet.getRange('A5:F13').format.rowHeight = 44;
pSheet.getRange('C12').setNumberFormat('0.0%');
wb.recalculate();

const inspect = await wb.inspect({ kind: 'workbook,sheet,table', maxChars: 7000, tableMaxRows: 3, tableMaxCols: 6 });
await write('workbook-inspect.ndjson', inspect.ndjson, checkDir);
const errors = await wb.inspect({ kind: 'match', searchTerm: '#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!', options: { useRegex: true, maxResults: 100 }, summary: 'raw workbook error scan' });
await write('workbook-errors.ndjson', errors.ndjson, checkDir);
const xlsx = await SpreadsheetFile.exportXlsx(wb);
await xlsx.save(path.join(rawDir, '暖禾热饭_模拟原始台账.xlsx'));
// The exporter creates a technical sidecar; keep it outside the model's raw directory.
try {
  await fs.rename(path.join(rawDir, '暖禾热饭_模拟原始台账.xlsx.inspect.ndjson'), path.join(checkDir, 'export-inspect.ndjson'));
} catch (error) {
  if (error.code !== 'ENOENT') throw error;
}
// Serialize source rectangles solely for cross-format verification, outside raw inputs.
await write('workbook-source-rectangles.json', JSON.stringify(rectangles, null, 2) + '\n', checkDir);
for (const [sheetName, range] of [['随表说明', 'A1:B8'], ['经营拼表', 'A1:L9'], ['成本横排', 'A1:O8'], ['同窗试行', 'A1:J9'], ['温度抽查', 'A1:K9'], ['采购与排班', 'A1:F13']]) {
  const preview = await wb.render({ sheetName, range, scale: 1.25, format: 'png' });
  await fs.writeFile(path.join(checkDir, `${sheetName}.png`), new Uint8Array(await preview.arrayBuffer()));
}
console.log(JSON.stringify({ merchant: '暖禾热饭·望江店', synthetic: true, history_rows: history.length, trial_rows: trial.length, cost_rows: costs.length, temperature_rows: temperature.length, xlsx: path.join(rawDir, '暖禾热饭_模拟原始台账.xlsx'), checks: checkDir }));
