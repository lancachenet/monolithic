#!/usr/bin/env python3
"""Discover content origins and maintain keepalive pools with last-good DNS/config state."""
import argparse
from collections import OrderedDict
import fcntl
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time

# No region-specific seeds are required; traffic discovers origin hostnames.
HOSTS = ()
MAX_HOSTS = max(1, min(1024, int(os.environ.get('ORIGIN_KEEPALIVE_MAX_HOSTS', '64'))))
REFRESH_INTERVAL = max(1, int(os.environ.get('ORIGIN_KEEPALIVE_INTERVAL', '15')))
DNS_TTL = max(1, int(os.environ.get('ORIGIN_KEEPALIVE_DNS_TTL', '300')))
DNS_FAILURE_TTL = max(1, int(os.environ.get('ORIGIN_KEEPALIVE_DNS_FAILURE_TTL', '30')))
LOCAL_NETWORKS = tuple(ipaddress.ip_network(value) for value in ('0.0.0.0/8', '10.0.0.0/8', '127.0.0.0/8', '169.254.0.0/16', '172.16.0.0/12', '192.168.0.0/16', '224.0.0.0/4', '::/128', '::1/128', 'fc00::/7', 'fe80::/10', 'ff00::/8'))


def normalize_host(value):
    value = value.lower().strip().rstrip('.')
    if ':' in value:
        value, port = value.rsplit(':', 1)
        if not port.isdigit():
            return None
    if value == 'lancache.steamcontent.com' or len(value) > 253:
        return None
    labels = value.split('.')
    if len(labels) < 2 or all(label.isdigit() for label in labels):
        return None
    if not all(re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', label) for label in labels):
        return None
    return value


def pool_name(host):
    return dict(HOSTS).get(host, 'lancache_origin_' + hashlib.sha256(host.encode()).hexdigest()[:16])


def ipv6_enabled():
    value = os.environ.get('ORIGIN_KEEPALIVE_IPV6', 'on').lower()
    if value not in ('on', 'off'):
        raise ValueError('ORIGIN_KEEPALIVE_IPV6 must be on or off')
    return value == 'on'


def resolver_endpoints():
    result = []
    for endpoint in os.environ.get('UPSTREAM_DNS', '8.8.8.8 8.8.4.4').replace(';', ' ').split():
        if endpoint.startswith('['):
            address, separator, port = endpoint[1:].partition(']')
            if not separator or (port and not port.startswith(':')):
                raise ValueError('Invalid resolver endpoint')
            port = port[1:] if port else '53'
        elif endpoint.count(':') == 1:
            address, port = endpoint.rsplit(':', 1)
        else:
            address, port = endpoint, '53'
        parsed = ipaddress.ip_address(address)
        if not port.isdigit() or not 1 <= int(port) <= 65535:
            raise ValueError('Invalid resolver port')
        result.append((str(parsed), int(port)))
    if not result:
        raise ValueError('UPSTREAM_DNS must contain a resolver')
    return result


def resolver_directive():
    endpoints = []
    for address, port in resolver_endpoints():
        host = '[' + address + ']' if ':' in address else address
        endpoints.append(host + (':' + str(port) if port != 53 else ''))
    return 'resolver ' + ' '.join(endpoints) + ' valid=' + str(DNS_TTL) + 's ipv6=' + ('on' if ipv6_enabled() else 'off') + ';'


def select_native_dns(mode='auto', run=subprocess.run):
    if mode not in ('auto', 'native', 'managed'):
        raise ValueError('ORIGIN_KEEPALIVE_DNS_MODE must be auto, native or managed')
    if mode == 'managed':
        return False
    result = run(['nginx', '-v'], capture_output=True, text=True, timeout=5, check=True)
    version = re.search(r'nginx/(\d+)\.(\d+)\.(\d+)', result.stderr + result.stdout)
    capable = bool(version and tuple(map(int, version.groups())) >= (1, 27, 3))
    if mode == 'native' and not capable:
        raise ValueError('Native origin DNS requires nginx >= 1.27.3')
    return capable


def resolve_dns(host):
    # Query nginx's resolvers, not system DNS that may point back at lancache-dns.
    errors = []
    families = ('A', 'AAAA') if ipv6_enabled() else ('A',)
    for address, port in resolver_endpoints():
        addresses = []
        for family in families:
            try:
                result = subprocess.run(['dig', '+short', '+time=2', '+tries=1', '@' + address,
                                         '-p', str(port), host, family], capture_output=True, text=True, timeout=5, check=True)
                for line in result.stdout.splitlines():
                    try:
                        addresses.append(str(ipaddress.ip_address(line.strip())))
                    except ValueError:
                        pass  # Intermediate CNAMEs are not addresses.
            except (OSError, subprocess.SubprocessError) as error:
                errors.append(error)
        if addresses:
            return list(dict.fromkeys(addresses))
    raise OSError('No configured upstream resolver returned an origin address') from (errors[-1] if errors else None)


def render(records, redirect_issuers=(), native=False):
    lines = ['# Generated origin pools. No account credentials are stored here.']
    for host in sorted(records):
        if normalize_host(host) != host:
            raise ValueError('Invalid origin hostname')
        name = pool_name(host)
        if not native:
            parsed = {ipaddress.ip_address(address) for address in records[host]}
            if any(any(address in network for network in LOCAL_NETWORKS)
                   or (getattr(address, 'ipv4_mapped', None) is not None
                       and any(address.ipv4_mapped in network for network in LOCAL_NETWORKS)) for address in parsed):
                raise ValueError('Origin resolves to a local address')
            addresses = sorted((address for address in parsed if address.version == 4 or ipv6_enabled()),
                               key=lambda address: (address.version, int(address)))
            if not addresses:
                raise OSError('No enabled-family addresses for ' + host)
        for suffix, port in [('', 80), ('_tls', 443)]:
            lines.append('upstream ' + name + suffix + ' {')
            if native:
                lines.extend(['    zone ' + name + suffix + ' 64k;', '    ' + resolver_directive(),
                              '    resolver_timeout 5s;',
                              '    server ' + host + ':' + str(port) + ' resolve max_fails=2 fail_timeout=10s;'])
            else:
                lines.extend('    server ' + ('[' + str(address) + ']' if address.version == 6 else str(address))
                             + ':' + str(port) + ' max_fails=2 fail_timeout=10s;' for address in addresses)
            lines.extend(['    keepalive 64;', '    keepalive_requests 1000;', '    keepalive_timeout 30s;', '}'])
    lines.extend(['map $host $lancache_origin_backend {', '    default $host;'])
    lines.extend('    ' + host + ' ' + pool_name(host) + ';' for host in sorted(records))
    lines.append('}')
    lines.extend(['map $host $lancache_primary_backend {', '    default $lancache_origin_backend;'])
    lines.extend('    ' + host + ' lancache_redirect_gateway;' for host in sorted(set(redirect_issuers) & set(records)))
    lines.append('}')
    for variable, suffix in [('http', ''), ('https', '_tls')]:
        lines.extend(['map $lancache_redirect_host $lancache_redirect_' + variable + '_backend {', '    default $lancache_redirect_host;'])
        lines.extend('    ' + host + ' ' + pool_name(host) + suffix + ';' for host in sorted(records))
        lines.append('}')
    return '\n'.join(lines) + '\n'


def atomic_write(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, filename = tempfile.mkstemp(prefix='.origin-', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(filename, 0o644)
        os.replace(filename, path)
    finally:
        if os.path.exists(filename):
            os.unlink(filename)


def event_hosts(line):
    try:
        event = json.loads(line)
    except ValueError:
        return None
    if not isinstance(event, dict):
        return ('', '')
    return tuple(normalize_host(value) if isinstance(value, str) else None
                 for value in (event.get('host'), event.get('redirect_host')))


def discover_hosts(path):
    result = []
    for line in reversed(redirect_log_lines(path)):
        event = event_hosts(line)
        if event is not None:
            host = event[0]
        else:
            # Read old default text logs only when explicitly supplied by an operator.
            if not re.search(r'HTTP/[^"]+"\s+(?:200|206)\s+', line):
                continue
            quoted = re.findall(r'"([^"\n]*)"', line)
            host = normalize_host(quoted[-2]) if len(quoted) >= 6 else None
        if host and host not in result:
            result.append(host)
        if len(result) >= MAX_HOSTS:
            break
    return result


def previous_records(content):
    groups = {name: [address.strip('[]') for address in re.findall(r'\bserver\s+(\[[0-9a-fA-F:]+\]|[0-9.]+):(?:80|443)\b', body)]
              for name, body in re.findall(r'upstream\s+(\w+)\s*\{([^}]+)\}', content)}
    return {host: groups[name] for host, name in re.findall(r'^\s+([a-z0-9.-]+)\s+(lancache_\w+);', content, re.MULTILINE)
            if normalize_host(host) == host and name in groups}


def redirect_log_lines(path, truncate=False):
    path = Path(path)
    if not path.exists():
        return []
    with path.open('rb') as stream:
        size = path.stat().st_size
        stream.seek(max(0, size - 524288))
        lines = stream.read().decode('utf-8', errors='replace').splitlines()
    # This is our dedicated hostname-only discovery log, never the primary access log.
    if truncate and size > 1048576 and path.name in ('origin-redirect-hosts.log', 'origin-hosts.jsonl'):
        with path.open('r+b') as stream:
            stream.truncate(0)
    return lines


def discover_redirect_hosts(path):
    result = []
    for line in reversed(redirect_log_lines(path, truncate=True)):
        event = event_hosts(line)
        parts = event if event is not None else [normalize_host(part) for part in line.split()]
        for host in parts:
            if host and host not in result:
                result.append(host)
    return result[:MAX_HOSTS]


def discover_redirect_issuers(path):
    result = []
    for line in reversed(redirect_log_lines(path)):
        event = event_hosts(line)
        if event is None:
            parts = line.split()
            event = tuple(normalize_host(part) for part in parts) if len(parts) == 2 else (None, None)
        host, target = event
        if host and target and host not in result:
            result.append(host)
    return result[:MAX_HOSTS]


def previous_redirect_issuers(content):
    return re.findall(r'^\s+([a-z0-9.-]+)\s+lancache_redirect_gateway;', content, re.MULTILINE)


def selected_hosts(path, access_log, redirect_log=None):
    previous = previous_records(Path(path).read_text()) if Path(path).exists() else {}
    redirected = discover_redirect_hosts(redirect_log) if redirect_log is not None else []
    return list(dict.fromkeys(redirected + discover_hosts(access_log) + list(previous) + [host for host, _ in HOSTS]))[:MAX_HOSTS]


class CachingResolver:
    def __init__(self, resolve=resolve_dns, clock=time.monotonic):
        self.resolve = resolve
        self.clock = clock
        self.entries = OrderedDict()

    def __call__(self, host):
        now = self.clock()
        cached = self.entries.get(host)
        if cached:
            self.entries.move_to_end(host)
        elif len(self.entries) >= MAX_HOSTS * 2:
            self.entries.popitem(last=False)
        if cached and now < cached[0]:
            if isinstance(cached[1], Exception):
                raise cached[1]
            return cached[1]
        try:
            value = self.resolve(host)
            self.entries[host] = (now + DNS_TTL, value)
            return value
        except Exception as error:
            if cached and not isinstance(cached[1], Exception):
                self.entries[host] = (now + DNS_FAILURE_TTL, cached[1])
                return cached[1]
            self.entries[host] = (now + DNS_FAILURE_TTL, error)
            raise


def refresh(path, resolve=resolve_dns, run=subprocess.run, bootstrap=False, hosts=None, redirect_issuers=(), native=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with (path.parent / '.refresh.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        previous = path.read_text() if path.exists() else None
        previous_hosts = previous_records(previous or '')
        records = {}
        errors = []
        for host in hosts if hosts is not None else [host for host, _ in HOSTS]:
            if native:
                records[host] = []
                continue
            try:
                records[host] = resolve(host)
            except Exception as error:
                errors.append(error)
                if previous_hosts.get(host):
                    records[host] = previous_hosts[host]
        if not records and errors:
            raise errors[0]
        issuers = previous_redirect_issuers(previous or '') + list(redirect_issuers)
        content = render(records, issuers, native=native)
        if previous == content:
            return False
        atomic_write(path, content)
        if bootstrap:
            return True
        try:
            for command in (['nginx', '-t'], ['nginx', '-s', 'reload']):
                result = run(command, capture_output=True, text=True, timeout=10)
                if result.returncode:
                    raise RuntimeError('Origin configuration validation/reload failed')
        except Exception:
            if previous is None:
                path.unlink(missing_ok=True)
            else:
                atomic_write(path, previous)
            raise
        return True


def bootstrap(path, resolve=resolve_dns, run=subprocess.run, hosts=None, redirect_issuers=(), native=False):
    incompatible_previous = False
    try:
        previous = Path(path).read_text() if Path(path).exists() else ''
        saved = previous_records(previous)
        incompatible_previous = not native and (' resolve ' in previous or
            (not ipv6_enabled() and any(':' in address for addresses in saved.values() for address in addresses)))
        if native:
            refresh(path, resolve, run, bootstrap=True, hosts=hosts if hosts is not None else list(saved),
                    redirect_issuers=redirect_issuers, native=True)
            return
        saved = {host: [address for address in addresses if ':' not in address or ipv6_enabled()]
                 for host, addresses in saved.items()}
        saved = {host: addresses for host, addresses in saved.items() if addresses}
        if saved:
            # Start from the saved addresses immediately; the watcher refreshes DNS
            # after nginx is serving, rather than delaying availability per hostname.
            refresh(path, saved.__getitem__, run, bootstrap=True, hosts=list(saved), redirect_issuers=redirect_issuers)
            return
        refresh(path, resolve, run, bootstrap=True, hosts=hosts, redirect_issuers=redirect_issuers)
    except Exception as error:
        if not Path(path).exists() or incompatible_previous:
            atomic_write(path, render({}))
        print('Origin DNS unavailable; retaining existing/default routing (' + type(error).__name__ + ')', flush=True)


def main():
    global HOSTS
    seeds = os.environ.get('ORIGIN_KEEPALIVE_SEED_HOSTS', '').replace(',', ' ').split()
    normalized = [normalize_host(host) for host in seeds]
    if any(host is None for host in normalized):
        raise ValueError('Invalid ORIGIN_KEEPALIVE_SEED_HOSTS hostname')
    HOSTS = tuple((host, 'lancache_origin_' + hashlib.sha256(host.encode()).hexdigest()[:16])
                  for host in dict.fromkeys(normalized))
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--bootstrap', action='store_true')
    modes.add_argument('--watch', action='store_true')
    modes.add_argument('--once', action='store_true')
    parser.add_argument('--state-file', default='/data/info/cdn-origin/upstreams.conf')
    parser.add_argument('--access-log', default='/data/logs/origin-hosts.jsonl')
    parser.add_argument('--redirect-log', default='/data/logs/origin-hosts.jsonl')
    options = parser.parse_args()
    native = select_native_dns(os.environ.get('ORIGIN_KEEPALIVE_DNS_MODE', 'auto'))
    resolver = CachingResolver()
    if options.bootstrap:
        atomic_write('/etc/nginx/sites-available/upstream.conf.d/10_resolver.conf',
                     resolver_directive() + '\nresolver_timeout 5s;\n')
        issuers = discover_redirect_issuers(options.redirect_log)
        bootstrap(options.state_file, resolver, hosts=selected_hosts(options.state_file, options.access_log, options.redirect_log), redirect_issuers=issuers, native=native)
    elif options.once:
        issuers = discover_redirect_issuers(options.redirect_log)
        refresh(options.state_file, resolver, hosts=selected_hosts(options.state_file, options.access_log, options.redirect_log), redirect_issuers=issuers, native=native)
    else:
        while True:
            time.sleep(REFRESH_INTERVAL)
            try:
                issuers = discover_redirect_issuers(options.redirect_log)
                if refresh(options.state_file, resolver, hosts=selected_hosts(options.state_file, options.access_log, options.redirect_log), redirect_issuers=issuers, native=native):
                    print('Origin hosts/DNS changed; pools refreshed with graceful nginx reload', flush=True)
            except Exception as error:
                print('Origin refresh deferred; retaining last good configuration (' + type(error).__name__ + ')', flush=True)


if __name__ == '__main__':
    main()
