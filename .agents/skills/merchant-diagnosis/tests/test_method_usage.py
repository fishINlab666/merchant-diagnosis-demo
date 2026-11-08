"""Method evidence must point to this report and this run, not decorative badges."""
import copy
import unittest

from test_quick_contract import citation, materials, method_records, report, request
from quick_contract import bind_report
from service_calculator import calculate_requests


class MethodUsageTests(unittest.TestCase):
    def setUp(self):
        self.calculations = calculate_requests([request()], materials())
        self.report = report()
        self.report['method_usage'] = method_records()

    def bind(self, value=None, **options):
        return bind_report(self.report if value is None else value, materials(), self.calculations,
                           **options)

    def test_record_is_preserved_and_all_four_methods_have_specific_status(self):
        bound = self.bind()
        self.assertEqual(method_records(), bound.get('method_usage'))
        self.assertEqual(bound, self.bind(bound))

    def test_record_order_is_canonical_and_model_cannot_override_method_provenance(self):
        self.report['method_usage'].reverse()
        for item in self.report['method_usage']:
            item.update(name='模型自称的方法', origin='模型捏造的历史实践')
        self.assertEqual(method_records(), self.bind()['method_usage'])

    def test_direct_export_validator_checks_shape_without_claiming_material_verification(self):
        from method_usage import validate_usage
        result = validate_usage(method_records(), self.report)
        self.assertEqual(method_records(), result)
        for citation_value in ([{'material': '', 'locator': 'row:2'}],
                               [{'material': 'weekly.csv', 'locator': 'unstructured'}], 'weekly.csv'):
            records = method_records()
            records[2]['evidence'] = citation_value
            with self.subTest(citation=citation_value), self.assertRaises(ValueError):
                validate_usage(records, self.report)

    def test_new_contract_requires_method_records_but_direct_legacy_binding_stays_compatible(self):
        old = report()
        self.assertNotIn('method_usage', self.bind(old))
        with self.assertRaisesRegex(ValueError, 'method_usage'):
            self.bind(old, require_method_usage=True)

    def test_missing_duplicate_or_unknown_methods_are_rejected(self):
        for mutation in ('missing', 'duplicate', 'unknown'):
            value = copy.deepcopy(self.report)
            if mutation == 'missing':
                value['method_usage'].pop()
            else:
                value['method_usage'][0]['method'] = ('tool_mix' if mutation == 'duplicate' else 'invented')
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.bind(value)

    def test_applied_or_adapted_requires_real_evidence_and_at_least_one_target(self):
        for status in ('applied', 'adapted'):
            for field in ('evidence', 'targets'):
                value = copy.deepcopy(self.report)
                value['method_usage'][2]['status'] = status
                value['method_usage'][2][field] = []
                with self.subTest(status=status, field=field), self.assertRaises(ValueError):
                    self.bind(value)

    def test_evidence_cannot_reference_another_file_or_nonexistent_row(self):
        for evidence in ([{'material': 'missing.csv', 'locator': 'row:2'}],
                         [{'material': 'weekly.csv', 'locator': 'row:900'}]):
            value = copy.deepcopy(self.report)
            value['method_usage'][2]['evidence'] = evidence
            with self.subTest(evidence=evidence), self.assertRaisesRegex(ValueError, '定位'):
                self.bind(value)

    def test_targets_must_resolve_and_indices_are_not_booleans_or_negative(self):
        targets = [{'section': 'money', 'index': 1}, {'section': 'money', 'index': False},
                   {'section': 'findings', 'index': -1}, {'section': 'actions', 'index': 10},
                   {'section': 'charts', 'index': 1}, {'section': 'audience_plan', 'index': 0},
                   {'section': 'followup', 'index': 0}, {'section': 'actions', 'index': '0'}]
        for target in targets:
            value = copy.deepcopy(self.report)
            value['method_usage'][2]['targets'] = [target]
            with self.subTest(target=target), self.assertRaisesRegex(ValueError, 'target'):
                self.bind(value)

    def test_missing_data_does_not_force_all_methods_to_be_applied(self):
        bound = self.bind(require_method_usage=True)
        self.assertEqual('needs_data', bound['method_usage'][1]['status'])
        self.assertEqual([], bound['method_usage'][1]['targets'])
        self.assertEqual([], bound['gaps'])

    def test_status_reason_and_decision_must_be_explicit(self):
        for field, replacement in [('status', 'maybe'), ('reason', ' '), ('decision', '')]:
            value = copy.deepcopy(self.report)
            value['method_usage'][0][field] = replacement
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.bind(value)

    def audience(self):
        return {'audience': '近30天首购客', 'product': '双人主食组合', 'benefit': '加购小食券',
                'decision': '先覆盖试点门店首购客', 'validation': '按组回传核销和券后贡献',
                'basis': '本周首购客仍以单品为主', 'evidence': citation(),
                'economics': {'label': '试点贡献', 'unit': '元', 'calc_id': 'c1', 'value': 999}}

    def test_audience_plan_binds_real_calculation_and_targets(self):
        self.report['audience_plan'] = [self.audience()]
        self.report['method_usage'][1].update(status='applied', evidence=citation(),
            targets=[{'section': 'audience_plan', 'index': 0}])
        bound = self.bind()
        self.assertEqual(60, bound.get('audience_plan', [{}])[0].get('economics', {}).get('value'))
        self.assertEqual(citation(), bound['audience_plan'][0]['economics']['evidence'])
        self.assertEqual(bound, self.bind(bound))

    def test_audience_plan_rejects_unsupported_money_missing_proof_and_blank_decisions(self):
        for mutation in ('money', 'evidence', 'decision', 'unit', 'too_many'):
            value = copy.deepcopy(self.report)
            row = self.audience()
            if mutation == 'money':
                row['economics'].pop('calc_id')
                row['economics']['evidence'] = citation()
            elif mutation == 'evidence':
                row['evidence'] = []
            elif mutation == 'decision':
                row['decision'] = ''
            elif mutation == 'unit':
                row['economics']['unit'] = '万元'
            value['audience_plan'] = [row] * (7 if mutation == 'too_many' else 1)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.bind(value)

    def test_audience_can_have_no_numeric_economics_without_fabricating_zero(self):
        row = self.audience()
        row.pop('economics')
        self.report['audience_plan'] = [row]
        bound = self.bind()
        self.assertEqual([row], bound.get('audience_plan'))

    def test_audience_basis_is_optional_and_preserved_as_public_evidence_summary(self):
        row = self.audience()
        self.report['audience_plan'] = [row]
        self.assertEqual(row['basis'], self.bind()['audience_plan'][0].get('basis'))
        row.pop('basis')
        self.assertEqual('', self.bind()['audience_plan'][0].get('basis'))


if __name__ == '__main__':
    unittest.main()
