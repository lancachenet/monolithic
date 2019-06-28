# Frequently Asked Questions

## What is a LAN Cache or Steam Cache?

A Steam Cache or LAN Cache is a way of speeding up Steam or other content downloads on a local area network for multiple users.

## How does it work?

The Cache works as a simple caching proxy server. Most game and content updates use unsecured HTTP for downloading the content. We are able to intercept these download requests and save them, so that if another request is made for the same file, we don't need to download it again from the Internet.

## This doesn't sound very new or original, we've been using caches for years

You're correct. HTTP caches are not a new thing, many businesses and organisations such as universities and schools have been running them for a while, however they are normally intended for caching traditional web traffic with short caching lifetimes and small files.

## Why not use Squid or another server?

We chose nginx as it offers the flexibility we need to overwrite cache keys and optimise the cache performance to cope with gaming update traffic. We need to be able to cache files for a long period of time, rewrite upstream HTTP headers and to be able to exclude the hostname of the server from the cache key, to allow us to cache content served from Content Delivery Networks (CDNs)

## Should I use this then?

It depends on your situation. If you just have a single PC and you download games to it once, you probably won't see any advantage or benefit from using the cache. It won't speed up your downloads of **new** content. It would speed up downloads if you removed the game and then re-installed it.

If you have multiple computers sharing one Internet connection, you would see a benefit to it. If user A downloads Team Fortress 2 on Steam, it will download at the speed of your Internet Connection and stored on the cache server. Once it's been downloaded, if user B downloads Team Fortress 2, it will be served up from your cache server at the maximum speed it can read the files from storage.

## So can I really get 10gbps downloads for my games?

Yes, but it relies on a few things:

 1. You have already downloaded the content and it is on your cache server.
 2. Your network switch, network card in the cache server and PC network are 10gbps.
 3. You can read the files from disk at 10gbps.

Realistic performance you can expect from the cache depends on all of these things.

## You mentioned storage, how fast does my storage need to be?

As fast as possible. Linux is great in that it will cache in memory any files accessed from disk, so if someone accesses the same files multiple times, and they haven't changed, those files will be served from memory, which is very quick.

If the files aren't cached in memory, the OS will need to read it from the disk. If you have mechnical drives, this can be slow, and if you're reading from different areas of the disk, this will slow things down further. SSDs are quicker and if you use RAID, you can improve things even further.

If you can't afford a large SSD, you can also use lvmcache and set up the SSD to act as a read cache for the rotational disk. This will give you three levels of caching:

 1. RAM
 2. SSD based lvmcache
 3. Rotational Hard Disk

If you can afford large SSDs, then run your entire cache using SSDs!

## Why do you mention you support Windows Update, can't we use WSUS?

This cache is intended for a LAN party environment where you have no control over the computers on the network. To force them to use a WSUS server, you'd need to either join them to a domain and push the config out through group policy or run a script to get them to use the WSUS server. Each of which is not really possible for a LAN party

This solution is designed to support anything from a couple of people at home, to thousands of people at gaming events. This is the easiest way to achieve the caching of services like Windows Update, without modifying people's computers.

## But what about HTTPS, can I cache HTTPS?

No. HTTPS traffic is encrypted. Some of the games, Origin for instance, also serve HTTPS content on the same hostnames we're intercepting - for this you can use SNI Proxy. It listens on port 443 and just passes through any HTTPS traffic. It is unable to inspect the traffic, or cache it.

You can find more at the [lancachenet/sniproxy](https://github.com/lancachenet/sniproxy) project page.

## Can I cache Fortnite/Epic Games Launcher?

Yes, as of [2019-05-30](https://github.com/uklans/cache-domains/pull/89) - Epic Games have kindly moved their CDN servers and launcher to use HTTP for content delivery.

## Can I cache *some other service*

Yes, almost any HTTP content can be cached. We're maintaining a list of hostnames for various update services on the [uklans/cache-domains](https://github.com/uklans/cache-domains) project. There's a lot of services you can cache!

## How do you intercept the HTTP traffic?

We prefer to use DNS-based interception This is because it is easier to deploy than other methods. We have a [lancache-dns](https://github.com/lancachenet/lancache-dns) project that is a self-contained DNS server with options for setting your cache IP addresses.

If you already run a DNS server and are comfortable configuring new override DNS zones, you can also just do this from the list on [uklans/cache-domains](https://github.com/uklans/cache-domains). pfSense's DNS forwarder can easily be configured, and the project has scripts to generate config for unbound.

Other options also involve transparently intercepting HTTP traffic at a network level either using WCCP on Cisco switches or on your router if it supports it.

## Can I load some content into the cache ahead of my event?

You could look at [zeropingheroes/lancache-autofill](https://github.com/zeropingheroes/lancache-autofill) as an aide to pre-loading popular games into the cache ahead of time to help kick start the cache
