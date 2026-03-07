from db import get_db


def get_image(pid):
    conn = get_db()
    row = conn.execute("SELECT image FROM products WHERE id = ?", (pid,)).fetchone()
    if not row or not row["image"]:
        return None
    return row["image"]


def set_image(pid, image):
    if not image or not image.startswith("data:image/"):
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


def delete_image(pid):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE products SET image = '' WHERE id = ?", (pid,))
    if cur.rowcount == 0:
        return False
    conn.commit()
    return True
