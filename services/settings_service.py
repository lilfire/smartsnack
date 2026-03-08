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


def get_off_credentials():
    conn = get_db()
    user_row = conn.execute("SELECT value FROM user_settings WHERE key='off_user_id'").fetchone()
    pass_row = conn.execute("SELECT value FROM user_settings WHERE key='off_password'").fetchone()
    return {
        "off_user_id": user_row["value"] if user_row else "",
        "off_password": pass_row["value"] if pass_row else "",
    }


def set_off_credentials(user_id, password):
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO user_settings (key, value) VALUES ('off_user_id', ?)", (user_id.strip(),))
    conn.execute("INSERT OR REPLACE INTO user_settings (key, value) VALUES ('off_password', ?)", (password,))
    conn.commit()
