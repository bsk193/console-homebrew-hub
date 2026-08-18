var CACHE = 'chh-v4';
var PRECACHE = [
  '/', '/index.html',
  '/console-nav.js',
  '/ps5/', '/ps5/index.html',
  '/ps5/browser/', '/ps5/browser/index.html',
  '/ps5/payloads/', '/ps5/payloads/index.html',
  '/ps5/exploits/slopkit/', '/ps5/exploits/slopkit/index.html',
  '/ps5/exploits/umtx/', '/ps5/exploits/umtx/index.html',
  '/ps5/exploits/ipv6/', '/ps5/exploits/ipv6/index.html',
  '/ps4/', '/ps3/', '/vita/', '/switch/', '/switch2/',
  /* Exploit core entry points — cloned at deploy time, needed for offline shortcut use */
  '/ps5/exploits/umtx/core/document/en/ps5/index.html',
  '/ps5/exploits/ipv6/core/document/en/ps5/index.html',
  '/ps5/exploits/slopkit/core/slopkit/poops.html',
  /* ELF payloads — cached for offline shortcut use */
  '/pldmgrx.elf',
  '/chh-installer.elf',
];

self.addEventListener('install', function (e) {
  e.waitUntil(
    caches.open(CACHE).then(function (c) {
      return Promise.allSettled(PRECACHE.map(function (u) {
        return c.add(u).catch(function () {});
      }));
    }).then(function () { return self.skipWaiting(); })
  );
});

self.addEventListener('activate', function (e) {
  e.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(keys.filter(function (k) { return k !== CACHE; }).map(function (k) { return caches.delete(k); }));
    }).then(function () { return self.clients.claim(); })
  );
});

/* Cache-warm on demand: exploit wrappers send this after install success */
self.addEventListener('message', function (e) {
  if (!e.data || e.data.type !== 'CACHE_URLS') return;
  e.waitUntil(
    caches.open(CACHE).then(function (c) {
      return Promise.allSettled((e.data.urls || []).map(function (u) {
        return fetch(u).then(function (r) { return c.put(u, r); }).catch(function () {});
      }));
    })
  );
});

self.addEventListener('fetch', function (e) {
  var url = e.request.url;
  /* Cache-first for ELFs, bins, and exploit core resources (JS/data inside core/) */
  var cacheFirst = /\.(elf|bin)$|\?v=|\/offsets\/|\/core\//.test(url);
  if (cacheFirst) {
    e.respondWith(caches.match(e.request).then(function (r) {
      return r || fetch(e.request).then(function (res) {
        var clone = res.clone();
        caches.open(CACHE).then(function (c) { c.put(e.request, clone); });
        return res;
      });
    }));
    return;
  }
  /* Network-first for HTML and everything else */
  e.respondWith(
    fetch(e.request).then(function (res) {
      var clone = res.clone();
      caches.open(CACHE).then(function (c) { c.put(e.request, clone); });
      return res;
    }).catch(function () { return caches.match(e.request); })
  );
});
