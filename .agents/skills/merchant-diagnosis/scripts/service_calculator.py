"""Bounded decimal arithmetic; citations validate location, not business meaning."""
import ast
import copy
from decimal import Decimal, DecimalException, ROUND_HALF_UP, localcontext
import re

from validate import LOCATORS, valid_location

FUNCTIONS = {'sum', 'mean', 'min', 'max', 'abs', 'round'}
LIMIT = Decimal('1e100')


def _decimal(value):
    if type(value) not in (int, float):
        raise ValueError('变量或常量必须是有限数字，不接受布尔值或数字字符串')
    return _bounded(Decimal(str(value)))


def _bounded(result):
    if not result.is_finite() or abs(result) > LIMIT or (result and abs(result) < Decimal('1e-100')):
        raise ValueError('数值超出可计算范围')
    return result


def _tree(expression, variables):
    if not isinstance(expression, str) or not expression.strip() or len(expression) > 2000:
        raise ValueError('表达式为空或超出长度限制')
    try:
        root = ast.parse(expression, mode='eval').body
    except (SyntaxError, ValueError, RecursionError):
        raise ValueError('表达式语法无效') from None
    used, count = set(), [0]

    def check(node, depth=0):
        count[0] += 1
        if depth > 20 or count[0] > 200:
            raise ValueError('表达式过深或过大')
        if isinstance(node, ast.Constant):
            node.decimal_value = _decimal(node.value)
            if type(node.value) is float:
                literal = ast.get_source_segment(expression, node).replace('_', '')
                node.decimal_value = _bounded(Decimal(literal))
        elif isinstance(node, ast.Name):
            if node.id not in variables:
                raise ValueError('表达式引用未声明变量')
            used.add(node.id)
        elif isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            check(node.left, depth + 1)
            check(node.right, depth + 1)
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            check(node.operand, depth + 1)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FUNCTIONS:
            if node.keywords or not 1 <= len(node.args) <= 100:
                raise ValueError('函数参数无效')
            if node.func.id == 'abs' and len(node.args) != 1:
                raise ValueError('abs 只接受一个参数')
            if node.func.id == 'round' and len(node.args) not in (1, 2):
                raise ValueError('round 只接受一到两个参数')
            for item in node.args:
                check(item, depth + 1)
        else:
            raise ValueError('表达式含未允许的语法')
    check(root)
    return root, used


def _evaluate(node, variables):
    if isinstance(node, ast.Constant):
        value = node.decimal_value
    elif isinstance(node, ast.Name):
        value = variables[node.id]
    elif isinstance(node, ast.UnaryOp):
        value = _evaluate(node.operand, variables)
        value = -value if isinstance(node.op, ast.USub) else value
    elif isinstance(node, ast.BinOp):
        left, right = _evaluate(node.left, variables), _evaluate(node.right, variables)
        if isinstance(node.op, ast.Add):
            value = left + right
        elif isinstance(node.op, ast.Sub):
            value = left - right
        elif isinstance(node.op, ast.Mult):
            value = left * right
        else:
            value = left / right
    else:
        args = [_evaluate(arg, variables) for arg in node.args]
        function = node.func.id
        if function == 'sum':
            value = sum(args, Decimal(0))
        elif function == 'mean':
            value = sum(args, Decimal(0)) / len(args)
        elif function == 'min':
            value = min(args)
        elif function == 'max':
            value = max(args)
        elif function == 'abs':
            value = abs(args[0])
        else:
            digits = args[1] if len(args) == 2 else Decimal(0)
            if digits != digits.to_integral_value() or not -20 <= digits <= 20:
                raise ArithmeticError('round 精度须为 -20 到 20 的整数')
            value = args[0].quantize(Decimal(1).scaleb(-int(digits)), rounding=ROUND_HALF_UP)
    if not value.is_finite() or abs(value) > LIMIT or (value and abs(value) < Decimal('1e-100')):
        raise ArithmeticError('计算结果超出范围')
    return value


def calculate_requests(requests, materials):
    """Return ok/unknown/error results; malformed or unsafe requests raise ValueError.

    Functions accept positional scalar arguments (e.g. mean(a,b), round(a,2)).
    Unknown variables used by a formula propagate null; unused nulls do not.
    Decimal precision is 50 digits; round uses round-half-up. Output JSON
    numbers may round decimal fractions when represented as Python floats.
    """
    if not isinstance(requests, list) or len(requests) > 100:
        raise ValueError('计算请求须为列表且最多 100 项')
    material_list = materials.get('materials', []) if isinstance(materials, dict) else materials
    if not isinstance(material_list, list):
        raise ValueError('材料清单无效')
    sources = {}
    for item in material_list:
        if (not isinstance(item, dict) or not isinstance(item.get('name'), str)
                or not isinstance(item.get('fragments'), list) or item['name'] in sources
                or any(not isinstance(f, dict) or not isinstance(f.get('locator'), str) for f in item['fragments'])):
            raise ValueError('材料清单或定位无效')
        sources[item['name']] = item
    results, ids = [], set()
    for request in requests:
        if not isinstance(request, dict):
            raise ValueError('计算请求必须为对象')
        for key in ('id', 'unit', 'purpose'):
            if not isinstance(request.get(key), str) or not request[key].strip() or len(request[key]) > 2000:
                raise ValueError('计算请求必填字段无效')
        if request['id'] in ids:
            raise ValueError('计算编号重复')
        ids.add(request['id'])
        variables = request.get('variables')
        if not isinstance(variables, dict) or len(variables) > 100:
            raise ValueError('计算变量须为对象且最多 100 项')
        values, assumptions = {}, []
        for name, item in variables.items():
            if (not isinstance(name, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,63}', name)
                    or name in FUNCTIONS or not isinstance(item, dict) or 'value' not in item):
                raise ValueError('变量名称或定义无效')
            evidence, assumption = item.get('evidence', []), item.get('assumption')
            if not isinstance(evidence, list) or len(evidence) > 1000:
                raise ValueError('变量引用无效')
            if assumption is not None and (not isinstance(assumption, str) or not assumption.strip() or len(assumption) > 2000):
                raise ValueError('假设说明无效')
            if not evidence and not assumption:
                raise ValueError('变量须提供材料引用或明确假设')
            for citation in evidence:
                if not isinstance(citation, dict):
                    raise ValueError('变量引用无效')
                material, locator = citation.get('material'), citation.get('locator')
                if (not isinstance(material, str) or material not in sources or not isinstance(locator, str)
                        or not LOCATORS.fullmatch(locator)
                        or not valid_location(material, material + '／' + locator, sources[material], sources)):
                    raise ValueError('变量引用的材料或定位不存在')
            if assumption:
                assumptions.append({'variable': name, 'assumption': assumption})
            values[name] = None if item['value'] is None else _decimal(item['value'])
        tree, used = _tree(request.get('expression'), variables)
        missing = sorted(name for name in used if values[name] is None)
        result = {key: copy.deepcopy(request[key]) for key in ('id','expression','variables','unit','purpose')}
        result.update(status='unknown' if missing else 'ok', value=None, missing_variables=missing, assumptions=assumptions)
        if not missing:
            try:
                with localcontext() as context:
                    context.prec = 50
                    value = _evaluate(tree, values)
                result['value'] = int(value) if value == value.to_integral_value() else float(value)
            except (DecimalException, ArithmeticError):
                result['status'] = 'error'
                result['error'] = '除零、精度参数无效或结果超出范围；未生成数值'
        results.append(result)
    return results
