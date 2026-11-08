"""Method applicability records and public provenance, independent of rendering."""
from validate import LOCATORS


METHODS = {
    'store_segmentation': {
        'name': '按店况分配资源',
        'origin': '来自阿里 KA 门店分层实践；本产品将平台侧收益判断改写为商户贡献与承接能力。'},
    'audience_offer': {
        'name': '人群 × 商品 × 权益',
        'origin': '来自阿里 KA 按频次与生命周期匹配商品和权益的实践；本轮按商户材料细化。'},
    'tool_mix': {
        'name': '先定策略，再选工具',
        'origin': '来自阿里 KA 先判断增长问题、再组合运营与投放工具的实践。'},
    'execution_followup': {
        'name': '明确执行与复盘',
        'origin': '来自阿里 KA 诊断、培训与接口人推进实践；止损、回传和扩围约束为本轮补强。'},
}
STATUSES = {'applied': '已采用', 'adapted': '按场景改写',
            'not_applicable': '本轮不适用', 'needs_data': '材料不足，暂不采用'}
TARGET_SECTIONS = {'money', 'findings', 'actions', 'charts', 'audience_plan'}


def _text(value, path, *, optional=False):
    if value is None and optional:
        return ''
    if not isinstance(value, str) or (not optional and not value.strip()) or len(value) > 10000:
        raise ValueError(path + ' 须为非空文字且不超过10000字')
    return value.strip()


def _citation_shape(evidence, path):
    """For direct export only; source existence is checked by the run binder."""
    if not isinstance(evidence, list) or len(evidence) > 100:
        raise ValueError(path + ' 须为证据列表')
    result = []
    for item in evidence:
        if not isinstance(item, dict):
            raise ValueError(path + ' 须包含材料与定位')
        citation = {key: _text(item.get(key), path + '.' + key) for key in ('material', 'locator')}
        if not LOCATORS.fullmatch(citation['locator']):
            raise ValueError(path + ' 的定位格式无效')
        if citation not in result:
            result.append(citation)
    return result


def validate_usage(records, report, *, bind_evidence=None):
    """Resolve applicability and output targets; never prove business semantics.

    A run supplies bind_evidence to verify locations against its frozen material.
    Direct exporters can check structure, but have no authority to verify sources.
    """
    if not isinstance(records, list) or len(records) != len(METHODS):
        raise ValueError('method_usage 须逐一记录四种方法的适用结果')
    normalized = {}
    for item in records:
        if not isinstance(item, dict):
            raise ValueError('method_usage 每项须为对象')
        method = item.get('method')
        if not isinstance(method, str) or method not in METHODS or method in normalized:
            raise ValueError('method_usage 方法须来自固定四项且不能重复')
        status = item.get('status')
        if not isinstance(status, str) or status not in STATUSES:
            raise ValueError('method_usage.status 须说明采用、改写、不适用或缺数据')
        applied = status in ('applied', 'adapted')
        bound = {'method': method, 'status': status,
                 'reason': _text(item.get('reason'), 'method_usage.reason'),
                 'decision': _text(item.get('decision'), 'method_usage.decision'),
                 'evidence_summary': _text(item.get('evidence_summary'),
                                           'method_usage.evidence_summary', optional=True)}
        citations = _citation_shape(item.get('evidence', []), 'method_usage.evidence')
        if applied and not citations:
            raise ValueError('method_usage 已采用或改写的方法须给本轮证据')
        bound['evidence'] = bind_evidence(citations) if bind_evidence is not None else citations
        targets = item.get('targets', [])
        if (not isinstance(targets, list) or len(targets) > 100 or (applied and not targets)):
            raise ValueError('method_usage.targets 已采用或改写的方法须指向真实输出')
        bound['targets'] = []
        for target in targets:
            if not isinstance(target, dict):
                raise ValueError('method_usage.target 须为 section/index 对象')
            section, index = target.get('section'), target.get('index')
            if not isinstance(section, str) or section not in TARGET_SECTIONS:
                raise ValueError('method_usage.target.section 不支持该输出区块')
            section_value = report.get(section)
            limit = (1 if isinstance(section_value, dict) else 0) if section == 'money' else (
                len(section_value) if isinstance(section_value, list) else 0)
            if type(index) is not int or not 0 <= index < limit:
                raise ValueError('method_usage.target.index 必须指向本报告中存在的输出')
            anchor = {'section': section, 'index': index}
            if anchor not in bound['targets']:
                bound['targets'].append(anchor)
        normalized[method] = bound
    return [normalized[method] for method in METHODS]
