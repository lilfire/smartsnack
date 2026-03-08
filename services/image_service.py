"""Service for managing product images stored as base64 data URIs."""

from db import get_db

_ALLOWED_IMAGE_PREFIXES = (
    "data:image/jpeg",
    "data:image/png",
    "data:image/webp",
    "data:image/gif",
)


def get_image(pid: int) -> str | None:
    """Get the base64 image for a product, or None if not set."""
    conn = get_db()
    row = conn.execute("SELECT image FROM products WHERE id = ?", (pid,)).fetchone()
    if not row or not row["image"]:
        return None
    return row["image"]


def set_image(pid: int, image: str) -> bool:
    """Set a product image from a base64 data URI."""
    if not image or not image.startswith(_ALLOWED_IMAGE_PREFIXES):
        raise ValueError("Invalid image format")
    max_image_bytes = 2 * 1024 * 1024  # 2 MB base64 string limit
    if len(image) > max_image_bytes:
        raise ValueError("Image too large (max 2 MB)")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE products SET image = ? WHERE id = ?", (image, pid))
    if cur.rowcount == 0:
        return False
    conn.commit()
    return True


def delete_image(pid: int) -> bool:
    """Remove the image for a product."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE products SET image = '' WHERE id = ?", (pid,))
    if cur.rowcount == 0:
        return False
    conn.commit()
    return True
