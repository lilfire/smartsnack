from db import get_db
from config import SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE


def get_language():
    conn = get_db()
    row = conn.execute("SELECT value FROM user_settings WHERE key='language'").fetchone()
    return row["value"] if row else DEFAULT_LANGUAGE


def set_language(lang):
    lang = lang.strip().lower()
    if lang not in SUPPORTED_LANGUAGES:
        raise ValueError(f"Unsupported language. Supported: {', '.join(SUPPORTED_LANGUAGES)}")
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO user_settings (key, value) VALUES ('language', ?)", (lang,))
    conn.commit()
    return lang
