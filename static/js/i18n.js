// ── i18n (Internationalization) ─────────────────────
import { state, api, setTranslationFunc } from './state.js';

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

// Register t() with state.js so catLabel() can translate without circular imports
setTranslationFunc(t);

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
  window.__t = t;
  applyStaticTranslations();
}

export function applyStaticTranslations() {
  document.querySelectorAll('[data-i18n]').forEach((el) => {
    const key = el.getAttribute('data-i18n');
    const params = {};
    let hasParams = false;
    for (const attr of el.attributes) {
      if (attr.name.startsWith('data-i18n-param-')) {
        params[attr.name.slice(16)] = attr.value;
        hasParams = true;
      }
    }
    el.textContent = t(key, hasParams ? params : undefined);
  });
  document.querySelectorAll('[data-i18n-html]').forEach((el) => {
    el.textContent = t(el.getAttribute('data-i18n-html'));
  });
  document.querySelectorAll('[data-i18n-placeholder]').forEach((el) => {
    el.placeholder = t(el.getAttribute('data-i18n-placeholder'));
  });
  document.querySelectorAll('[data-i18n-title]').forEach((el) => {
    el.title = t(el.getAttribute('data-i18n-title'));
  });
  document.querySelectorAll('[data-i18n-aria-label]').forEach((el) => {
    el.setAttribute('aria-label', t(el.getAttribute('data-i18n-aria-label')));
  });
  document.documentElement.lang = currentLang;
}

export async function changeLanguage(lang) {
  const ok = await loadTranslations(lang);
  if (!ok) return;
  await api('/api/settings/language', { method: 'PUT', body: JSON.stringify({ language: lang }) });
  applyStaticTranslations();
  // Immediately update stats-line with cached data so it doesn't flash "loading"
  const statsEl = document.getElementById('stats-line');
  if (statsEl && state.cachedStats) {
    statsEl.textContent = t('stats_line', { total: state.cachedStats.total, types: state.cachedStats.types });
  }
  // Re-fetch flag config so labels match the new language
  const { loadFlagConfig } = await import('./render.js');
  await loadFlagConfig();
  // Rebuild advanced filters panel if open (labels are baked into DOM)
  const panel = document.getElementById('advanced-filters');
  if (panel && panel.classList.contains('open')) {
    const { rebuildAdvancedFilters } = await import('./advanced-filters.js');
    rebuildAdvancedFilters();
  }
  // Reload dynamic content — use lazy imports to avoid circular deps
  if (state.currentView === 'settings') {
    const { loadSettings } = await import('./settings.js');
    await loadSettings();
  } else {
    const { loadData } = await import('./products.js');
    await loadData();
  }
}
