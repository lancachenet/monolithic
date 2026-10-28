import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

MODULE_PATH = Path(__file__).parents[1] / 'overlay' / 'scripts' / 'refresh_cdn_upstreams.py'
SPEC = importlib.util.spec_from_file_location('origin_upstreams', MODULE_PATH)
origin = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(origin)


class OriginUpstreamTests(unittest.TestCase):
    def setUp(self):
        patch = mock.patch.object(origin, 'HOSTS', (('one.example.net', 'lancache_seed_one'), ('two.example.net', 'lancache_seed_two')))
        patch.start()
        self.addCleanup(patch.stop)
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'upstreams.conf'
        self.records = {host: ['192.0.2.2', '192.0.2.1'] for host, _ in origin.HOSTS}
        self.calls = []

    def resolve(self, host):
        return self.records[host]

    def nginx_run(self, args, **kwargs):
        self.calls.append(args)
        return subprocess.CompletedProcess(args, 0, '', '')

    def test_bootstrap_writes_resolved_pools_without_reloading_nginx(self):
        self.assertTrue(origin.refresh(self.path, self.resolve, self.nginx_run, bootstrap=True))
        value = self.path.read_text()
        self.assertIn('server 192.0.2.1:80', value)
        self.assertIn('keepalive 64;', value)
        self.assertEqual(self.calls, [])

    def test_dns_reordering_does_not_reload_the_running_service(self):
        origin.refresh(self.path, self.resolve, self.nginx_run, bootstrap=True)
        for host in self.records:
            self.records[host].reverse()
        self.assertFalse(origin.refresh(self.path, self.resolve, self.nginx_run))
        self.assertEqual(self.calls, [])

    def test_dns_failure_preserves_the_last_good_configuration(self):
        self.path.write_text('last good configuration\n')
        def unavailable(host):
            raise OSError('DNS unavailable')
        with self.assertRaises(OSError):
            origin.refresh(self.path, unavailable, self.nginx_run)
        self.assertEqual(self.path.read_text(), 'last good configuration\n')
        self.assertEqual(self.calls, [])

    def test_invalid_nginx_configuration_is_rolled_back_without_reload(self):
        self.path.write_text('last good configuration\n')
        def reject(args, **kwargs):
            self.calls.append(args)
            return subprocess.CompletedProcess(args, 1, '', 'invalid configuration')
        with self.assertRaises(RuntimeError):
            origin.refresh(self.path, self.resolve, reject)
        self.assertEqual(self.path.read_text(), 'last good configuration\n')
        self.assertEqual(self.calls, [['nginx', '-t']])

    def test_dns_change_is_validated_before_graceful_reload(self):
        self.path.write_text('last good configuration\n')
        self.assertTrue(origin.refresh(self.path, self.resolve, self.nginx_run))
        self.assertEqual(self.calls, [['nginx', '-t'], ['nginx', '-s', 'reload']])

    def test_reload_failure_restores_the_previous_file(self):
        self.path.write_text('last good configuration\n')
        def fail_reload(args, **kwargs):
            return subprocess.CompletedProcess(args, int('-s' in args), '', 'reload failed')
        with self.assertRaises(RuntimeError):
            origin.refresh(self.path, self.resolve, fail_reload)
        self.assertEqual(self.path.read_text(), 'last good configuration\n')

    def test_invalid_resolver_output_cannot_enter_nginx_configuration(self):
        self.path.write_text('last good configuration\n')
        with self.assertRaises(ValueError):
            origin.refresh(self.path, lambda _: ['192.0.2.1; include /tmp/evil'], self.nginx_run)
        self.assertEqual(self.path.read_text(), 'last good configuration\n')

    def test_offline_first_boot_falls_back_to_existing_dynamic_proxy_routing(self):
        def unavailable(host):
            raise OSError('DNS unavailable')
        origin.bootstrap(self.path, unavailable, self.nginx_run)
        self.assertIn('default $host;', self.path.read_text())
        self.assertNotIn('upstream ', self.path.read_text())
        self.assertEqual(self.calls, [])

    def test_offline_restart_preserves_previously_resolved_servers(self):
        self.path.write_text('last good configuration\n')
        def unavailable(host):
            raise OSError('DNS unavailable')
        origin.bootstrap(self.path, unavailable, self.nginx_run)
        self.assertEqual(self.path.read_text(), 'last good configuration\n')

    def test_warm_boot_reuses_saved_addresses_before_attempting_network_dns(self):
        origin.refresh(self.path, self.resolve, self.nginx_run, bootstrap=True)
        calls = []
        def slow_dns(host):
            calls.append(host)
            raise OSError('DNS unavailable during startup')
        origin.bootstrap(self.path, slow_dns, self.nginx_run)
        self.assertEqual(calls, [])
        self.assertIn('server 192.0.2.1:80', self.path.read_text())

    def test_observed_cdn_domains_are_discovered_without_storing_signed_urls(self):
        log = self.path.parent / 'access.log'
        log.write_text('[steam] 192.0.2.12 / - - - [27/Oct/2026:23:00:00 +0800] "GET /depot/1/chunk/abc?authkey=do-not-store HTTP/1.1" 200 123 "-" "Valve/Steam HTTP Client 1.0" "MISS" "NEW-EDGE.EXAMPLE.NET:80" "-"\n')
        self.assertEqual(origin.discover_hosts(log), ['new-edge.example.net'])

    def test_discovery_ignores_local_trigger_and_invalid_hostnames(self):
        log = self.path.parent / 'access.log'
        log.write_text('\n'.join('[steam] client / - - - [date] "GET /depot/1/chunk/abc HTTP/1.1" 200 123 "-" "agent" "MISS" "' + host + '" "-"'
                                 for host in ['lancache.steamcontent.com', 'localhost', '192.168.0.57', 'bad; include evil']))
        self.assertEqual(origin.discover_hosts(log), [])

    def test_additional_cdn_gets_a_pool_without_being_hardcoded(self):
        self.records['new-edge.example.net'] = ['192.0.2.9']
        hosts = [host for host, _ in origin.HOSTS] + ['new-edge.example.net']
        self.assertTrue(origin.refresh(self.path, self.resolve, self.nginx_run, bootstrap=True, hosts=hosts))
        self.assertIn('new-edge.example.net', self.path.read_text())
        self.assertIn('server 192.0.2.9:80', self.path.read_text())

    def test_one_failed_cdn_retains_its_old_pool_while_other_cdn_updates(self):
        origin.refresh(self.path, self.resolve, self.nginx_run, bootstrap=True)
        old_host, changed_host = [host for host, _ in origin.HOSTS]
        def partial(host):
            if host == old_host:
                raise OSError('one CDN DNS unavailable')
            return ['192.0.2.99']
        try:
            origin.refresh(self.path, partial, self.nginx_run)
        except OSError:
            self.fail('One failed hostname must not block all other CDN updates')
        self.assertIn('server 192.0.2.1:80', self.path.read_text())
        self.assertIn('server 192.0.2.99:80', self.path.read_text())

    def test_dns_cache_avoids_dns_queries_on_every_discovery_tick(self):
        calls = []
        now = [100.0]
        resolver = origin.CachingResolver(lambda host: calls.append(host) or ['192.0.2.1'], lambda: now[0])
        resolver('cdn.example.net')
        now[0] += 15
        resolver('cdn.example.net')
        self.assertEqual(len(calls), 1)
        now[0] += 300
        resolver('cdn.example.net')
        self.assertEqual(len(calls), 2)

    def test_redirect_targets_are_discovered_even_when_original_host_did_not_change(self):
        log = self.path.parent / 'origin-redirect-hosts.log'
        log.write_text('dl1.steam.clngaa.com\nDL1.STEAM.CLNGAA.COM\n\n')
        self.assertEqual(origin.discover_redirect_hosts(log), ['dl1.steam.clngaa.com'])

    def test_redirect_discovery_log_cannot_grow_without_bound(self):
        log = self.path.parent / 'origin-redirect-hosts.log'
        log.write_text('dl1.steam.clngaa.com\n' * 70000)
        self.assertIn('dl1.steam.clngaa.com', origin.discover_redirect_hosts(log))
        self.assertLessEqual(log.stat().st_size, 1048576)

    def test_redirect_log_discovers_both_issuer_and_target(self):
        log = self.path.parent / 'origin-redirect-hosts.log'
        log.write_text('dl.steam.clngaa.com dl1.steam.clngaa.com\n')
        self.assertEqual(set(origin.discover_redirect_hosts(log)), {'dl.steam.clngaa.com', 'dl1.steam.clngaa.com'})
        self.assertEqual(origin.discover_redirect_issuers(log), ['dl.steam.clngaa.com'])

    def test_redirect_issuer_uses_body_draining_gateway_and_survives_log_rotation(self):
        host = 'dl.steam.clngaa.com'
        self.records[host] = ['192.0.2.9']
        hosts = list(self.records)
        origin.refresh(self.path, self.resolve, self.nginx_run, bootstrap=True,
                       hosts=hosts, redirect_issuers=[host])
        self.assertIn(host + ' lancache_redirect_gateway;', self.path.read_text())
        origin.refresh(self.path, self.resolve, self.nginx_run, hosts=hosts)
        self.assertIn(host + ' lancache_redirect_gateway;', self.path.read_text())


    def test_dns_queries_configured_upstreams_instead_of_system_dns(self):
        answer = subprocess.CompletedProcess([], 0, 'alias.example.net.\n192.0.2.42\n', '')
        with mock.patch.dict(origin.os.environ, {'UPSTREAM_DNS': '192.0.2.53:5353;192.0.2.54'}), mock.patch.object(origin.subprocess, 'run', return_value=answer) as run:
            self.assertEqual(origin.resolve_dns('cdn.example.net'), ['192.0.2.42'])
        args = run.call_args.args[0]
        self.assertIn('@192.0.2.53', args)
        self.assertEqual(args[args.index('-p') + 1], '5353')

    def test_dns_tries_next_configured_resolver_after_failure(self):
        failure = subprocess.TimeoutExpired('dig', 5)
        answer = subprocess.CompletedProcess([], 0, '192.0.2.42\n', '')
        with mock.patch.dict(origin.os.environ, {'UPSTREAM_DNS': '192.0.2.53 192.0.2.54'}), mock.patch.object(origin.subprocess, 'run', side_effect=[failure, failure, answer, subprocess.CompletedProcess([], 0, '', '')]) as run:
            self.assertEqual(origin.resolve_dns('cdn.example.net'), ['192.0.2.42'])
        self.assertIn('@192.0.2.54', run.call_args.args[0])

    def test_dns_accepts_bracketed_ipv6_resolver(self):
        answer = subprocess.CompletedProcess([], 0, '192.0.2.42\n', '')
        with mock.patch.dict(origin.os.environ, {'UPSTREAM_DNS': '[2001:db8::53]:5353'}), mock.patch.object(origin.subprocess, 'run', return_value=answer) as run:
            self.assertEqual(origin.resolve_dns('cdn.example.net'), ['192.0.2.42'])
        self.assertIn('@2001:db8::53', run.call_args.args[0])

    def test_lifetime_resolver_cache_is_bounded_under_host_churn(self):
        resolver = origin.CachingResolver(lambda _: ['192.0.2.1'])
        for i in range(origin.MAX_HOSTS * 4):
            resolver(f'edge-{i}.example.net')
        self.assertLessEqual(len(resolver.entries), origin.MAX_HOSTS * 2)
        self.assertNotIn('edge-0.example.net', resolver.entries)


    def test_managed_pools_support_ipv6_and_persist_it_across_restart(self):
        value = origin.render({'cdn.example.net': ['192.0.2.8', '2001:db8::8']})
        self.assertIn('server [2001:db8::8]:80', value)
        self.assertIn('server [2001:db8::8]:443', value)
        self.assertEqual(set(origin.previous_records(value)['cdn.example.net']), {'192.0.2.8', '2001:db8::8'})

    def test_managed_pool_rejects_local_ipv6_addresses(self):
        for address in ['::', '::1', 'fc00::1', 'fe80::1', 'ff02::1', '::ffff:127.0.0.1']:
            with self.subTest(address=address), self.assertRaises(ValueError):
                origin.render({'cdn.example.net': [address]})

    def test_managed_dns_collects_a_and_aaaa(self):
        answers = [subprocess.CompletedProcess([], 0, '192.0.2.42\n', ''),
                   subprocess.CompletedProcess([], 0, '2001:db8::42\n', '')]
        with mock.patch.dict(origin.os.environ, {'UPSTREAM_DNS': '192.0.2.53', 'ORIGIN_KEEPALIVE_IPV6': 'on'}), mock.patch.object(origin.subprocess, 'run', side_effect=answers) as run:
            self.assertEqual(origin.resolve_dns('cdn.example.net'), ['192.0.2.42', '2001:db8::42'])
        self.assertEqual([call.args[0][-1] for call in run.call_args_list], ['A', 'AAAA'])

    def test_ipv6_can_be_disabled_for_ipv4_only_networks(self):
        answer = subprocess.CompletedProcess([], 0, '192.0.2.42\n', '')
        with mock.patch.dict(origin.os.environ, {'UPSTREAM_DNS': '192.0.2.53', 'ORIGIN_KEEPALIVE_IPV6': 'off'}), mock.patch.object(origin.subprocess, 'run', return_value=answer) as run:
            self.assertEqual(origin.resolve_dns('cdn.example.net'), ['192.0.2.42'])
            self.assertIn('ipv6=off', origin.resolver_directive())
        self.assertEqual(run.call_count, 1)

    def test_native_pools_delegate_addresses_to_nginx(self):
        with mock.patch.dict(origin.os.environ, {'UPSTREAM_DNS': '192.0.2.53 [2001:db8::53]:5353'}):
            value = origin.render({'cdn.example.net': []}, native=True)
        self.assertIn('server cdn.example.net:80 resolve', value)
        self.assertIn('server cdn.example.net:443 resolve', value)
        self.assertIn('zone ', value)
        self.assertIn('resolver 192.0.2.53 [2001:db8::53]:5353', value)
        self.assertIn('ipv6=on', value)
        self.assertEqual(list(origin.previous_records(value)), ['cdn.example.net'])

    def test_native_refresh_does_not_query_dns_or_reload_for_address_changes(self):
        def forbidden_dns(_):
            self.fail('Native mode must delegate DNS to nginx')
        self.assertTrue(origin.refresh(self.path, forbidden_dns, self.nginx_run, bootstrap=True,
                                       hosts=['cdn.example.net'], native=True))
        self.assertFalse(origin.refresh(self.path, forbidden_dns, self.nginx_run,
                                        hosts=['cdn.example.net'], native=True))
        self.assertEqual(self.calls, [])
        origin.refresh(self.path, forbidden_dns, self.nginx_run,
                       hosts=['cdn.example.net', 'new.example.net'], native=True)
        self.assertEqual(self.calls, [['nginx', '-t'], ['nginx', '-s', 'reload']])

    def test_native_mode_is_selected_only_on_capable_nginx(self):
        def version(value):
            return lambda *args, **kwargs: subprocess.CompletedProcess([], 0, '', 'nginx version: nginx/' + value)
        self.assertFalse(origin.select_native_dns('auto', version('1.24.0')))
        self.assertTrue(origin.select_native_dns('auto', version('1.27.3')))
        self.assertTrue(origin.select_native_dns('auto', version('1.30.6')))
        self.assertFalse(origin.select_native_dns('managed', version('1.30.6')))
        with self.assertRaises(ValueError):
            origin.select_native_dns('native', version('1.24.0'))

    def test_json_access_events_discover_hosts_without_parsing_main_log_format(self):
        log = self.path.parent / 'origin-hosts.jsonl'
        log.write_text('{"host":"NEW-EDGE.EXAMPLE.NET","redirect_host":""}\n'
                       '{"host":"other.example.net","redirect_host":"target.example.net"}\n')
        self.assertEqual(set(origin.discover_hosts(log)), {'new-edge.example.net', 'other.example.net'})
        self.assertEqual(set(origin.discover_redirect_hosts(log)), {'new-edge.example.net', 'other.example.net', 'target.example.net'})
        self.assertEqual(origin.discover_redirect_issuers(log), ['other.example.net'])

    def test_json_discovery_ignores_malformed_nonstring_and_local_host_values(self):
        log = self.path.parent / 'origin-hosts.jsonl'
        log.write_text('{truncated\n["example.net"]\n'
                       '{"host":null,"redirect_host":4}\n'
                       '{"host":"lancache.steamcontent.com","redirect_host":"192.168.0.57"}\n'
                       '{"host":"valid.example.net","redirect_host":""}\n')
        self.assertEqual(origin.discover_hosts(log), ['valid.example.net'])

    def test_owned_json_discovery_log_is_bounded(self):
        log = self.path.parent / 'origin-hosts.jsonl'
        log.write_text('{"host":"cdn.example.net","redirect_host":""}\n' * 30000)
        self.assertIn('cdn.example.net', origin.discover_redirect_hosts(log))
        self.assertLessEqual(log.stat().st_size, 1048576)


    def test_native_bootstrap_reuses_hostnames_without_system_dns(self):
        self.path.write_text(origin.render({'cdn.example.net': ['192.0.2.1']}))
        def unavailable(_):
            self.fail('Native bootstrap must not resolve origins in Python')
        origin.bootstrap(self.path, unavailable, self.nginx_run, native=True)
        self.assertIn('server cdn.example.net:80 resolve', self.path.read_text())
        self.assertEqual(self.calls, [])

    def test_offline_downgrade_does_not_leave_native_syntax_on_old_nginx(self):
        self.path.write_text(origin.render({'cdn.example.net': []}, native=True))
        def unavailable(_):
            raise OSError('offline during rollback')
        origin.bootstrap(self.path, unavailable, self.nginx_run, hosts=['cdn.example.net'], native=False)
        self.assertNotIn(' resolve ', self.path.read_text())
        self.assertIn('default $host;', self.path.read_text())


    def test_ipv6_off_warm_boot_removes_disabled_family_from_saved_pools(self):
        self.path.write_text(origin.render({'dual.example.net': ['192.0.2.1', '2001:db8::1'],
                                           'v6.example.net': ['2001:db8::2']}))
        def unavailable(_):
            raise OSError('offline')
        with mock.patch.dict(origin.os.environ, {'ORIGIN_KEEPALIVE_IPV6': 'off'}):
            origin.bootstrap(self.path, unavailable, self.nginx_run)
        self.assertNotIn('[2001:db8::', self.path.read_text())
        self.assertIn('server 192.0.2.1:80', self.path.read_text())

    def test_ipv6_off_offline_boot_clears_ipv6_only_saved_state(self):
        self.path.write_text(origin.render({'v6.example.net': ['2001:db8::1']}))
        def unavailable(_):
            raise OSError('offline')
        with mock.patch.dict(origin.os.environ, {'ORIGIN_KEEPALIVE_IPV6': 'off'}):
            origin.bootstrap(self.path, unavailable, self.nginx_run, hosts=['v6.example.net'])
        self.assertNotIn('[2001:db8::', self.path.read_text())
        self.assertIn('default $host;', self.path.read_text())


if __name__ == '__main__':
    unittest.main()
