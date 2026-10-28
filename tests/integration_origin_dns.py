"""Hermetic container fixture: run with Python as root, network=none, no data mounts.

Loads the opt-in nginx snippets and serves local DNS/HTTP/TLS origins. No Internet
requests are made. Native mode exercises resolver timers; managed mode exercises
numeric IPv4/IPv6 pools using documentation-address-to-loopback substitutions.
"""
import collections
import contextlib
import http.client
import http.server
import importlib.util
import json
import os
from pathlib import Path
import socket
import socketserver
import ssl
import struct
import subprocess
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
os.environ['UPSTREAM_DNS'] = '127.0.0.1:1053'
os.environ['ORIGIN_KEEPALIVE_DNS_TTL'] = '1'
os.environ['ORIGIN_KEEPALIVE_IPV6'] = 'on'
spec = importlib.util.spec_from_file_location('origin', ROOT / 'overlay/scripts/refresh_cdn_upstreams.py')
origin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(origin)
NATIVE = origin.select_native_dns('auto')
HOSTS = ['v4.example.test', 'v6.example.test', 'dual.example.test', 'rotate.example.test',
         'issuer.example.test', 'plain-issuer.example.test', 'tls.example.test', 'fallback.example.test']
state = {'rotate': '127.0.0.1', 'failure': False}
queries = collections.Counter()
requests = collections.defaultdict(list)
sni = []


class DNS(socketserver.BaseRequestHandler):
    def handle(self):
        data, sock = self.request
        offset = 12
        labels = []
        while data[offset]:
            size = data[offset]
            labels.append(data[offset + 1:offset + 1 + size].decode())
            offset += 1 + size
        offset += 1
        family = struct.unpack('!H', data[offset:offset + 2])[0]
        name = '.'.join(labels)
        queries[(name, family)] += 1
        question = data[12:offset + 4]
        addresses = []
        if family == 1 and name != 'v6.example.test':
            addresses = [state['rotate'] if name == 'rotate.example.test' else '127.0.0.1']
        if family == 28 and name in ('v6.example.test', 'dual.example.test', 'fallback.example.test'):
            addresses = ['::2' if name == 'fallback.example.test' else '::1']
        answers = b''
        for address in addresses:
            raw = socket.inet_pton(socket.AF_INET if family == 1 else socket.AF_INET6, address)
            answers += b'\xc0\x0c' + struct.pack('!HHIH', family, 1, 1, len(raw)) + raw
        failure = state['failure']
        header = struct.pack('!HHHHHH', struct.unpack('!H', data[:2])[0], 0x8182 if failure else 0x8180,
                             1, 0 if failure else len(addresses), 0, 0)
        sock.sendto(header + question + (b'' if failure else answers), self.client_address)


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def setup(self):
        super().setup()
        with self.server.counter_lock:
            self.server.counter += 1
            self.connection_id = self.server.counter

    def handle(self):
        # Redirect interception deliberately closes some upstream sockets early.
        with contextlib.suppress(ConnectionResetError, BrokenPipeError):
            super().handle()

    def do_GET(self):
        host = self.headers['Host']
        requests[host].append((self.server.server_address[0], self.connection_id))
        if host in ('issuer.example.test', 'plain-issuer.example.test'):
            body = b'Follow the redirect.\n' * 64
            self.send_response(302)
            self.send_header('Location', 'https://tls.example.test' + self.path)
        else:
            body = json.dumps({'host': host, 'path': self.path,
                               'address': self.server.server_address[0], 'connection': self.connection_id}).encode()
            self.send_response(200)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class HTTP(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, context=None):
        self.address_family = socket.AF_INET6 if ':' in address[0] else socket.AF_INET
        self.counter = 0
        self.counter_lock = threading.Lock()
        super().__init__(address, Handler)
        if context:
            self.socket = context.wrap_socket(self.socket, server_side=True)


def serve(server):
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def fetch(host, path='/payload?authkey=fixture%2Fvalue&x=one%2Btwo'):
    connection = http.client.HTTPConnection('127.0.0.1', 8080, timeout=3)
    try:
        connection.request('GET', path, headers={'Host': host})
        response = connection.getresponse()
        data = response.read()
        return response.status, data
    finally:
        connection.close()


def wait_for(predicate, timeout=8):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            value = predicate()
            if value:
                return value
        except (OSError, http.client.HTTPException, ValueError):
            pass
        time.sleep(0.1)
    raise AssertionError('Fixture condition timed out')


def worker_pids(pid):
    return Path(f'/proc/{pid}/task/{pid}/children').read_text().split()


def run():
    with tempfile.TemporaryDirectory(prefix='origin-integration-') as temporary:
        tmp = Path(temporary)
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                        '-keyout', str(tmp / 'key.pem'), '-out', str(tmp / 'cert.pem'),
                        '-subj', '/CN=tls.example.test', '-days', '1'], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(tmp / 'cert.pem', tmp / 'key.pem')
        context.set_servername_callback(lambda _, name, __: sni.append(name))
        servers = [serve(socketserver.UDPServer(('127.0.0.1', 1053), DNS))]
        process = None
        try:
            servers += [serve(HTTP(('127.0.0.1', 80))), serve(HTTP(('127.0.0.2', 80))),
                        serve(HTTP(('::1', 80))), serve(HTTP(('127.0.0.1', 443), context))]
            pools = {host: [] for host in HOSTS} if NATIVE else {
                host: ['2001:db8::1'] if host == 'v6.example.test' else
                ['192.0.2.1', '2001:db8::1'] if host == 'dual.example.test' else
                ['192.0.2.1', '2001:db8::2'] if host == 'fallback.example.test' else ['192.0.2.1'] for host in HOSTS}
            rendered = origin.render(pools, redirect_issuers=['issuer.example.test'], native=NATIVE)
            if not NATIVE:
                rendered = rendered.replace('192.0.2.1', '127.0.0.1').replace('2001:db8::1', '::1').replace('2001:db8::2', '::2')
            Path('/data/logs').mkdir(parents=True, exist_ok=True)
            state_path = Path('/data/info/cdn-origin/upstreams.conf')
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text(rendered)
            resolver_path = Path('/etc/nginx/sites-available/upstream.conf.d/10_resolver.conf')
            resolver_path.write_text(origin.resolver_directive() + '\nresolver_timeout 1s;\n')
            feature = ROOT / 'overlay/opt/lancache/origin-keepalive/etc/nginx'
            keepalive = feature / 'conf.d/13_origin_keepalive.conf'
            primary = feature / 'sites-available/upstream.conf.d/30_primary_proxy.conf'
            redirect = feature / 'sites-available/upstream.conf.d/40_redirect_proxy.conf'
            config = tmp / 'nginx.conf'
            config.write_text(f'''
worker_processes 1;
pid {tmp}/nginx.pid;
error_log {tmp}/error.log info;
events {{ worker_connections 256; }}
http {{
    log_format deliberately_custom '$request_time';
    access_log {tmp}/custom-main.log deliberately_custom;
    include {keepalive};
    server {{
        listen 127.0.0.1:3128;
        include {resolver_path};
        proxy_connect_timeout 200ms;
        proxy_next_upstream error timeout;
        include {primary};
        include {redirect};
    }}
    server {{
        listen 127.0.0.1:8080;
        location / {{
            proxy_http_version 1.1;
            proxy_set_header Connection "";
            proxy_set_header Host $host;
            proxy_pass http://lancache_internal_relay$request_uri;
        }}
    }}
}}
''')
            subprocess.run(['nginx', '-t', '-c', str(config)], check=True, capture_output=True)
            process = subprocess.Popen(['nginx', '-c', str(config), '-g', 'daemon off;'],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            wait_for(lambda: fetch('v4.example.test')[0] == 200)
            workers = worker_pids(process.pid)
            assert workers, 'nginx must have a running worker'
            for host in ('v4.example.test', 'v6.example.test', 'dual.example.test'):
                for _ in range(12):
                    status, data = fetch(host)
                    payload = json.loads(data)
                    assert status == 200 and payload['host'] == host
                    assert payload['path'] == '/payload?authkey=fixture%2Fvalue&x=one%2Btwo'
            assert {address for address, _ in requests['dual.example.test']} == {'127.0.0.1', '::1'}
            assert len(set(requests['v4.example.test'])) == 1, 'IPv4 origin connection should be reused'
            assert len(set(requests['v6.example.test'])) == 1, 'IPv6 origin connection should be reused'
            for _ in range(12):
                assert fetch('fallback.example.test')[0] == 200, 'Unreachable IPv6 must fall back to IPv4'
            dns_result = 'managed numeric pools'
            failure_result = 'managed behavior covered by unit tests'
            if NATIVE:
                assert fetch('rotate.example.test')[0] == 200
                state['rotate'] = '127.0.0.2'
                wait_for(lambda: json.loads(fetch('rotate.example.test')[1]).get('address') == '127.0.0.2')
                assert worker_pids(process.pid) == workers, 'DNS rotation must not replace workers'
                before = queries[('rotate.example.test', 1)] + queries[('rotate.example.test', 28)]
                state['failure'] = True
                wait_for(lambda: queries[('rotate.example.test', 1)] + queries[('rotate.example.test', 28)] >= before + 4)
                status, _ = fetch('rotate.example.test')
                failure_result = 'SERVFAIL last-good status=' + str(status)
                assert status == 200, 'Transient SERVFAIL should retain the last-good native peer'
                state['failure'] = False
                dns_result = 'A rotation served new address with unchanged worker PID'
            for host in ('plain-issuer.example.test', 'issuer.example.test'):
                for _ in range(10):
                    status, data = fetch(host)
                    payload = json.loads(data)
                    assert status == 200 and payload['host'] == 'tls.example.test'
                    assert payload['path'] == '/payload?authkey=fixture%2Fvalue&x=one%2Btwo'
            direct_connections = len(set(requests['plain-issuer.example.test']))
            gateway_connections = len(set(requests['issuer.example.test']))
            assert gateway_connections <= 2, 'Body-draining gateway should reuse issuer connections'
            assert 'tls.example.test' in sni, 'HTTPS redirect must preserve the real SNI'
            events_path = Path('/data/logs/origin-hosts.jsonl')
            events = [json.loads(line) for line in events_path.read_text().splitlines()]
            assert all(set(event) == {'host', 'redirect_host'} for event in events)
            assert 'authkey' not in events_path.read_text(), 'Discovery must not store signed URLs'
            assert 'issuer.example.test' in origin.discover_redirect_issuers(events_path)
            assert {'v4.example.test', 'v6.example.test'} <= set(origin.discover_hosts(events_path))
            print(json.dumps({'nginx': subprocess.run(['nginx', '-v'], capture_output=True, text=True).stderr.strip(),
                              'native': NATIVE, 'dualStack': 'passed', 'unreachableIpv6Fallback': 'passed', 'dnsRotation': dns_result,
                              'dnsFailure': failure_result, 'workersUnchanged': worker_pids(process.pid) == workers,
                              'redirectIssuerConnections': {'direct': direct_connections, 'gateway': gateway_connections},
                              'queryHostAndSni': 'passed', 'customMainLogIndependentDiscovery': 'passed'}, indent=2))
        except Exception:
            if (tmp / 'error.log').exists():
                print((tmp / 'error.log').read_text()[-8000:])
            raise
        finally:
            if process:
                process.terminate()
                with contextlib.suppress(subprocess.TimeoutExpired):
                    process.wait(timeout=3)
                if process.poll() is None:
                    process.kill()
            for server in servers:
                server.shutdown()
                server.server_close()


if __name__ == '__main__':
    run()
