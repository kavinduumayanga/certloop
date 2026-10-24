import re


ALLOWED_PLACEHOLDERS = {"name", "workshop_name"}
PLACEHOLDER_RE = re.compile(
    r"{{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*}}|(?<!{){\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*}(?!})"
)


def render_template(template: str, values: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1) or match.group(2)
        if key not in ALLOWED_PLACEHOLDERS:
            return match.group(0)
        return values.get(key, "")
    return PLACEHOLDER_RE.sub(replace, template)

