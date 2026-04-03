export const locales = ['en', 'es', 'de', 'el', 'ru', 'it', 'ar'] as const;
export type Locale = (typeof locales)[number];
export const defaultLocale: Locale = 'en';

export const localeNames: Record<Locale, string> = {
  en: 'English',
  es: 'Espanol',
  de: 'Deutsch',
  el: 'Ellinika',
  ru: 'Russkiy',
  it: 'Italiano',
  ar: 'Al-Arabiyya',
};

export const localeNativeNames: Record<Locale, string> = {
  en: 'English',
  es: 'Espa\u00f1ol',
  de: 'Deutsch',
  el: '\u0395\u03bb\u03bb\u03b7\u03bd\u03b9\u03ba\u03ac',
  ru: '\u0420\u0443\u0441\u0441\u043a\u0438\u0439',
  it: 'Italiano',
  ar: '\u0627\u0644\u0639\u0631\u0628\u064a\u0629',
};

export const rtlLocales: Locale[] = ['ar'];

export function isRtl(locale: Locale): boolean {
  return rtlLocales.includes(locale);
}

export function isValidLocale(value: string): value is Locale {
  return locales.includes(value as Locale);
}
