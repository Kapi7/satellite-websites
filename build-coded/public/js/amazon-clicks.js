/* Measure deliberate retailer clicks, never inferred purchases. No query strings or form inputs. */
(function () {
  'use strict';
  if (!['build-coded.com', 'www.build-coded.com'].includes(location.hostname)) return;
  function record(event) {
    if (!event.isTrusted || (event.type === 'auxclick' && event.button !== 1)) return;
    if (navigator.globalPrivacyControl || navigator.doNotTrack === '1' || window['ga-disable-G-MP5LPFNBN5'] || typeof window.gtag !== 'function') return;
    var link = event.target && event.target.closest ? event.target.closest('a[data-retailer="amazon-us"][data-product]') : null;
    if (!link) return;
    try {
      var destination = new URL(link.href);
      if (destination.protocol !== 'https:' || destination.hostname !== 'www.amazon.com' || !/^\/dp\/[A-Z0-9]{10}$/.test(destination.pathname)) return;
      var canonical = document.querySelector('link[rel="canonical"]');
      var page = canonical ? new URL(canonical.href).pathname : location.pathname;
      // Uses the existing gtag pipeline and its consent state; does not update consent.
      window.gtag('event', 'amazon_product_click', {
        retailer: 'amazon_us', product_id: link.dataset.product,
        link_url: destination.origin + destination.pathname,
        source_page: page, placement: link.dataset.placement || 'product-link',
        transport_type: 'beacon'
      });
    } catch (_) { /* A measurement failure must never block the retailer link. */ }
  }
  document.addEventListener('click', record);
  document.addEventListener('auxclick', record);
})();
