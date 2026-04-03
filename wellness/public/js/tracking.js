/**
 * GA4 Custom Event Tracking
 * Auto-discovers interactive elements via CSS selectors.
 * Sends events via gtag() — works with any GA4 property already configured.
 */
(function () {
  'use strict';

  // Guard: gtag must exist
  if (typeof gtag !== 'function') return;

  var host = location.hostname;
  var pageTitle = document.title;

  // Helper: determine which section an element is in
  function getSection(el) {
    var node = el;
    while (node && node !== document.body) {
      var tag = node.tagName;
      if (tag === 'NAV' || tag === 'HEADER') return 'header';
      if (tag === 'FOOTER') return 'footer';
      if (tag === 'ARTICLE') return 'article';
      if (tag === 'ASIDE') return 'sidebar';
      if (node.classList && (node.classList.contains('cta') || node.classList.contains('cta-section'))) return 'cta';
      node = node.parentElement;
    }
    return 'other';
  }

  // Helper: truncate string
  function trunc(s, max) {
    if (!s) return '';
    s = s.trim().replace(/\s+/g, ' ');
    return s.length > max ? s.slice(0, max) : s;
  }

  // 1. Scroll Depth (Intersection Observer)
  (function () {
    var thresholds = [25, 50, 75, 100];
    var fired = {};

    function setup() {
      var docHeight = Math.max(
        document.body.scrollHeight,
        document.documentElement.scrollHeight
      );

      thresholds.forEach(function (pct) {
        if (fired[pct]) return;
        var sentinel = document.createElement('div');
        sentinel.style.cssText = 'position:absolute;left:0;width:1px;height:1px;pointer-events:none;';
        sentinel.style.top = Math.min((pct / 100) * docHeight, docHeight - 1) + 'px';
        sentinel.setAttribute('data-scroll-depth', pct);
        document.body.appendChild(sentinel);

        var observer = new IntersectionObserver(function (entries) {
          entries.forEach(function (entry) {
            if (entry.isIntersecting && !fired[pct]) {
              fired[pct] = true;
              gtag('event', 'scroll_depth', {
                depth: String(pct),
                page_title: pageTitle
              });
              observer.disconnect();
              sentinel.remove();
            }
          });
        }, { threshold: 0 });

        observer.observe(sentinel);
      });
    }

    if (document.readyState === 'complete') {
      setup();
    } else {
      window.addEventListener('load', setup);
    }
  })();

  // 2. Reading Time (visibility-aware, idle-aware)
  (function () {
    var milestones = [30, 60, 180, 300];
    var firedMs = {};
    var elapsed = 0;
    var lastTick = 0;
    var active = true;
    var idleTimer = null;
    var IDLE_TIMEOUT = 30000;

    function resetIdle() {
      active = true;
      clearTimeout(idleTimer);
      idleTimer = setTimeout(function () { active = false; }, IDLE_TIMEOUT);
    }

    function tick() {
      var now = Date.now();
      if (active && document.visibilityState === 'visible' && lastTick > 0) {
        var delta = (now - lastTick) / 1000;
        if (delta < 2) elapsed += delta;
      }
      lastTick = now;

      milestones.forEach(function (s) {
        if (!firedMs[s] && elapsed >= s) {
          firedMs[s] = true;
          gtag('event', 'reading_time', {
            seconds: s,
            page_title: pageTitle
          });
        }
      });
    }

    setInterval(tick, 1000);
    resetIdle();

    ['mousemove', 'keydown', 'scroll', 'touchstart'].forEach(function (evt) {
      document.addEventListener(evt, resetIdle, { passive: true });
    });

    document.addEventListener('visibilitychange', function () {
      if (document.visibilityState === 'visible') {
        lastTick = Date.now();
        resetIdle();
      }
    });
  })();

  // 3-4, 6. Click Tracking (event delegation)
  document.addEventListener('click', function (e) {
    // Social share links (check before generic link handling)
    var shareLink = e.target.closest(
      'a[href*="twitter.com/intent"], a[href*="x.com/intent"], a[href*="facebook.com/sharer"]'
    );
    if (shareLink) {
      var platform = 'unknown';
      var sh = shareLink.href;
      if (sh.indexOf('twitter.com') !== -1 || sh.indexOf('x.com') !== -1) platform = 'twitter';
      else if (sh.indexOf('facebook.com') !== -1) platform = 'facebook';
      gtag('event', 'social_share', { platform: platform, page_title: pageTitle });
      return;
    }

    // Copy-link button
    var copyBtn = e.target.closest('.copy-link, [data-share="copy"]');
    if (copyBtn) {
      gtag('event', 'social_share', { platform: 'copy_link', page_title: pageTitle });
      return;
    }

    // Link clicks (outbound + internal)
    var link = e.target.closest('a[href]');
    if (link) {
      var href = link.href;
      var linkText = trunc(link.textContent, 100);
      try {
        var url = new URL(href);
        if (url.hostname !== host) {
          // Outbound
          gtag('event', 'outbound_click', {
            url: href,
            link_text: linkText,
            destination: url.hostname,
            page_title: pageTitle
          });
          if (url.hostname.indexOf('mirai-skin.com') !== -1) {
            gtag('event', 'product_click', {
              product_url: href,
              source_page: location.pathname
            });
          }
        } else if (url.pathname !== location.pathname) {
          // Internal
          gtag('event', 'internal_click', {
            destination: url.pathname,
            link_text: linkText,
            section: getSection(link)
          });
        }
      } catch (_) {}
    }
  }, true);

  // 5. Newsletter Form Submissions
  document.addEventListener('submit', function (e) {
    var form = e.target;
    if (!form || form.tagName !== 'FORM') return;
    if (!form.querySelector('input[type="email"]')) return;

    var formLoc = 'main';
    var node = form;
    while (node && node !== document.body) {
      if (node.tagName === 'FOOTER') { formLoc = 'footer'; break; }
      node = node.parentElement;
    }

    gtag('event', 'newsletter_signup', { form_location: formLoc });
  }, true);

  // 7. Ingredient Checker Tool (cosmetics only)
  (function () {
    var resultsSection = document.getElementById('results-section');
    if (!resultsSection) return;

    var resultsObserved = false;

    document.addEventListener('click', function (e) {
      var pill = e.target.closest('.ingredient-pill');
      if (pill) {
        var ing = pill.getAttribute('data-ing');
        setTimeout(function () {
          var isSelected = pill.classList.contains('bg-rose-600');
          var allSelected = document.querySelectorAll('.ingredient-pill.bg-rose-600');
          gtag('event', 'tool_ingredient_select', {
            ingredient: ing,
            action: isSelected ? 'add' : 'remove',
            total_selected: allSelected.length
          });
        }, 50);
        return;
      }

      var preset = e.target.closest('.preset-btn');
      if (preset) {
        gtag('event', 'tool_preset_click', {
          preset_name: trunc(preset.textContent, 50)
        });
        return;
      }

      if (e.target.closest('#reset-btn')) {
        gtag('event', 'tool_reset', {});
      }
    });

    var resultsObserver = new MutationObserver(function () {
      if (!resultsSection.classList.contains('hidden') && !resultsObserved) {
        resultsObserved = true;
        gtag('event', 'tool_results_viewed', {
          ingredients_count: document.querySelectorAll('.ingredient-pill.bg-rose-600').length,
          conflicts_red: document.querySelectorAll('#conflict-red-list > *').length,
          conflicts_yellow: document.querySelectorAll('#conflict-yellow-list > *').length,
          conflicts_green: document.querySelectorAll('#conflict-green-list > *').length
        });
      }
      if (resultsSection.classList.contains('hidden')) {
        resultsObserved = false;
      }
    });

    resultsObserver.observe(resultsSection, { attributes: true, attributeFilter: ['class'] });
  })();

  // 8. Article Engagement
  (function () {
    var article = document.querySelector('article');
    if (!article) return;

    var title = pageTitle;
    var category = '';
    var metaSection = document.querySelector('meta[property="article:section"]');
    if (metaSection) category = metaSection.getAttribute('content') || '';

    var wordCount = (article.textContent || '').trim().split(/\s+/).filter(Boolean).length;

    gtag('event', 'article_start', {
      title: title,
      category: category,
      word_count: wordCount
    });

    // article_complete at 90% scroll through article
    var completeFired = false;
    var startTime = Date.now();

    var children = article.children;
    if (children.length === 0) return;

    var completionSentinel = document.createElement('div');
    completionSentinel.style.cssText = 'width:1px;height:1px;pointer-events:none;';

    var insertIndex = Math.floor(children.length * 0.9);
    if (insertIndex >= children.length) {
      article.appendChild(completionSentinel);
    } else {
      article.insertBefore(completionSentinel, children[insertIndex]);
    }

    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting && !completeFired) {
          completeFired = true;
          gtag('event', 'article_complete', {
            title: title,
            category: category,
            time_spent_seconds: Math.round((Date.now() - startTime) / 1000)
          });
          observer.disconnect();
        }
      });
    }, { threshold: 0 });

    observer.observe(completionSentinel);
  })();

})();
