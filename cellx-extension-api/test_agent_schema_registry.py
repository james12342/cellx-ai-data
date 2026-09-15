from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError

import server
from agent_schema_registry import AgentSchemaRegistry, RegistryError, handle_registry_request


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'registry.sqlite3'
        self.bound = False
        self.registry = AgentSchemaRegistry(self.path, lambda _: self.bound)
        self.registry.dispatch('tenants/create', {'tenant_id': 'company_one'})
        self.agent = self.registry.dispatch('agents/create', {'tenant_id': 'company_one'})['agent_id']
        self.scope = {'tenant_id': 'company_one', 'agent_id': self.agent}
        self.manifest = {'version': 1, **self.scope, 'tables': [
            {'entity_key': 'customer', 'scope': 'company', 'fields': [
                {'name': 'id', 'type': 'uuid', 'nullable': False},
                {'name': 'email', 'type': 'string', 'nullable': True}]}], 'relationships': []}

    def tearDown(self):
        self.temp.cleanup()

    def save(self, version=0):
        return self.registry.dispatch('manifest/save', {**self.scope, 'expected_version': version, 'manifest': self.manifest})

    def planned(self, kind='schema'):
        return self.registry.dispatch('schema/preview' if kind == 'schema' else 'delete-impact', self.scope)

    def plan_body(self, plan):
        return {**self.scope, 'plan_id': plan['plan_id'], 'plan_hash': plan['plan_hash']}

    def assert_code(self, code, fn):
        with self.assertRaises(RegistryError) as error:
            fn()
        self.assertEqual(error.exception.code, code)

    def test_registry_reopens_and_never_materializes_business_tables(self):
        result = self.save()
        self.assertEqual(result['version'], 1)
        table = result['tables'][0]
        self.assertTrue(table['physical_name'].startswith('agent_customer_'))
        self.assertEqual(table['state'], 'planned')
        self.assertIsNone(table['physical_exists'])
        reopened = AgentSchemaRegistry(self.path, lambda _: False)
        with reopened.connect() as db:
            self.assertEqual(reopened.snapshot(db, 'company_one')['tables'][0]['physical_name'], table['physical_name'])
            names = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertNotIn(table['physical_name'], names)
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 1)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM agent_revisions').fetchone()[0], 1)

    def test_existing_unrelated_database_is_not_migrated(self):
        path = Path(self.temp.name) / 'unrelated.sqlite3'
        with closing(sqlite3.connect(path)) as db:
            with db:
                db.execute('CREATE TABLE customer_data(id INTEGER)')
        self.assert_code('not_an_agent_schema_registry', lambda: AgentSchemaRegistry(path))
        with closing(sqlite3.connect(path)) as db:
            self.assertEqual([r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")], ['customer_data'])

    def test_shared_reuse_and_tenant_isolation(self):
        first = self.save()['tables'][0]['physical_name']
        second = self.registry.dispatch('agents/create', {'tenant_id': 'company_one'})['agent_id']
        manifest = {**self.manifest, 'agent_id': second}
        data = self.registry.dispatch('manifest/save', {'tenant_id': 'company_one', 'agent_id': second, 'expected_version': 0, 'manifest': manifest})
        self.assertEqual(len(data['tables']), 1)
        self.assertEqual(set(data['tables'][0]['references']), {self.agent, second})
        plan = self.planned()
        self.assertEqual(plan['actions'][0]['action'], 'reuse_planned_table')
        self.registry.dispatch('tenants/create', {'tenant_id': 'company_two'})
        other = self.registry.dispatch('agents/create', {'tenant_id': 'company_two'})['agent_id']
        manifest = {**self.manifest, 'agent_id': other, 'tenant_id': 'company_two'}
        data = self.registry.dispatch('manifest/save', {'tenant_id': 'company_two', 'agent_id': other, 'expected_version': 0, 'manifest': manifest})
        self.assertNotEqual(first, data['tables'][0]['physical_name'])

    def test_wrong_tenant_or_manifest_cannot_access_agent(self):
        self.assert_code('agent_not_found', lambda: self.registry.dispatch('delete-impact', {**self.scope, 'tenant_id': 'company_two'}))
        self.manifest['tenant_id'] = 'company_two'
        self.assert_code('manifest_scope_mismatch', self.save)

    def test_conflict_rolls_back_registry(self):
        self.save()
        self.manifest['tables'][0]['fields'][1]['type'] = 'integer'
        self.assert_code('schema_conflict', lambda: self.save(1))
        with self.registry.connect() as db:
            self.assertEqual(db.execute('SELECT version FROM agents').fetchone()[0], 1)
            self.assertEqual(json.loads(db.execute('SELECT fields FROM table_registry').fetchone()[0])[0]['type'], 'string')

    def test_add_nullable_preserve_omitted_columns(self):
        self.save()
        self.manifest['tables'][0]['fields'].append({'name': 'industry', 'type': 'string', 'nullable': True})
        self.save(1)
        self.manifest['tables'][0]['fields'] = self.manifest['tables'][0]['fields'][:1]
        data = self.save(2)
        self.assertEqual({f['name'] for f in data['tables'][0]['fields']}, {'id', 'email', 'industry'})

    def test_apply_is_explicit_dry_run_and_no_business_driver(self):
        self.save()
        plan = self.planned()
        body = self.plan_body(plan)
        with patch.object(server, 'mysql_query', side_effect=AssertionError('No business SQL')):
            result = self.registry.dispatch('schema/apply', {**body, 'dry_run': True})
        self.assertFalse(result['executed'])
        self.assertFalse(result['business_ddl_executed'])
        self.assertFalse(result['physical_inventory_verified'])
        for value in (None, False, 'true', 1):
            self.assert_code('real_schema_apply_disabled', lambda: self.registry.dispatch('schema/apply', {**body, 'dry_run': value}))

    def test_stale_plan_version_and_hash_rejected(self):
        self.save()
        plan = self.planned()
        self.assert_code('invalid_plan', lambda: self.registry.dispatch('schema/apply', {**self.plan_body(plan), 'plan_hash': 'bad', 'dry_run': True}))
        self.save(1)
        self.assert_code('stale_or_expired_plan', lambda: self.registry.dispatch('schema/apply', {**self.plan_body(plan), 'dry_run': True}))
        self.assert_code('stale_agent_version', self.save)

    def test_expired_plan_rejected(self):
        self.save()
        plan = self.planned()
        with self.registry.connect() as db:
            db.execute('UPDATE plans SET expires_at=0')
        self.assert_code('stale_or_expired_plan', lambda: self.registry.dispatch('schema/apply', {**self.plan_body(plan), 'dry_run': True}))

    def test_soft_delete_is_retained_and_idempotent(self):
        self.save()
        plan = self.planned('delete')
        body = {**self.plan_body(plan), 'mode': 'keep_data'}
        result = self.registry.dispatch('delete', body)
        self.assertTrue(result['data_preserved'])
        self.assertEqual(result['lifecycle_scope'], 'registry_schema_draft_only')
        self.assertEqual(result['tables'][0]['registry_usage_status'], 'unused_planned')
        self.assertEqual(result, self.registry.dispatch('delete', body))
        with self.registry.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM table_registry').fetchone()[0], 1)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM agent_revisions').fetchone()[0], 1)
            self.assertEqual(db.execute('SELECT state FROM table_use').fetchone()[0], 'retained')
            self.assertEqual(db.execute('SELECT state FROM agents').fetchone()[0], 'deleted')
        self.assert_code('agent_deleted', lambda: self.save(2))

    def test_other_agent_binding_survives_delete(self):
        self.save()
        other = self.registry.dispatch('agents/create', {'tenant_id': 'company_one'})['agent_id']
        self.registry.dispatch('manifest/save', {**self.scope, 'agent_id': other, 'expected_version': 0, 'manifest': {**self.manifest, 'agent_id': other}})
        plan = self.planned('delete')
        result = self.registry.dispatch('delete', self.plan_body(plan))
        self.assertEqual(result['tables'][0]['registry_usage_status'], 'planned_in_use')
        with self.registry.connect() as db:
            self.assertEqual(db.execute("SELECT state FROM table_use WHERE agent_id=?", (other,)).fetchone()[0], 'active')

    def test_runtime_bound_or_unknown_registry_guard_blocks_delete(self):
        self.save()
        plan = self.planned('delete')
        self.bound = True
        self.assert_code('runtime_binding_requires_lifecycle_bridge', lambda: self.registry.dispatch('delete', self.plan_body(plan)))
        self.registry.runtime_guard = lambda _: (_ for _ in ()).throw(RuntimeError('Unknown runtime'))
        with self.assertRaises(RuntimeError):
            self.registry.dispatch('delete', self.plan_body(plan))
        with self.registry.connect() as db:
            self.assertEqual(db.execute('SELECT state FROM agents').fetchone()[0], 'active')

    def test_delete_cannot_accept_table_cleanup_or_destructive_mode(self):
        for body in ({**self.scope, 'mode': 'drop_exclusive'}, {**self.scope, 'table_ids': ['anything']}):
            with self.assertRaises(RegistryError):
                self.registry.dispatch('delete', body)

    def test_auth_and_feature_fail_closed_before_storage_access(self):
        def forbidden_factory():
            self.fail('Unauthenticated request accessed storage')
        for enabled, token, headers, body, expected in [
            (False, 'secret', {}, {}, 503), (True, '', {}, {}, 503),
            (True, 'secret', {}, {'adminToken': 'secret', 'role': 'admin'}, 401),
            (True, 'secret', {'X-Workflow-Admin-Token': 'wrong'}, {}, 401),
            (True, 'secret', {'X-Workflow-Admin-Token': '\u2603'}, {}, 401),
        ]:
            with self.subTest(expected=expected):
                result, status = handle_registry_request('status', headers, body, enabled=enabled, admin_token=token, factory=forbidden_factory)
                self.assertEqual(status, expected)

    def test_concurrent_shared_saves_create_single_registry_binding(self):
        other = self.registry.dispatch('agents/create', {'tenant_id': 'company_one'})['agent_id']
        errors = []
        def save(agent_id):
            try:
                self.registry.dispatch('manifest/save', {**self.scope, 'agent_id': agent_id, 'expected_version': 0, 'manifest': {**self.manifest, 'agent_id': agent_id}})
            except Exception as exc:
                errors.append(exc)
        threads = [threading.Thread(target=save, args=(agent,)) for agent in (self.agent, other)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(errors, [])
        with self.registry.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM table_registry').fetchone()[0], 1)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM table_use').fetchone()[0], 2)


class RegistryHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.patches = patch.multiple(server, AGENT_SCHEMA_ENABLED=True,
                                     AGENT_SCHEMA_DB=str(Path(self.temp.name) / 'registry.sqlite3'),
                                     WORKFLOW_SCHEDULE_DB=str(Path(self.temp.name) / 'schedule.sqlite3'),
                                     WORKFLOW_MANAGEMENT_TOKEN='test-only-secret')
        self.patches.start()
        self.http = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        self.worker = threading.Thread(target=self.http.serve_forever)
        self.worker.start()

    def tearDown(self):
        self.http.shutdown()
        self.worker.join()
        self.http.server_close()
        self.patches.stop()
        self.temp.cleanup()

    def request(self, operation='status', body=None, token='test-only-secret', **headers):
        if token:
            headers['X-Workflow-Admin-Token'] = token
        data = json.dumps(body).encode() if body is not None else None
        req = Request(f'http://127.0.0.1:{self.http.server_port}/ext-api/agent-schemas/{operation}', data=data, headers=headers)
        try:
            r = urlopen(req, timeout=5)
        except HTTPError as error:
            r = error
        return r.status, json.load(r), r.headers

    def test_http_auth_status_and_cache(self):
        self.assertEqual(self.request(token=None)[0], 401)
        self.assertFalse(Path(server.AGENT_SCHEMA_DB).exists())
        status, body, headers = self.request()
        self.assertEqual(status, 200)
        self.assertTrue(body['preview_enabled'])
        self.assertFalse(body['real_apply_enabled'])
        self.assertEqual(headers.get('Cache-Control'), 'no-store')
        self.assertIsNone(headers.get('Access-Control-Allow-Origin'))
        self.assertEqual(self.request(Origin='https://untrusted.example')[0], 403)

    def test_http_create_tenant_agent_then_guarded_api(self):
        self.assertEqual(self.request('tenants/create', {'tenant_id': 'company_one'})[0], 200)
        status, agent, _ = self.request('agents/create', {'tenant_id': 'company_one'})
        self.assertEqual(status, 200)
        self.assertTrue(agent['agent_id'].startswith('asr_'))
        self.assertEqual(self.request('schema/apply', {'tenant_id': 'company_one', 'agent_id': agent['agent_id'], 'dry_run': False})[0], 501)
        self.assertEqual(self.request('delete-impact', {'tenant_id': 'company_two', 'agent_id': agent['agent_id']})[0], 404)

    def test_http_full_dry_run_and_soft_delete_round_trip(self):
        self.request('tenants/create', {'tenant_id': 'company_one'})
        _, agent, _ = self.request('agents/create', {'tenant_id': 'company_one'})
        scope = {'tenant_id': 'company_one', 'agent_id': agent['agent_id']}
        manifest = {'version': 1, **scope, 'tables': [{'entity_key': 'customer', 'scope': 'company',
                    'fields': [{'name': 'id', 'type': 'uuid', 'nullable': False}]}]}
        with patch.object(server, 'mysql_query', side_effect=AssertionError('No MySQL calls')):
            self.assertEqual(self.request('manifest/save', {**scope, 'expected_version': 0, 'manifest': manifest})[0], 200)
            status, plan, _ = self.request('schema/preview', scope)
            self.assertEqual(status, 200)
            status, result, _ = self.request('schema/apply', {**scope, 'plan_id': plan['plan_id'], 'plan_hash': plan['plan_hash'], 'dry_run': True})
            self.assertEqual(status, 200)
            self.assertFalse(result['executed'])
            status, plan, _ = self.request('delete-impact', scope)
            self.assertEqual(status, 200)
            status, result, _ = self.request('delete', {**scope, 'plan_id': plan['plan_id'], 'plan_hash': plan['plan_hash'], 'mode': 'keep_data'})
            self.assertEqual(status, 200)
            self.assertTrue(result['data_preserved'])
            self.assertFalse(result['business_ddl_executed'])

    def test_registry_path_cannot_alias_scheduler_database(self):
        with patch.object(server, 'AGENT_SCHEMA_DB', server.WORKFLOW_SCHEDULE_DB):
            self.assertEqual(self.request()[0], 503)
        self.assertFalse(Path(server.WORKFLOW_SCHEDULE_DB).exists())

    def test_disabled_feature_and_request_size(self):
        with patch.object(server, 'AGENT_SCHEMA_ENABLED', False):
            self.assertEqual(self.request()[0], 503)
        self.assertFalse(Path(server.AGENT_SCHEMA_DB).exists())
        self.assertEqual(self.request('manifest/save', {'large': 'x' * 262145})[0], 413)

    def test_runtime_guard_is_read_only_and_fail_closed(self):
        self.assertFalse(server.agent_schema_runtime_bound('asr_test'))
        path = Path(server.WORKFLOW_SCHEDULE_DB)
        path.write_bytes(b'not a database')
        self.assertTrue(server.agent_schema_runtime_bound('asr_test'))


if __name__ == '__main__':
    unittest.main()
