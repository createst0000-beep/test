// プッシュ通知を受けて、音（端末の通知音）とバイブで知らせる
self.addEventListener('push', (event) => {
  let d = { title: '食事の写真を送ってください', body: '', url: '/', tag: 'meal' };
  try { d = Object.assign(d, event.data.json()); } catch (e) {}
  event.waitUntil(self.registration.showNotification(d.title, {
    body: d.body,
    tag: d.tag,
    renotify: true,             // 同じ tag でも毎回鳴らす
    requireInteraction: true,   // タップするまで消えない
    silent: false,              // 端末の通知音を鳴らす
    vibrate: [300, 150, 300, 150, 600],
    icon: '/static/icon.svg',
    badge: '/static/icon.svg',
    data: { url: d.url },
    actions: [{ action: 'open', title: '撮影する' }],
  }));
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || '/';
  event.waitUntil(clients.matchAll({ type: 'window' }).then((list) => {
    for (const c of list) { if ('focus' in c) { c.navigate(url); return c.focus(); } }
    return clients.openWindow(url);
  }));
});

self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (e) => e.waitUntil(self.clients.claim()));
