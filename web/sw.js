"use strict";
const CACHE="dominio-interface-v9", ARQUIVOS=["/","/static/app.css","/static/app.js","/static/lotes.js","/static/icone.svg","/static/icone-192.png","/static/icone-512.png","/static/manifest.webmanifest"];
self.addEventListener("install",e=>{e.waitUntil(caches.open(CACHE).then(c=>c.addAll(ARQUIVOS))); self.skipWaiting();});
self.addEventListener("activate",e=>{e.waitUntil(caches.keys().then(chaves=>Promise.all(chaves.filter(c=>c!==CACHE).map(c=>caches.delete(c)))).then(()=>self.clients.claim()));});
self.addEventListener("fetch",e=>{
  const url=new URL(e.request.url);
  // Sem cache de chave, pedido, resposta API ou arquivo fiscal.
  if (e.request.method!=="GET" || url.origin!==self.location.origin || !ARQUIVOS.includes(url.pathname)) return;
  e.respondWith(fetch(e.request).then(resposta=>{if (resposta.ok) {const copia=resposta.clone(); e.waitUntil(caches.open(CACHE).then(c=>c.put(e.request,copia)));} return resposta;}).catch(()=>caches.match(e.request)));
});
