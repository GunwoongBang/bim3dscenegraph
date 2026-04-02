import xml.etree.ElementTree as ET
from xml.dom import minidom


def safe_name(text, fallback) -> str:
    if not text:
        return fallback
    cleaned = "".join(ch if ch.isalnum() or ch in (
        "_", "-") else "_" for ch in text)
    return cleaned[:120] if cleaned else fallback


def write_obj(mesh_path, vertices, faces) -> None:
    """Write a triangle mesh to OBJ format (visual-only use)."""
    lines = []
    for v in vertices:
        lines.append(f"v {v[0]:.9f} {v[1]:.9f} {v[2]:.9f}")

    # OBJ is 1-based indexing.
    for f in faces:
        lines.append(f"f {int(f[0]) + 1} {int(f[1]) + 1} {int(f[2]) + 1}")

    mesh_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def pretty_xml(element) -> str:
    rough = ET.tostring(element, encoding="utf-8")
    parsed = minidom.parseString(rough)
    return parsed.toprettyxml(indent="  ")
