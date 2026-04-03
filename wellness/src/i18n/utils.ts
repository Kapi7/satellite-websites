import type { Locale } from './locales';
import { defaultLocale, isValidLocale, locales } from './locales';

// Import all translation files
import en from './translations/en.json';
import es from './translations/es.json';
import de from './translations/de.json';
import el from './translations/el.json';
import ru from './translations/ru.json';
import it from './translations/it.json';
import ar from './translations/ar.json';

const translations: Record<Locale, Record<string, any>> = { en, es, de, el, ru, it, ar };

/**
 * Get a translated string by dot-notation key. Falls back to English.
 */
export function t(locale: Locale, key: string): string {
  const keys = key.split('.');
  let result: any = translations[locale];
  for (const k of keys) {
    result = result?.[k];
  }
  if (typeof result === 'string') return result;

  // Fallback to English
  let fallback: any = translations[defaultLocale];
  for (const k of keys) {
    fallback = fallback?.[k];
  }
  return typeof fallback === 'string' ? fallback : key;
}

/**
 * Build a locale-aware path.
 * English (default) stays at root, others get prefix.
 */
export function localePath(path: string, locale: Locale): string {
  const clean = path.startsWith('/') ? path : `/${path}`;
  if (locale === defaultLocale) return clean;
  return `/${locale}${clean}`;
}

/**
 * Extract locale from a URL pathname.
 */
export function getLocaleFromUrl(url: URL): Locale {
  const segments = url.pathname.split('/').filter(Boolean);
  const first = segments[0];
  if (first && isValidLocale(first)) return first;
  return defaultLocale;
}

/**
 * Get the path without the locale prefix.
 */
export function getPathWithoutLocale(url: URL): string {
  const segments = url.pathname.split('/').filter(Boolean);
  const first = segments[0];
  if (first && isValidLocale(first) && first !== defaultLocale) {
    return '/' + segments.slice(1).join('/') + (url.pathname.endsWith('/') ? '/' : '');
  }
  return url.pathname;
}

/**
 * Format a date for the given locale.
 */
export function formatDate(date: Date, locale: Locale): string {
  const localeMap: Record<Locale, string> = {
    en: 'en-US',
    es: 'es-ES',
    de: 'de-DE',
    el: 'el-GR',
    ru: 'ru-RU',
    it: 'it-IT',
    ar: 'ar-SA',
  };
  return date.toLocaleDateString(localeMap[locale], {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });
}

export function formatDateShort(date: Date, locale: Locale): string {
  const localeMap: Record<Locale, string> = {
    en: 'en-US',
    es: 'es-ES',
    de: 'de-DE',
    el: 'el-GR',
    ru: 'ru-RU',
    it: 'it-IT',
    ar: 'ar-SA',
  };
  return date.toLocaleDateString(localeMap[locale], {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

/** All supported locales (re-export for convenience) */
export { locales, defaultLocale } from './locales';
export type { Locale } from './locales';
