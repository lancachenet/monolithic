# Game Download Cache Docker Container

## Introduction

This docker container provides a caching proxy server for game download content. For any network with more than one PC gamer in connected this will drastically reduce internet bandwidth consumption. 

The primary use case is gaming events, such as LAN parties, which need to be able to cope with hundreds or thousands of computers receiving an unannounced patch - without spending a fortune on internet connectivity. Other uses include smaller networks, such as Internet Cafes and home networks, where the new games are regularly installed on multiple computers; or multiple independent operating systems on the same computer.

This container is designed to support any game that uses HTTP and also supports HTTP range requests (used by Origin). This should make it suitable for:

 - Steam (Valve)
 - Origin (EA Games)
 - Riot Games (League of Legends)
 - Battle.net (Hearthstone, Starcraft 2, Overwatch)
 - Frontier Launchpad (Elite Dangerous, Planet Coaster)
 - Uplay (Ubisoft)
 - Windows Updates

This is the best container to use for all game caching and should be used for Steam in preference to the steamcache/steamcache container.

## Usage

You need to be able to redirect HTTP traffic to this container. The easiest way to do this is to replace the DNS entries for the various game services with your cache server.

You can use the [steamcache-dns](https://hub.docker.com/r/steamcache/steamcache-dns/) docker image to do this or you can use a DNS service already on your network see the [steamcache-dns github page](https://github.com/steamcache/steamcache-dns) for more information.

For the cache files to persist you will need to mount a directory on the host machine into the container. You can do this using `-v <path on host>:/data/cache`. You can do the same with a logs directory as well if you want logs to be persistent as well.

Run the container using the following to allow TCP port 80 (HTTP) and to mount `/cache/steam/data` directory into the container.

```
docker run \
  --restart unless-stopped \
  --name cache-steam \
  -v /cache/steam/data:/data/cache \
  -v /cache/steam/logs:/data/logs \
  -p 192.168.1.10:80:80 \
  steamcache/generic:latest
```

## Caching Multiple Services

If you want to cache multiple game services then you should run multiple instances of the cache and use different IP addresses on the host machine. The first thing is to add an extra IP to your network interface.

You should then create a second data directory on the host and then run the container for the service you want to cache:

```
docker run \
  --restart unless-stopped \
  --name cache-blizzard \
  -v /cache/blizzard/data:/data/cache \
  -v /cache/blizzard/logs:/data/logs \
  -p 192.168.1.11:80:80 \
  steamcache/generic:latest
```

Repeat this for as many services as you want to cache. It is best practice to keep the caches separate for each service to prevent the possibility of overwriting the same data.

## Origin and SSL

Some publishers, including Origin, use the same hostnames we're replacing for HTTPS content as well as HTTP content. We can't cache HTTPS traffic, so if you're intercepting DNS, you will need to run an SNI Proxy container on port 443 to forward on any HTTPS traffic.

```
docker run \
  --restart unless-stopped \
  --name sniproxy \
  -p 443:443 \
  steamcache/sniproxy:latest
```

Please read the [steamcache/sniproxy](https://github.com/steamcache/sniproxy) project for more information.

## DNS Entries

You can find a list of domains you will want to use for each service over on [uklans/cache-domains](https://github.com/uklans/cache-domains). The aim is for this to be a definitive list of all domains you might want to cache.

## Suggested Hardware

Regular commodity hardware (a single 2TB WD Black on an HP Microserver) can achieve peak throughputs of 30MB/s+ using this setup (depending on the specific content being served).

## Changing Upstream DNS

If you need to change the upstream DNS server the cache uses, these are defined by the `UPSTREAM_DNS` environment variable. The defaults are Google DNS (8.8.8.8 and 8.8.4.4).

```
 UPSTREAM_DNS 8.8.8.8 8.8.4.4
```

You can override these using the `-e` argument to docker run and specifying your upstream DNS servers. Multiple upstream dns servers are allowed,  separated by whitespace.

```
-e UPSTREAM_DNS="1.1.1.1 1.0.0.1"
```

## Tweaking Cache sizes

Two environment variables are available to manage both the memory and disk cache for a particular container, and are set to the following defaults.
```
CACHE_MEM_SIZE 500m
CACHE_DISK_SIZE 500000m
```

In addition, there is an environment variable to control the max cache age

```
CACHE_MAX_AGE 3650d
````

You can override these at run time by adding the following to your docker run command.  They accept the standard nginx notation for sizes (k/m/g/t) and durations (m/h/d)

```
-e CACHE_MEM_SIZE=4000m -e CACHE_DISK_SIZE=1000g
```

## Monitoring

Access logs are written to /data/logs. If you don't particularly care about keeping them, you don't need to mount an external volume into the container.

You can tail them using:

```
docker exec -it cache-steam tail -f /data/logs/access.log
```

If you have mounted the volume externally then you can tail it on the host instead.

## Advice to Publishers

If you're a games publisher and you'd like LAN parties, gaming centers and other places to be able to easily cache your game updates, we reccomend the following:

 - If your content downloads are on HTTPS, you can do what Riot have done - try and resolve a specific hostname. If it resolves to a RFC1918 private address, switch your downloads to use HTTP instead.
 - Try to use hostnames specific for your HTTP download traffic.
 - Tell us the hostnames that you're using for your game traffic. We're maintaining a list at [uklans/cache-domains](https://github.com/uklans/cache-domains) and we'll accept pull requests!
 - Have your client verify the files and ensure the file they've downloaded matches the file they **should** have downloaded. This cache server acts as a man-in-the-middle so it would be good to ensure the files are correct.

 If you need any further advice, please contact us and we'll be glad to help!

## Frequently Asked Questions

If you have any questions, please check [our FAQs](faq.md). If this doesn't answer your question, please raise an issue in GitHub.

## Thanks

 - Based on original configs from [ansible-lanparty](https://github.com/ti-mo/ansible-lanparty).
 - Everyone on [/r/lanparty](https://reddit.com/r/lanparty) who has provided feedback and helped people with this.
 - UK LAN Techs for all the support.

## License

The MIT License (MIT)

Copyright (c) 2016 Jessica Smith, Robin Lewis, Brian Wojtczak, Jason Rivers

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
