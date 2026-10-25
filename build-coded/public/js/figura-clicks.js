/* Stamp UTMs on figura3d.ai outbound links; best-effort figura_cta_click. Never block navigation. */
(function () {
  'use strict';
  if (!['build-coded.com', 'www.build-coded.com'].includes(location.hostname)) return;

  function sourcePath() {
    var canonical = document.querySelector('link[rel="canonical"]');
    try {
      return canonical ? new URL(canonical.href).pathname : location.pathname;
    } catch (_) {
      return location.pathname;
    }
  }

  function placementFor(link, destination) {
    var explicit = link.getAttribute('data-figura-placement');
    if (explicit) return explicit;
    var p = destination.pathname.replace(/\/$/, '') || '/';
    if (p === '/pages/create') return 'create-primary';
    if (p === '/pages/print-at-home') return 'print-at-home';
    if (p === '/pages/gallery') return 'gallery';
    if (p === '/pages/pricing') return 'pricing';
    if (p === '/pages/faq') return 'faq';
    return 'inline';
  }

  function tagFiguraLink(link) {
    if (!link) return;
    try {
      var destination = new URL(link.href);
      if (destination.protocol !== 'https:') return;
      if (!['figura3d.ai', 'www.figura3d.ai'].includes(destination.hostname)) return;
      var tags = {
        utm_source: 'build-coded.com',
        utm_medium: 'affiliate',
        utm_campaign: 'figura_3d',
        utm_content: sourcePath(),
        utm_term: placementFor(link, destination)
      };
      Object.keys(tags).forEach(function (key) {
        if (!destination.searchParams.has(key)) destination.searchParams.set(key, tags[key]);
      });
      link.href = destination.href;
    } catch (_) { /* A tagging failure must never block the link. */ }
  }

  function tagAll() {
    document.querySelectorAll('a[href]').forEach(tagFiguraLink);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', tagAll, { once: true });
  } else {
    tagAll();
  }
  ['pointerdown', 'click', 'auxclick', 'contextmenu'].forEach(function (event) {
    document.addEventListener(event, function (e) {
      tagFiguraLink(e.target && e.target.closest ? e.target.closest('a[href]') : null);
    }, true);
  });

  function record(event) {
    if (!event.isTrusted || (event.type === 'auxclick' && event.button !== 1)) return;
    if (navigator.globalPrivacyControl || navigator.doNotTrack === '1' || window['ga-disable-G-MP5LPFNBN5'] || typeof window.gtag !== 'function') return;
    var link = event.target && event.target.closest ? event.target.closest('a[href]') : null;
    if (!link) return;
    try {
      var destination = new URL(link.href);
      if (destination.protocol !== 'https:' || !['figura3d.ai', 'www.figura3d.ai'].includes(destination.hostname)) return;
      window.gtag('event', 'figura_cta_click', {
        link_url: destination.origin + destination.pathname,
        source_page: sourcePath(),
        placement: placementFor(link, destination),
        transport_type: 'beacon'
      });
    } catch (_) { /* A measurement failure must never block the Figura link. */ }
  }
  document.addEventListener('click', record);
  document.addEventListener('auxclick', record);
})();
