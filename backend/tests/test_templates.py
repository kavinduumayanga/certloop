from app.services.templates import render_template


def test_known_placeholders_expand_and_unknown_remains():
    result = render_template("Hello {name} — {{workshop_name}} {unknown} {{unsafe}}", {"name":"Nimal","workshop_name":"DevOps Day"})
    assert result == "Hello Nimal — DevOps Day {unknown} {{unsafe}}"

