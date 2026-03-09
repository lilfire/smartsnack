// ── i18n (Internationalization) ─────────────────────
import { state, api } from './state.js';

var currentLang = 'no';
var translations = {};

export function t(key, params) {
  var text = translations[key] || key;
  if (params) {
    Object.keys(params).forEach(function(k) {
      text = text.replace(new RegExp('\\{' + k + '\\}', 'g'), function() { return params[k]; });
    });
  }
  return text;
}

export function getCurrentLang() { return currentLang; }

async function loadTranslations(lang) {
  try {
    var data = await api('/api/translations/' + lang);
    if (!data || data.error) return false;
    translations = data;
    currentLang = lang;
    return true;
  } catch(e) { return false; }
}

export async function initLanguage() {
  try {
    var data = await api('/api/settings/language');
    currentLang = data.language || 'no';
  } catch(e) { currentLang = 'no'; }
  await loadTranslations(currentLang);
  applyStaticTranslations();
}

export function applyStaticTranslations() {
  document.querySelectorAll('[data-i18n]').forEach(function(el) {
    var key = el.getAttribute('data-i18n');
    el.textContent = t(key);
  });
  document.querySelectorAll('[data-i18n-html]').forEach(function(el) {
    var key = el.getAttribute('data-i18n-html');
    el.textContent = t(key);
  });
  document.querySelectorAll('[data-i18n-placeholder]').forEach(function(el) {
    var key = el.getAttribute('data-i18n-placeholder');
    el.placeholder = t(key);
  });
  document.querySelectorAll('[data-i18n-title]').forEach(function(el) {
    var key = el.getAttribute('data-i18n-title');
    el.title = t(key);
  });
  document.documentElement.lang = currentLang;
}

export async function changeLanguage(lang) {
  var ok = await loadTranslations(lang);
  if (!ok) return;
  await api('/api/settings/language', { method: 'PUT', body: JSON.stringify({ language: lang }) });
  applyStaticTranslations();
  // Reload dynamic content — use lazy imports to avoid circular deps
  if (state.currentView === 'settings') {
    var { loadSettings } = await import('./settings.js');
    await loadSettings();
  } else {
    var { loadData } = await import('./products.js');
    await loadData();
  }
}
