from __future__ import annotations

from ..core.config import TEMPLATE_DIR
from ..core.utils import escape


def render_template(name: str, **context: object) -> str:
    template = (TEMPLATE_DIR / name).read_text(encoding="utf-8")
    values = {key: escape(value) for key, value in context.items()}
    if "body" in context:
        values["body"] = str(context["body"])
    return template.format(**values)
