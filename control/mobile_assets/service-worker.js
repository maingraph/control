const CACHE="control-shell-v1";
const SHELL=["/app","/assets/mobile.css","/assets/mobile.js","/assets/control-icon.svg","/manifest.webmanifest"];
self.addEventListener("install", event => {event.waitUntil(caches.open(CACHE).then(c=>c.addAll(SHELL)));self.skipWaiting();});
self.addEventListener("activate", event => {event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==CACHE).map(k=>caches.delete(k)))));self.clients.claim();});
self.addEventListener("fetch", event => {
 const url=new URL(event.request.url);
 if (event.request.method!=="GET"||url.origin!==self.location.origin||!SHELL.includes(url.pathname))return;
 event.respondWith(fetch(event.request).then(response=>{if(response.ok){const clone=response.clone();caches.open(CACHE).then(cache=>cache.put(event.request,clone));}return response;}).catch(()=>caches.match(event.request)));
});