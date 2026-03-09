// ── i18n (Internationalization) ─────────────────────
import { state, api } from './state.js';

let currentLang = 'no';
let translations = {};

// Pre-compiled regex for parameter substitution
const _paramRegex = /\{(\w+)\}/g;

export function t(key, params) {
  let text = translations[key] || key;
  if (params) {
    text = text.replace(_paramRegex, (match, k) => params[k] !== undefined ? params[k] : match);
  }
  return text;
}

export function getCurrentLang() { return currentLang; }

async function loadTranslations(lang) {
  try {
    const data = await api('/api/translations/' + lang);
    if (!data || data.error) return false;
    translations = data;
    currentLang = lang;
    return true;
  } catch(e) { return false; }
}

export async function initLanguage() {
  try {
    const data = await api('/api/settings/language');
    currentLang = data.language || 'no';
  } catch(e) { currentLang = 'no'; }
  await loadTranslations(currentLang);
  applyStaticTranslations();
}

export function applyStaticTranslations() {
  document.querySelectorAll('[data-i18n]').forEach((el) => {
    el.textContent = t(el.getAttribute('data-i18n'));
  });
  document.querySelectorAll('[data-i18n-html]').forEach((el) => {
    el.innerHTML = t(el.getAttribute('data-i18n-html'));
  });
  document.querySelectorAll('[data-i18n-placeholder]').forEach((el) => {
    el.placeholder = t(el.getAttribute('data-i18n-placeholder'));
  });
  document.querySelectorAll('[data-i18n-title]').forEach((el) => {
    el.title = t(el.getAttribute('data-i18n-title'));
  });
  document.documentElement.lang = currentLang;
}

export async function changeLanguage(lang) {
  const ok = await loadTranslations(lang);
  if (!ok) return;
  await api('/api/settings/language', { method: 'PUT', body: JSON.stringify({ language: lang }) });
  applyStaticTranslations();
  // Reload dynamic content — use lazy imports to avoid circular deps
  if (state.currentView === 'settings') {
    const { loadSettings } = await import('./settings.js');
    await loadSettings();
  } else {
    const { loadData } = await import('./products.js');
    await loadData();
  }
}
