from pathlib import Path
import csv
from openpyxl import Workbook

root = Path(__file__).resolve().parents[1]
headers = ['门店ID', '周开始', '订单', '净GMV', '商家补贴', '平台补贴', '投放工具', '消耗', '归因净GMV', '归因窗口', '归因定义', '导出时间']
main_rows = [
    ['S1', '2026-10-12', 1200, 60000, 4000, 1500, '点金推广', 1000, 10000, 7, '点击归因', '2026-10-26T00:00:00+08:00'],
    ['S1', '2026-10-12', 1200, 60000, 4000, 1500, '搜索推广', 800, 14400, 7, '点击归因', '2026-10-26T00:00:00+08:00'],
    ['S1', '2026-10-12', 1200, 60000, 4000, 1500, '品牌展示', 600, 7200, 7, '点击归因', '2026-10-26T00:00:00+08:00'],
]
control_rows = [
    main_rows[0],
    ['S1', '2026-10-12', 1200, 60000, 4000, 1500, '搜索推广', 800, 14400, 1, '点击归因', '2026-10-26T00:00:00+08:00'],
]

fixture_dir = root / 'tests' / 'fixtures'
fixture_dir.mkdir(parents=True, exist_ok=True)
workbook = Workbook()
sheet = workbook.active
sheet.title = '周报'
sheet.append(headers)
for row in main_rows:
    sheet.append(row)
workbook.save(fixture_dir / 'main-report.xlsx')

public_dir = root / 'public' / 'fixtures'
public_dir.mkdir(parents=True, exist_ok=True)
for name, rows in [('main-weekly.csv', main_rows), ('control-weekly.csv', control_rows)]:
    with (public_dir / name).open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(rows)
print('Created XLSX test fixture and two public CSV fixtures')
