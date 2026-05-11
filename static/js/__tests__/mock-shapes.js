/**
 * Shared mock shape validation utility for frontend tests.
 *
 * Defines canonical API response shapes and exports realistic mock objects.
 * Test files import from here to keep mocks DRY and prevent drift from
 * real API contracts. Use validateMockShape() in test assertions to fail
 * fast when a mock diverges from the expected contract.
 */

// ── Canonical shapes (key → expected type or 'array') ──────────────────────

export const SHAPES = {
  'GET /api/ocr/providers': {
    providers: 'array',
  },
  'GET /api/ocr/settings': {
    provider: 'string',
    fallback_to_tesseract: 'boolean',
    models: 'object',
  },
  'POST /api/ocr/settings': {
    ok: 'boolean',
  },
  'GET /api/off/search': {
    products: 'array',
  },
  'GET /api/off/product': {
    status: 'number',
  },
  'GET /api/products': {
    products: 'array',
    total: 'number',
  },
  'GET /api/weights': {
    // returns an array directly
    _root: 'array',
  },
  'GET /api/off/credentials': {
    off_user_id: 'string',
    has_password: 'boolean',
  },
  'GET /api/off/language-priority': {
    priority: 'array',
  },
  'GET /api/off/languages': {
    languages: 'array',
  },
  'GET /api/bulk/refresh-off/status': {
    running: 'boolean',
  },
};

// ── Realistic mock objects ─────────────────────────────────────────────────

export const MOCK_OCR_PROVIDERS = {
  providers: [
    { key: 'tesseract', label: 'Tesseract OCR', models: [] },
    { key: 'openai', label: 'OpenAI Vision', models: ['gpt-4o', 'gpt-4o-mini'] },
    { key: 'gemini', label: 'Gemini Vision', models: ['gemini-2.0-flash', 'gemini-1.5-pro'] },
  ],
};

export const MOCK_OCR_SETTINGS = {
  provider: 'tesseract',
  fallback_to_tesseract: false,
  models: {},
};

export const MOCK_OCR_SETTINGS_AI = {
  provider: 'openai',
  fallback_to_tesseract: true,
  models: { openai: 'gpt-4o' },
};

export const MOCK_OCR_SETTINGS_SAVE_OK = {
  ok: true,
};

export const MOCK_OFF_PRODUCT_FOUND = {
  status: 1,
  product: {
    product_name: 'Test Product',
    code: '1234567890123',
    nutriments: {
      'energy-kcal_100g': 150,
      'fat_100g': 5.2,
      'carbohydrates_100g': 20.1,
      'proteins_100g': 10.0,
      'salt_100g': 0.5,
      'fiber_100g': 2.0,
    },
    categories_tags: ['en:dairy', 'en:milks'],
    brands: 'TestBrand',
    image_url: 'https://static.openfoodfacts.org/images/products/123/front.jpg',
  },
};

export const MOCK_OFF_PRODUCT_NOT_FOUND = {
  status: 0,
  product: null,
};

export const MOCK_OFF_SEARCH_RESULTS = {
  products: [
    {
      product_name: 'Chicken Breast',
      code: '5000157024671',
      nutriments: {
        'energy-kcal_100g': 165,
        'fat_100g': 3.6,
        'carbohydrates_100g': 0,
        'proteins_100g': 31.0,
        'salt_100g': 0.17,
      },
      categories_tags: ['en:meats'],
      brands: 'FarmCo',
    },
    {
      product_name: 'Greek Yogurt',
      code: '5000157024680',
      nutriments: {
        'energy-kcal_100g': 97,
        'fat_100g': 0.4,
        'carbohydrates_100g': 6.0,
        'proteins_100g': 10.0,
        'salt_100g': 0.1,
      },
      categories_tags: ['en:dairy', 'en:yogurts'],
    },
  ],
};

export const MOCK_PRODUCTS_RESPONSE = {
  products: [
    { id: 1, name: 'Milk', type: 'dairy', total_score: 80, has_image: 0 },
    { id: 2, name: 'Bread', type: 'bakery', total_score: 65, has_image: 0 },
  ],
  total: 2,
};

export const MOCK_WEIGHTS_RESPONSE = [
  { field: 'kcal', label: 'Kcal', desc: 'Energy', direction: 'lower', weight: 100, enabled: true },
  { field: 'protein', label: 'Protein', desc: 'Protein', direction: 'higher', weight: 100, enabled: true },
];

export const MOCK_OFF_CREDENTIALS = {
  off_user_id: 'testuser',
  has_password: true,
};

export const MOCK_OFF_LANGUAGE_PRIORITY = {
  priority: ['no', 'en'],
};

export const MOCK_OFF_LANGUAGES = {
  languages: ['no', 'en', 'se', 'fi', 'da'],
};

export const MOCK_BULK_STATUS_IDLE = {
  running: false,
};

export const MOCK_BULK_STATUS_RUNNING = {
  running: true,
};

// ── Validation helper ──────────────────────────────────────────────────────

/**
 * Validates that a mock object conforms to the expected shape.
 *
 * @param {string} endpointKey - Key from SHAPES (e.g. 'GET /api/ocr/settings')
 * @param {*} mock - The mock value to validate
 * @throws {Error} if the mock is missing required keys or has wrong types
 */
export function validateMockShape(endpointKey, mock) {
  const shape = SHAPES[endpointKey];
  if (!shape) throw new Error(`No shape defined for: ${endpointKey}`);

  // Root-level array shape
  if (shape._root === 'array') {
    if (!Array.isArray(mock)) {
      throw new Error(`Mock for ${endpointKey} must be an array`);
    }
    return;
  }

  if (mock === null || mock === undefined) {
    throw new Error(`Mock for ${endpointKey} must not be null/undefined`);
  }

  for (const [key, type] of Object.entries(shape)) {
    if (!(key in mock)) {
      throw new Error(`Mock for ${endpointKey} is missing required key: "${key}"`);
    }
    if (type === 'array') {
      if (!Array.isArray(mock[key])) {
        throw new Error(`Mock for ${endpointKey}.${key} must be an array`);
      }
    } else if (typeof mock[key] !== type) {
      throw new Error(
        `Mock for ${endpointKey}.${key} must be of type "${type}", got "${typeof mock[key]}"`,
      );
    }
  }
}
