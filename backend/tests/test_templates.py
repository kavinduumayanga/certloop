from app.services.templates import render_template


def test_only_name_placeholder_expands_and_uses_saved_participant_name():
    result = render_template(
        "Hello {name} / {{name}} — {workshop_name} {{workshop_name}} {unknown}",
        {"name": "Saved CSV Name", "workshop_name": "Must not render"},
    )
    assert result == "Hello Saved CSV Name / Saved CSV Name — {workshop_name} {{workshop_name}} {unknown}"

