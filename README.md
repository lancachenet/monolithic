# Monolithic Game Download Cache Docker Container

![Docker Pulls](https://img.shields.io/docker/pulls/lancachenet/monolithic?label=Monolithic) ![Docker Pulls](https://img.shields.io/docker/pulls/lancachenet/lancache-dns?label=Lancache-dns) ![Docker Pulls](https://img.shields.io/docker/pulls/lancachenet/sniproxy?label=Sniproxy) ![Docker Pulls](https://img.shields.io/docker/pulls/lancachenet/generic?label=Generic)

## Documentation

The documentation for the LanCache.net project can be found on [our website](http://www.lancache.net)

The specific documentation for this monolithic container is [here](http://lancache.net/docs/containers/monolithic/)

If you have any problems after reading the documentation please see [the support page](http://lancache.net/support/) before opening a new issue on github.

## Experimental origin connection reuse

`ORIGIN_KEEPALIVE_ENABLED=true` opts in to per-origin HTTP/1.1 keepalive pools.
The default is `false`; normal nginx routing is retained when disabled.
The optional implementation discovers real hostnames and redirect targets from
its own hostname-only JSON log, independently of the main access-log format. It also pools the internal
cache-to-proxy hop, HTTP/HTTPS redirect targets, and existing updater exceptions.
Original Host, signed path/query, TLS SNI, slice size and cache keys are preserved.

For observed HTTP redirect issuers, an internal loopback-only listener on 3129
finishes the origin response before the outer proxy intercepts its redirect.
This addresses an extra source of connection churn beyond adding HTTP/1.1 to
the primary location. Do not publish this port. Existing interception semantics
remain limited to 301/302/307; relative redirects, nonstandard ports and arbitrary
redirect chains are not expanded by this feature. TCP TLS passthrough is unchanged.

The helper requires Python 3; `dig` is used only in the managed DNS path.
`ORIGIN_KEEPALIVE_DNS_MODE=auto` selects native hostname/`zone`/`resolve` pools on
nginx >= 1.27.3 and compatible numeric-address pools on older nginx. Native DNS
uses nginx's resolver timers: address changes do not run helper DNS queries or
reload workers. New hostname/redirect-issuer sets still require validated reloads.
This does not assume that a variable `proxy_pass` automatically gains a pool.
The Dockerfile retains the existing upstream base; using native mode requires an
appropriately upgraded base image, not copying incompatible nginx modules over it.

Both paths support IPv4 and IPv6 origins. `ORIGIN_KEEPALIVE_IPV6=off` disables
AAAA origin lookups and removes saved IPv6 peers during managed warm restart.
Resolver servers themselves may use either family regardless of the origin
setting, and may specify ports (bracket IPv6 resolver addresses). Both DNS paths
query `UPSTREAM_DNS`, avoiding system DNS that may point back at LANCache. Managed
pools reject local/loopback/link-local origin addresses; native pools follow the
configured trusted resolver as nginx's existing dynamic forwarding does.

Optional tuning (positive seconds/counts):

| Variable | Default | Purpose |
| --- | --- | --- |
| `ORIGIN_KEEPALIVE_DNS_MODE` | `auto` | `auto`, `native` (requires nginx >=1.27.3), or `managed` |
| `ORIGIN_KEEPALIVE_IPV6` | `on` | Enable IPv6 origins; use `off` for IPv4-only networks |
| `ORIGIN_KEEPALIVE_MAX_HOSTS` | `64` | Active host limit, capped at 1024; managed resolver entries are limited to twice this count |
| `ORIGIN_KEEPALIVE_INTERVAL` | `15` | Hostname discovery interval |
| `ORIGIN_KEEPALIVE_DNS_TTL` | `300` | Managed DNS cache lifetime or native nginx resolver validity |
| `ORIGIN_KEEPALIVE_DNS_FAILURE_TTL` | `30` | Managed DNS retry interval; native mode uses nginx's resolver behavior |
| `ORIGIN_KEEPALIVE_SEED_HOSTS` | empty | Optional comma/space-separated names to warm before traffic arrives |

Pool definitions and issuer state live in `/data/info/cdn-origin/upstreams.conf`;
persist `/data/info` to reuse the known hosts. Managed mode also persists numeric
addresses and can warm-start from them while DNS is offline. Native mode persists
names: its first lookup after a restart still requires DNS. Transient native
SERVFAIL retention is tested at runtime; this does not promise stale-address
serving for every DNS failure type. Mode/version rollback rewrites incompatible
native syntax to compatible routing when addresses cannot be obtained offline.
Updates use atomic writes, `nginx -t`, graceful reload and file rollback.

Discovery writes only `host` and `redirect_host` to
`/data/logs/origin-hosts.jsonl`. It does not copy signed URLs, credentials or query
strings. The helper reads a bounded tail and truncates this owned log above
1 MiB; it never truncates the user's main access log. Main text, JSON or custom
log formats do not affect discovery. Old default-text/redirect files remain
readable when explicitly supplied through the helper's command-line options.

Run `python3 -m unittest discover -s tests -v` for discovery, native/managed mode
selection and migration, IPv4/IPv6 state, bounded storage and rollback tests.
`tests/integration_origin_dns.py` additionally serves local DNS, HTTP and HTTPS
origins, loads the actual opt-in snippets and checks transfers, connection reuse,
Host/query/SNI, IPv6 failure fallback, custom-main-log discovery and, on a modern
nginx, DNS rotation without replacing workers. Run it in an isolated container
with no network or production data mounts:

```sh
docker build --network=host -f tests/Dockerfile.origin-dns -t origin-dns-fixture .
docker run --rm --network=none origin-dns-fixture
```

The pinned fixture is separate from the deployment image. To run the same script
against an existing compatible monolithic image, mount this checkout read-only
at `/src`, override its entrypoint with `python3`, and execute
`/src/tests/integration_origin_dns.py`. The fixture uses privileged port numbers
inside its own network namespace and publishes no host ports.

Local short A/B samples using the same CDN IP/request and 32-way concurrency
measured 96.94 MB/s with fresh HTTP/1.0 connections and 154.96 MB/s with pools,
with zero request errors. These are workload-specific samples, not sustained
client throughput guarantees. Three updater exceptions were checked as nginx
configuration only, without their native clients. See existing upstream issue
[#202](https://github.com/lancachenet/monolithic/issues/202) and PR
[#217](https://github.com/lancachenet/monolithic/pull/217) for related work; this
experimental implementation is offered for discussion of the additional scope.

## Thanks

- Based on original configs from [ansible-lanparty](https://github.com/ti-mo/ansible-lanparty).
- Everyone on [/r/lanparty](https://reddit.com/r/lanparty) who has provided feedback and helped people with this.
- UK LAN Techs for all the support.

## License

The MIT License (MIT)

Copyright (c) 2019 Jessica Smith, Robin Lewis, Brian Wojtczak, Jason Rivers, James Kinsman

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
