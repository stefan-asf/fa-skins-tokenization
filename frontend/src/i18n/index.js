const SUPPORTED_LOCALES = ["en_US", "ru_RU"];
const DEFAULT_LOCALE = "en_US";

let _strings = {};
let _locale = DEFAULT_LOCALE;

async function loadLocale(locale) {
  const res = await fetch(`/i18n/${locale}.json`);
  if (!res.ok) throw new Error(`Failed to load locale: ${locale}`);
  return res.json();
}

export async function initI18n() {
  const saved = localStorage.getItem("locale");
  const browserLang = navigator.language.replace("-", "_");
  const matched = SUPPORTED_LOCALES.find((l) => l === saved || l.startsWith(browserLang.slice(0, 2)));
  _locale = matched || DEFAULT_LOCALE;
  _strings = await loadLocale(_locale);
  document.documentElement.lang = _locale.slice(0, 2);
}

export function t(key) {
  const parts = key.split(".");
  let val = _strings;
  for (const p of parts) {
    val = val?.[p];
    if (val === undefined) return key;
  }
  return val ?? key;
}

export function getLocale() {
  return _locale;
}

export async function setLocale(locale) {
  if (!SUPPORTED_LOCALES.includes(locale)) return;
  _locale = locale;
  localStorage.setItem("locale", locale);
  _strings = await loadLocale(locale);
  document.dispatchEvent(new CustomEvent("localechange"));
}

export { SUPPORTED_LOCALES };
