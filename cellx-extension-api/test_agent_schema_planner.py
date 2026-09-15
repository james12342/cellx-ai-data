import copy
import json
from pathlib import Path
import unittest

from agent_schema_planner import SchemaPlanningAPI, delete_impact, physical_table_name, preview_schema, validate_manifest


class PlannerTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((Path(__file__).parent / 'examples/agent-schema-preview.json').read_text())
        self.manifest = self.data['manifest']
        self.snapshot = self.data['snapshot']

    def preview(self):
        return preview_schema('demo_company', self.manifest, self.snapshot)

    def impact(self):
        return delete_impact('demo_company', 'research_agent', self.snapshot)

    def test_shared_reuse_additive_field(self):
        result = self.preview()
        self.assertFalse(result['can_apply'])
        self.assertEqual(result['blockers'], [])
        self.assertEqual(sum(a['action'] == 'reuse_table' for a in result['actions']), 2)
        self.assertEqual(sum(a['action'] == 'propose_add_nullable_field' for a in result['actions']), 1)
        self.assertEqual(self.manifest, self.data['manifest'])

    def test_second_agent_reuses_shared_not_exclusive(self):
        self.manifest['agent_id'] = 'sales_agent'
        result = self.preview()
        self.assertEqual(sum(a['action'] == 'reuse_table' for a in result['actions']), 1)
        self.assertEqual(sum(a['action'] == 'propose_create_table' for a in result['actions']), 1)

    def test_names_deterministic_and_tenant_isolated(self):
        self.snapshot['tables'] = []
        first = self.preview()
        self.assertEqual(first, self.preview())
        self.manifest['tenant_id'] = self.snapshot['tenant_id'] = 'other_company'
        second = preview_schema('other_company', self.manifest, self.snapshot)
        self.assertNotEqual(first['actions'][0]['physical_name'], second['actions'][0]['physical_name'])

    def test_names_have_safe_readable_prefix_and_length_limit(self):
        name = physical_table_name('tenant-1', 'company', 'customer', 'agent-1')
        self.assertRegex(name, r'^agent_customer_[a-f0-9]{24}$')
        self.assertEqual(name, physical_table_name('tenant-1', 'company', 'customer', 'agent-2'))
        long_name = physical_table_name('tenant-1', 'agent', 'a' * 48, 'agent-1')
        self.assertEqual(len(long_name), 64)
        self.assertNotEqual(long_name, physical_table_name('tenant-1', 'agent', 'a' * 47 + 'b', 'agent-1'))
        self.assertNotEqual(long_name, physical_table_name('tenant-1', 'agent', 'a' * 48, 'agent-2'))
        for invalid in ('Customer', 'order;drop', 'a-b', 'a b', 'a' * 49, ''):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                physical_table_name('tenant-1', 'agent', invalid, 'agent-1')

    def test_occupied_physical_name_blocks_creation(self):
        self.snapshot['tables'] = []
        name = physical_table_name('demo_company', 'company', 'customer', 'research_agent')
        self.snapshot['occupied_physical_names'] = [name]
        result = self.preview()
        self.assertIn({'entity_key': 'customer', 'code': 'physical_name_collision'}, result['blockers'])
        self.assertFalse(any(a.get('physical_name') == name for a in result['actions']))

    def test_cross_tenant_rejected(self):
        self.manifest['tenant_id'] = 'other_company'
        with self.assertRaises(PermissionError):
            self.preview()
        self.manifest['tenant_id'] = 'demo_company'
        self.snapshot['tables'][0]['tenant_id'] = 'other_company'
        with self.assertRaises(PermissionError):
            self.impact()

    def test_ambiguous_shared_match_blocked(self):
        self.snapshot['tables'].append(copy.deepcopy(self.snapshot['tables'][0]))
        self.assertEqual(self.preview()['blockers'][0]['code'], 'ambiguous_registry_match')

    def test_unmanaged_requires_adoption(self):
        self.snapshot['tables'][0]['managed'] = False
        self.assertEqual(self.preview()['blockers'][0]['code'], 'adoption_or_recovery_required')

    def test_type_change_and_required_addition_blocked(self):
        self.manifest['tables'][0]['fields'][1]['type'] = 'integer'
        self.manifest['tables'][0]['fields'][2]['nullable'] = False
        self.assertEqual({b['code'] for b in self.preview()['blockers']}, {'incompatible_field', 'backfill_review_required'})

    def test_omitted_fields_never_dropped(self):
        self.manifest['tables'][0]['fields'] = self.manifest['tables'][0]['fields'][:1]
        self.assertFalse(any('drop' in a['action'] for a in self.preview()['actions']))

    def test_input_not_mutated(self):
        old = copy.deepcopy(self.data)
        self.preview()
        self.impact()
        self.assertEqual(old, self.data)

    def test_legacy_agent_id_allowed(self):
        self.manifest['agent_id'] = 'workflow-1234-example'
        self.assertFalse(self.preview()['can_apply'])

    def test_unrecognized_manifest_attributes_rejected(self):
        self.manifest['tables'][0]['fields'][1]['default_sql'] = 'NOW()'
        with self.assertRaises(ValueError):
            self.preview()

    def test_default_delete_retains_everything(self):
        result = self.impact()
        self.assertFalse(result['can_execute'])
        self.assertEqual(result['default_action'], 'soft_delete_agent_keep_data')
        self.assertTrue(all(t['default_action'] == 'retain_table_unlink_agent' for t in result['tables']))
        shared, exclusive = result['tables']
        self.assertTrue(result['data_preserved'])
        self.assertFalse(result['cleanup_available'])
        self.assertEqual(result['admin_cleanup'], 'future_separate_admin_task')
        self.assertNotIn('requires_second_confirmation_for_drop', result)
        self.assertEqual(shared['usage_after_unlink'], 'retained_in_use')
        self.assertEqual(shared['creator_agent_id'], 'sales_agent')
        self.assertEqual(shared['field_consumers']['email'], ['sales_agent', 'research_agent'])
        self.assertIsNone(shared['row_count'])
        self.assertEqual(exclusive['usage_after_unlink'], 'unused_orphaned')
        self.assertEqual(exclusive['row_count'], 120)
        for table in result['tables']:
            self.assertTrue(table['data_preserved'])
            self.assertTrue(table['physical_name'].startswith('agent_'))
            self.assertNotIn('drop_candidate', table)
            self.assertNotIn('drop_blockers', table)

    def test_extra_reference_or_dependency_marks_retained_in_use(self):
        table = self.snapshot['tables'][1]
        table['references'].append('sales_agent')
        table['dependents'] = ['another_table_fk']
        result = self.impact()['tables'][1]
        self.assertEqual(result['usage_after_unlink'], 'retained_in_use')
        self.assertTrue(result['data_preserved'])
        self.assertIn('referenced_by_other_agents', result['retention_notes'])
        self.assertIn('inbound_dependencies', result['retention_notes'])

    def test_missing_inventory_or_retention_requires_review_not_orphan_label(self):
        for key in ('dependency_inventory_complete', 'retention_hold'):
            with self.subTest(key=key):
                original = self.snapshot['tables'][1].pop(key)
                self.assertEqual(self.impact()['tables'][1]['usage_after_unlink'], 'retained_review_required')
                self.snapshot['tables'][1][key] = original

    def test_bad_manifest_types_ids_duplicates_and_relationships(self):
        variants = []
        for path, value in [('type', 'varchar(2); DROP TABLE x'), ('nullable', 'false'), ('name', 'Email')]:
            item = copy.deepcopy(self.manifest)
            item['tables'][0]['fields'][1][path] = value
            variants.append(item)
        duplicate = copy.deepcopy(self.manifest)
        duplicate['tables'].append(copy.deepcopy(duplicate['tables'][0]))
        variants.append(duplicate)
        relation = copy.deepcopy(self.manifest)
        relation['relationships'][0]['on_delete'] = 'cascade'
        variants.append(relation)
        for variant in variants:
            with self.subTest(variant=variant), self.assertRaises(ValueError):
                validate_manifest(variant)

    def test_api_auth_and_mutations_fail_closed(self):
        api = SchemaPlanningAPI(None)
        self.assertEqual(api.handle('preview_schema', None, 'research_agent', {})[0], 401)
        principal = {'tenant_id': 'demo_company', 'user_id': 'user_one', 'capabilities': []}
        self.assertEqual(api.handle('preview_schema', principal, 'research_agent', {})[0], 403)
        principal['capabilities'] = ['schema:preview']
        for operation in ('apply_schema', 'confirm_delete'):
            self.assertEqual(api.handle(operation, principal, 'research_agent', {})[0], 501)
        for body in ({'mode': 'drop_exclusive'}, {'mode': 'keep_data', 'table_ids': ['table_recommendation']}):
            status, result = api.handle('confirm_delete', principal, 'research_agent', body)
            self.assertEqual(status, 400)
            self.assertEqual(result['code'], 'agent_delete_must_keep_data')

    def test_api_uses_server_inventory_not_payload(self):
        snapshot = self.snapshot
        class Repository:
            def can_access_agent(self, tenant_id, user_id, agent_id):
                return tenant_id == 'demo_company' and agent_id == 'research_agent'
            def snapshot(self, tenant_id):
                return snapshot
        api = SchemaPlanningAPI(Repository())
        principal = {'tenant_id': 'demo_company', 'user_id': 'user_one', 'capabilities': ['schema:preview']}
        status, body = api.handle('preview_schema', principal, 'research_agent', {'manifest': self.manifest, 'snapshot': {}})
        self.assertEqual(status, 200)
        self.assertEqual(body['inventory_revision'], 7)
        self.assertEqual(api.handle('delete_impact', principal, 'foreign_agent', {})[0], 404)
        self.manifest['tenant_id'] = 'other_company'
        self.assertEqual(api.handle('preview_schema', principal, 'research_agent', {'manifest': self.manifest})[0], 403)


if __name__ == '__main__':
    unittest.main()
