/**
 * API mock shape conformance tests.
 *
 * Every canonical mock exported from mock-shapes.js is validated here
 * against its declared shape. Tests fail when a mock diverges from the
 * real API contract — preventing silent drift between test mocks and
 * actual backend responses.
 */
import { describe, it, expect } from 'vitest';
import {
  validateMockShape,
  MOCK_OCR_PROVIDERS,
  MOCK_OCR_SETTINGS,
  MOCK_OCR_SETTINGS_AI,
  MOCK_OCR_SETTINGS_SAVE_OK,
  MOCK_OFF_PRODUCT_FOUND,
  MOCK_OFF_PRODUCT_NOT_FOUND,
  MOCK_OFF_SEARCH_RESULTS,
  MOCK_PRODUCTS_RESPONSE,
  MOCK_WEIGHTS_RESPONSE,
  MOCK_OFF_CREDENTIALS,
  MOCK_OFF_LANGUAGE_PRIORITY,
  MOCK_OFF_LANGUAGES,
  MOCK_BULK_STATUS_IDLE,
  MOCK_BULK_STATUS_RUNNING,
} from './mock-shapes.js';

describe('validateMockShape utility', () => {
  it('passes for a conforming mock', () => {
    expect(() => validateMockShape('GET /api/ocr/settings', MOCK_OCR_SETTINGS)).not.toThrow();
  });

  it('throws for a missing required key', () => {
    expect(() =>
      validateMockShape('GET /api/ocr/settings', { provider: 'tesseract' }),
    ).toThrow('missing required key: "fallback_to_tesseract"');
  });

  it('throws for wrong type', () => {
    expect(() =>
      validateMockShape('GET /api/ocr/settings', {
        provider: 42,
        fallback_to_tesseract: false,
        models: {},
      }),
    ).toThrow('must be of type "string"');
  });

  it('throws for null mock', () => {
    expect(() =>
      validateMockShape('GET /api/ocr/settings', null),
    ).toThrow('must not be null/undefined');
  });

  it('throws for array required at root when object given', () => {
    expect(() =>
      validateMockShape('GET /api/weights', { field: 'kcal' }),
    ).toThrow('must be an array');
  });

  it('throws for unknown endpoint key', () => {
    expect(() =>
      validateMockShape('GET /api/nonexistent', {}),
    ).toThrow('No shape defined for');
  });

  it('passes for root-array shape', () => {
    expect(() =>
      validateMockShape('GET /api/weights', MOCK_WEIGHTS_RESPONSE),
    ).not.toThrow();
  });
});

describe('OCR mock shapes conform to API contract', () => {
  it('MOCK_OCR_PROVIDERS matches GET /api/ocr/providers shape', () => {
    expect(() => validateMockShape('GET /api/ocr/providers', MOCK_OCR_PROVIDERS)).not.toThrow();
  });

  it('MOCK_OCR_PROVIDERS has non-empty providers array', () => {
    expect(MOCK_OCR_PROVIDERS.providers).toBeInstanceOf(Array);
    expect(MOCK_OCR_PROVIDERS.providers.length).toBeGreaterThan(0);
  });

  it('each provider has key, label, and models', () => {
    for (const p of MOCK_OCR_PROVIDERS.providers) {
      expect(p).toHaveProperty('key');
      expect(p).toHaveProperty('label');
      expect(p).toHaveProperty('models');
      expect(p.models).toBeInstanceOf(Array);
    }
  });

  it('MOCK_OCR_SETTINGS matches GET /api/ocr/settings shape', () => {
    expect(() => validateMockShape('GET /api/ocr/settings', MOCK_OCR_SETTINGS)).not.toThrow();
  });

  it('MOCK_OCR_SETTINGS_AI matches GET /api/ocr/settings shape', () => {
    expect(() => validateMockShape('GET /api/ocr/settings', MOCK_OCR_SETTINGS_AI)).not.toThrow();
  });

  it('MOCK_OCR_SETTINGS_SAVE_OK matches POST /api/ocr/settings shape', () => {
    expect(() =>
      validateMockShape('POST /api/ocr/settings', MOCK_OCR_SETTINGS_SAVE_OK),
    ).not.toThrow();
  });
});

describe('OFF product mock shapes conform to API contract', () => {
  it('MOCK_OFF_PRODUCT_FOUND matches GET /api/off/product shape', () => {
    expect(() =>
      validateMockShape('GET /api/off/product', MOCK_OFF_PRODUCT_FOUND),
    ).not.toThrow();
  });

  it('MOCK_OFF_PRODUCT_FOUND has status=1 and product object', () => {
    expect(MOCK_OFF_PRODUCT_FOUND.status).toBe(1);
    expect(MOCK_OFF_PRODUCT_FOUND.product).toBeTypeOf('object');
    expect(MOCK_OFF_PRODUCT_FOUND.product).not.toBeNull();
  });

  it('MOCK_OFF_PRODUCT_FOUND.product has nutriments object', () => {
    const { product } = MOCK_OFF_PRODUCT_FOUND;
    expect(product.nutriments).toBeTypeOf('object');
    expect(product.nutriments['energy-kcal_100g']).toBeTypeOf('number');
    expect(product.nutriments['proteins_100g']).toBeTypeOf('number');
  });

  it('MOCK_OFF_PRODUCT_NOT_FOUND matches GET /api/off/product shape', () => {
    expect(() =>
      validateMockShape('GET /api/off/product', MOCK_OFF_PRODUCT_NOT_FOUND),
    ).not.toThrow();
  });

  it('MOCK_OFF_PRODUCT_NOT_FOUND has status=0 and null product', () => {
    expect(MOCK_OFF_PRODUCT_NOT_FOUND.status).toBe(0);
    expect(MOCK_OFF_PRODUCT_NOT_FOUND.product).toBeNull();
  });
});

describe('OFF search mock shapes conform to API contract', () => {
  it('MOCK_OFF_SEARCH_RESULTS matches GET /api/off/search shape', () => {
    expect(() =>
      validateMockShape('GET /api/off/search', MOCK_OFF_SEARCH_RESULTS),
    ).not.toThrow();
  });

  it('each search result has product_name and nutriments', () => {
    for (const p of MOCK_OFF_SEARCH_RESULTS.products) {
      expect(p).toHaveProperty('product_name');
      expect(p).toHaveProperty('nutriments');
      expect(p.nutriments).toBeTypeOf('object');
    }
  });

  it('nutriments have required OFF keys', () => {
    for (const p of MOCK_OFF_SEARCH_RESULTS.products) {
      const n = p.nutriments;
      expect(n).toHaveProperty('energy-kcal_100g');
      expect(n).toHaveProperty('proteins_100g');
    }
  });
});

describe('Products mock shapes conform to API contract', () => {
  it('MOCK_PRODUCTS_RESPONSE matches GET /api/products shape', () => {
    expect(() =>
      validateMockShape('GET /api/products', MOCK_PRODUCTS_RESPONSE),
    ).not.toThrow();
  });

  it('MOCK_PRODUCTS_RESPONSE has non-empty products array and total', () => {
    expect(MOCK_PRODUCTS_RESPONSE.products.length).toBeGreaterThan(0);
    expect(MOCK_PRODUCTS_RESPONSE.total).toBeTypeOf('number');
  });

  it('MOCK_WEIGHTS_RESPONSE matches GET /api/weights shape (root array)', () => {
    expect(() =>
      validateMockShape('GET /api/weights', MOCK_WEIGHTS_RESPONSE),
    ).not.toThrow();
    expect(Array.isArray(MOCK_WEIGHTS_RESPONSE)).toBe(true);
  });
});

describe('OFF credentials + language mock shapes', () => {
  it('MOCK_OFF_CREDENTIALS matches GET /api/off/credentials shape', () => {
    expect(() =>
      validateMockShape('GET /api/off/credentials', MOCK_OFF_CREDENTIALS),
    ).not.toThrow();
  });

  it('MOCK_OFF_LANGUAGE_PRIORITY matches GET /api/off/language-priority shape', () => {
    expect(() =>
      validateMockShape('GET /api/off/language-priority', MOCK_OFF_LANGUAGE_PRIORITY),
    ).not.toThrow();
  });

  it('MOCK_OFF_LANGUAGES matches GET /api/off/languages shape', () => {
    expect(() =>
      validateMockShape('GET /api/off/languages', MOCK_OFF_LANGUAGES),
    ).not.toThrow();
  });
});

describe('Bulk refresh mock shapes', () => {
  it('MOCK_BULK_STATUS_IDLE matches GET /api/bulk/refresh-off/status shape', () => {
    expect(() =>
      validateMockShape('GET /api/bulk/refresh-off/status', MOCK_BULK_STATUS_IDLE),
    ).not.toThrow();
    expect(MOCK_BULK_STATUS_IDLE.running).toBe(false);
  });

  it('MOCK_BULK_STATUS_RUNNING matches GET /api/bulk/refresh-off/status shape', () => {
    expect(() =>
      validateMockShape('GET /api/bulk/refresh-off/status', MOCK_BULK_STATUS_RUNNING),
    ).not.toThrow();
    expect(MOCK_BULK_STATUS_RUNNING.running).toBe(true);
  });
});
