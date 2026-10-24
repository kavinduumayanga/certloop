from app.services.csv_import import csv_safe, normalize_header, parse_participants


def test_bom_quotes_trim_and_duplicate_detection():
    content = '\ufeffName,Email\n" Ada Lovelace ","ADA@example.edu "\nOther,ada@example.edu\n'.encode()
    rows, headers = parse_participants(content)
    assert headers == ["Name", "Email"]
    assert rows[0].name == "Ada Lovelace"
    assert rows[0].normalized_email == "ada@example.edu"
    assert rows[0].is_valid
    assert not rows[1].is_valid
    assert "Duplicate" in rows[1].error


def test_invalid_rows_and_header_mapping():
    rows, _ = parse_participants(b"Full Name,Contact\n,broken\n", "Full Name", "Contact")
    assert not rows[0].is_valid
    assert "Name is required" in rows[0].error


def test_csv_export_prevents_formula_injection():
    assert csv_safe("=HYPERLINK('bad')").startswith("'")
    assert csv_safe(" normal") == " normal"


def test_google_forms_export_is_detected_and_unrelated_timestamp_is_ignored():
    content = (
        "\ufeff Timestamp ,  NAME  ,Email Address (To send the E-Certificate),Workshop choice\n"
        '2026/10/22 10:00:00," Ada Perera ",ADA@example.com,DevOps\n'
    ).encode("utf-8")
    rows, headers = parse_participants(content)
    assert headers[0] == " Timestamp "
    assert len(rows) == 1
    assert rows[0].name == "Ada Perera"
    assert rows[0].normalized_email == "ada@example.com"
    assert rows[0].is_valid


def test_custom_columns_can_be_mapped_case_and_whitespace_insensitively():
    rows, _ = parse_participants(
        b"Attendee Display,Primary Contact,Ignore Me\nGrace Hopper,grace@example.com,x\n",
        " attendee display ",
        "PRIMARY CONTACT",
    )
    assert len(rows) == 1
    assert rows[0].name == "Grace Hopper"
    assert rows[0].email == "grace@example.com"


def test_header_normalization_handles_bom_case_and_spacing():
    assert normalize_header("\ufeff  Email   Address ") == "email address"
