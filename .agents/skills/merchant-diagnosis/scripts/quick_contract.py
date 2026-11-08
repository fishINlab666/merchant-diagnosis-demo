"""Bind a single business report to this run's evidence and arithmetic."""
import copy
import json
import math
from pathlib import PurePosixPath
import re

from service_calculator import _tree
from validate import LOCATORS, valid_location
from method_usage import validate_usage


def _pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('JSON 键名重复')
        value[key] = item
    return value


def _finite_tree(value):
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError('JSON 不允许非有限数值')
    if isinstance(value, dict):
        for item in value.values():
            _finite_tree(item)
    elif isinstance(value, list):
        for item in value:
            _finite_tree(item)


def read_json_text(raw):
    """Allow one enclosing JSON fence, but never guess damaged JSON or values."""
    if not isinstance(raw, str):
        raise ValueError('JSON 输入须为文字')
    raw = raw.strip().lstrip('\ufeff')
    fenced = re.fullmatch(r'```(?:json)?\s*\n(.*?)\n```', raw, re.S | re.I)
    if fenced:
        raw = fenced.group(1)
    try:
        value = json.loads(raw, object_pairs_hook=_pairs,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError('JSON 不允许非有限数值')))
    except json.JSONDecodeError as error:
        raise ValueError(f'JSON 格式错误：第 {error.lineno} 行第 {error.colno} 列') from None
    _finite_tree(value)
    return value


def parse_report(raw):
    value = read_json_text(raw) if isinstance(raw, str) else copy.deepcopy(raw)
    _finite_tree(value)
    if not isinstance(value, dict) or not value:
        raise ValueError('报告必须为非空 JSON 对象')
    if 'report' in value:
        if value.get('kind', 'final') != 'final':
            raise ValueError('报告包装 kind 必须为 final')
        value = value['report']
    if not isinstance(value, dict) or not value:
        raise ValueError('report 必须为非空对象')
    return value


def _text(value, path, optional=False):
    if value is None and optional:
        return ''
    if not isinstance(value, str) or (not optional and not value.strip()):
        raise ValueError(path + ' 须为非空文字')
    if len(value) > 10000:
        raise ValueError(path + ' 文字过长')
    return value.strip()


def _object(value, path):
    if not isinstance(value, dict):
        raise ValueError(path + ' 须为对象')
    return value


def _objects(value, path, *, minimum=0, maximum=100):
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        raise ValueError(f'{path} 须为 {minimum}–{maximum} 项列表')
    return [_object(item, path + f'[{index}]') for index, item in enumerate(value)]


def _texts(value, path):
    if isinstance(value, str):
        value = [value] if value.strip() else []
    if not isinstance(value, list) or len(value) > 100:
        raise ValueError(path + ' 须为文字列表')
    return [_text(item, path) for item in value]


def _number(value, path):
    if value is None:
        return None
    try:
        finite = type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise ValueError(path + ' 须为有限数值或 null，未知不可填零')
    return value


def _sources(materials):
    items = materials.get('materials', []) if isinstance(materials, dict) else materials
    sources = {}
    for item in _objects(items, 'materials'):
        name = _text(item.get('name'), 'material.name')
        if name in sources:
            raise ValueError('材料 basename 重复，无法唯一匹配来源')
        if not isinstance(item.get('fragments'), list):
            raise ValueError('材料缺少 fragments')
        sources[name] = item
    return sources


def _evidence(value, sources, path, required=False):
    if isinstance(value, dict):
        value = [value]
    items = _objects(value or [], path, minimum=1 if required else 0)
    result = []
    for item in items:
        name = _text(item.get('material'), path + '.material')
        if name not in sources:
            name = PurePosixPath(name.replace('\\', '/')).name
        locator = _text(item.get('locator'), path + '.locator')
        if (name not in sources or not LOCATORS.fullmatch(locator)
                or not valid_location(name, name + '／' + locator, sources[name], sources)):
            raise ValueError(path + ' 的材料或定位无法回查')
        citation = {'material': name, 'locator': locator}
        if citation not in result:
            result.append(citation)
    return result


def normalize_requests(requests, materials):
    """Only resolve unique material basenames; do not coerce numeric inputs."""
    sources = _sources(materials)
    result = copy.deepcopy(_objects(requests, 'requests', minimum=1))
    for request in result:
        variables = _object(request.get('variables'), 'variables')
        for variable in variables.values():
            variable = _object(variable, 'variable')
            if 'evidence' in variable:
                variable['evidence'] = _evidence(variable['evidence'], sources, 'variable.evidence')
    return result


def _value(item, unit, sources, calculations, path, *, main=False):
    result = {}
    if item.get('calc_id') is not None:
        key = _text(item['calc_id'], path + '.calc_id')
        calculation = calculations.get(key)
        if calculation is None or calculation.get('status') not in ('ok', 'unknown'):
            raise ValueError(path + '.calc_id 必须引用本轮成功或缺数的真实计算')
        if main:
            variables = _object(calculation.get('variables'), 'money.calculation.variables')
            _, used = _tree(calculation.get('expression'), variables)
            if not used:
                raise ValueError('money 计算须实际使用至少一个有来源或明确假设的变量，不能只写裸常数')
            for name in used:
                variable = _object(variables[name], 'money.calculation.variable')
                if not variable.get('evidence') and not _text(
                        variable.get('assumption'), 'money.calculation.assumption', optional=True):
                    raise ValueError('money 使用的变量须提供来源或明确假设')
        if calculation.get('unit') != unit:
            raise ValueError(path + ' 的单位与计算结果不一致；单位换算须另行计算')
        number = _number(calculation.get('value'), path + '.value')
        if (calculation['status'] == 'unknown') != (number is None):
            raise ValueError(path + ' 的计算状态与数值不一致')
        result.update(calc_id=key, value=number)
        evidence = [citation for variable in calculation.get('variables', {}).values()
                    for citation in variable.get('evidence', [])]
        result['evidence'] = _evidence(evidence, sources, path + '.evidence')
    else:
        number = _number(item.get('value'), path + '.value')
        if main and number is not None:
            raise ValueError('money 的数值须引用 calc_id；原始金额也可用恒等公式核算')
        result['value'] = number
        result['evidence'] = _evidence(item.get('evidence'), sources, path + '.evidence',
                                       required=number is not None)
    return result


def bind_report(report, materials, calculations, expected_merchant=None, *, require_method_usage=False):
    """Normalize display fields; evidence and calculations are never fabricated.

    This checks sources, arithmetic references, and actionable structure. It does
    not establish that a cited statement supports the model's business judgment.
    """
    report = parse_report(report)
    sources = _sources(materials)
    known_calculations = {}
    for item in _objects(calculations, 'calculations'):
        key = _text(item.get('id'), 'calculation.id')
        if key in known_calculations:
            raise ValueError('计算编号重复')
        known_calculations[key] = item
    merchant = _object(report.get('merchant'), 'merchant')
    identity = {key: _text(merchant.get(key), 'merchant.' + key)
                for key in ('name', 'scope', 'period')}
    if type(merchant.get('synthetic')) is not bool:
        raise ValueError('merchant.synthetic 须为布尔值')
    identity['synthetic'] = merchant['synthetic']
    if expected_merchant and any(identity[key] != expected_merchant[key]
                                 for key in ('name', 'synthetic') if key in expected_merchant):
        raise ValueError('报告商家身份或合成标记与本轮不一致')
    result = {'merchant': identity, 'headline': _text(report.get('headline'), 'headline')}
    money = _object(report.get('money'), 'money')
    result['money'] = {key: _text(money.get(key), 'money.' + key,
                                 optional=key in ('note', 'basis'))
                       for key in ('label', 'unit', 'period', 'note', 'basis')}
    result['money'].update(_value(money, result['money']['unit'], sources,
                                  known_calculations, 'money', main=True))
    result['findings'] = []
    for item in _objects(report.get('findings', []), 'findings', maximum=3):
        result['findings'].append({
            'title': _text(item.get('title'), 'finding.title'),
            'detail': _text(item.get('detail'), 'finding.detail'),
            'basis': _text(item.get('basis'), 'finding.basis', optional=True),
            'evidence': _evidence(item.get('evidence'), sources, 'finding.evidence')})
    result['actions'] = [{key: _text(item.get(key), 'action.' + key)
                          for key in ('title', 'owner', 'timing', 'budget', 'success', 'stop')}
                         for item in _objects(report.get('actions'), 'actions', minimum=1, maximum=3)]
    followup = _object(report.get('followup'), 'followup')
    result['followup'] = {key: _text(followup.get(key), 'followup.' + key)
                          for key in ('when', 'decision')}
    result['followup']['collect'] = _texts(followup.get('collect'), 'followup.collect')
    if not result['followup']['collect']:
        raise ValueError('followup.collect 须说明回传什么')
    result['charts'] = []
    for chart in _objects(report.get('charts', []), 'charts', maximum=3):
        chart_type = 'bar' if chart.get('type') == 'bars' else chart.get('type')
        if chart_type not in ('bar', 'stacked', 'waterfall'):
            raise ValueError('chart.type 须为 bar、stacked 或 waterfall')
        bound = {key: _text(chart.get(key), 'chart.' + key, optional=key == 'caption')
                 for key in ('type', 'title', 'unit', 'caption')}
        bound['type'] = chart_type
        bound['series'] = []
        for point in _objects(chart.get('series'), 'chart.series', minimum=1):
            item = {'label': _text(point.get('label'), 'series.label')}
            item.update(_value(point, bound['unit'], sources, known_calculations, 'series'))
            for key in ('role', 'group'):
                if point.get(key) is not None:
                    item[key] = _text(point[key], 'series.' + key)
            bound['series'].append(item)
        result['charts'].append(bound)
    analysis = _object(report.get('analysis'), 'analysis')
    result['analysis'] = {key: _text(analysis.get(key), 'analysis.' + key)
                          for key in ('goal', 'chosen_strategy', 'execution')}
    for key in ('alternatives', 'assumptions'):
        result['analysis'][key] = _texts(analysis.get(key, []), 'analysis.' + key)
    result['gaps'] = [{key: _text(item.get(key), 'gap.' + key) for key in ('item', 'why')}
                      for item in _objects(report.get('gaps', []), 'gaps')]
    if 'audience_plan' in report:
        result['audience_plan'] = []
        for item in _objects(report['audience_plan'], 'audience_plan', maximum=6):
            row = {key: _text(item.get(key), 'audience_plan.' + key)
                   for key in ('audience', 'product', 'benefit', 'decision', 'validation')}
            row['basis'] = _text(item.get('basis'), 'audience_plan.basis', optional=True)
            row['evidence'] = _evidence(item.get('evidence'), sources, 'audience_plan.evidence', required=True)
            if 'economics' in item:
                economics = _object(item['economics'], 'audience_plan.economics')
                row['economics'] = {key: _text(economics.get(key), 'audience_plan.economics.' + key)
                                    for key in ('label', 'unit')}
                row['economics'].update(_value(economics, row['economics']['unit'], sources,
                    known_calculations, 'audience_plan.economics', main=True))
            result['audience_plan'].append(row)
    if require_method_usage or 'method_usage' in report:
        result['method_usage'] = validate_usage(report.get('method_usage'), result,
            bind_evidence=lambda evidence: _evidence(evidence, sources, 'method_usage.evidence'))
    return result
