from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

from openpyxl import Workbook

from mail_agent.attachments import parsers
from mail_agent.attachments.parsers import extract_programmatic, sanitize_html
from mail_agent.attachments.validation import detect_content_type, safe_filename
from mail_agent.config import LimitsSettings, load_settings


def test_environment_has_precedence_over_yaml(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    config.write_text("mail:\n  mailbox: Archive\n  batch_size: 2\n", encoding="utf-8")
    settings = load_settings(config, {"MAILBOX": "INBOX", "MAIL_BATCH_SIZE": "7"})
    assert settings.mail.mailbox == "INBOX"
    assert settings.mail.batch_size == 7


def test_shared_dotenv_supplies_writer_key_and_results_api_address(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    config.write_text("results_api:\n  base_url: http://127.0.0.1:8080\n", encoding="utf-8")
    environment_file = tmp_path / ".env"
    environment_file.write_text(
        "WRITER_API_KEY='writer-secret'\nRESULTS_API_BASE_URL=http://127.0.0.1:8080\n"
        "RESULTS_API_HOST=192.168.88.32\nRESULTS_API_PORT=8080\n",
        encoding="utf-8",
    )

    settings = load_settings(config, {"AGENT_ENV_FILE": str(environment_file)})

    assert settings.results_api.api_key == "writer-secret"
    assert settings.results_api.base_url == "http://192.168.88.32:8080"


def test_process_environment_overrides_shared_dotenv(tmp_path: Path) -> None:
    environment_file = tmp_path / ".env"
    environment_file.write_text(
        "WRITER_API_KEY=writer-secret\nRESULTS_API_HOST=192.168.88.32\n",
        encoding="utf-8",
    )

    settings = load_settings(
        tmp_path / "missing.yaml",
        {
            "AGENT_ENV_FILE": str(environment_file),
            "RESULTS_API_KEY": "override-secret",
            "RESULTS_API_BASE_URL": "http://192.168.88.99:8080",
        },
    )

    assert settings.results_api.api_key == "override-secret"
    assert settings.results_api.base_url == "http://192.168.88.99:8080"


def test_sanitize_html_removes_active_and_hidden_content() -> None:
    text = sanitize_html("<style>x</style><script>alert(1)</script><p>visible</p><p style='display:none'>hidden</p>")
    assert text == "visible"


def test_filename_cannot_escape_temporary_directory() -> None:
    name = safe_filename("../../bad\x00name.pdf", "a" * 64)
    assert "/" not in name and ".." not in name and name.endswith(".pdf")


def test_csv_and_json_parsing(tmp_path: Path) -> None:
    csv_file = tmp_path / "a.csv"
    csv_file.write_text("a,b\n1,2\n", encoding="utf-8")
    assert "1\t2" in extract_programmatic(csv_file, ".csv", LimitsSettings()).text
    json_file = tmp_path / "a.json"
    json_file.write_text('{"key": "значение"}', encoding="utf-8")
    assert "значение" in extract_programmatic(json_file, ".json", LimitsSettings()).text


def test_xlsx_is_extracted_as_a_structured_table_without_running_formulas(tmp_path: Path) -> None:
    path = tmp_path / "proposal.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "ТКП"
    sheet.append(["Коммерческое предложение № 613"])
    sheet.append([])
    sheet.append(["Номенклатура", "Количество", "Цена"])
    sheet.append(["Деталь А", 2, 1_500])
    sheet.append(["Итого", None, "=SUM(C4:C4)"])
    workbook.save(path)

    parsed = extract_programmatic(path, ".xlsx", LimitsSettings())

    assert "[Таблица: XLSX" in parsed.text
    assert '[Лист: "ТКП"' in parsed.text
    assert "[Заголовки: Номенклатура | Количество | Цена]" in parsed.text
    assert "строка 4: Номенклатура=Деталь А; Количество=2; Цена=1500" in parsed.text
    assert "Итог, строка 5" in parsed.text
    assert "формула без сохранённого результата: =SUM(C4:C4)" in parsed.text
    assert parsed.usable


def test_legacy_xls_uses_its_actual_mime_type() -> None:
    assert detect_content_type(b"\xd0\xcf\x11\xe0", "application/octet-stream", ".xls") == "application/vnd.ms-excel"


def test_legacy_doc_uses_its_actual_mime_type() -> None:
    assert detect_content_type(b"\xd0\xcf\x11\xe0", "application/octet-stream", ".doc") == "application/msword"


def test_doc_uses_local_converter_without_opening_office(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "request.doc"
    path.write_bytes(b"legacy-doc")
    monkeypatch.setattr(parsers, "_doc_converters", lambda: [("/usr/bin/textutil", ["-convert", "txt", "-stdout"])])

    class Result:
        returncode = 0
        stdout = "Запрос ТКП\nСрок: до пятницы".encode()
        stderr = b""

    def run(command: list[str], **kwargs: object) -> Result:
        assert command == ["/usr/bin/textutil", "-convert", "txt", "-stdout", str(path)]
        assert kwargs["timeout"] == 30
        return Result()

    monkeypatch.setattr(parsers.subprocess, "run", run)

    parsed = extract_programmatic(path, ".doc", LimitsSettings())

    assert parsed.usable
    assert parsed.text == "Запрос ТКП\nСрок: до пятницы"


def test_doc_without_working_converter_requires_manual_review(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "broken.doc"
    path.write_bytes(b"legacy-doc")
    monkeypatch.setattr(parsers, "_doc_converters", lambda: [])

    parsed = extract_programmatic(path, ".doc", LimitsSettings())

    assert not parsed.usable
    assert any("требуется ручная проверка" in warning for warning in parsed.warnings)


def test_xlsx_with_unreadable_characters_requires_manual_review(tmp_path: Path) -> None:
    path = tmp_path / "broken.xlsx"
    workbook = Workbook()
    workbook.active.append(["���"])
    workbook.save(path)

    parsed = extract_programmatic(path, ".xlsx", LimitsSettings())

    assert not parsed.usable
    assert any("требуется ручная проверка" in warning for warning in parsed.warnings)


def test_xls_is_extracted_as_a_structured_table(tmp_path: Path, monkeypatch) -> None:
    class Cell:
        ctype = 1

        def __init__(self, value: object) -> None:
            self.value = value

    class Sheet:
        name = "Прайс"
        values = [["Наименование", "Цена"], ["Деталь А", 1_500], ["Итого", 1_500]]
        nrows = len(values)
        ncols = len(values[0])

        def cell(self, row: int, column: int) -> Cell:
            return Cell(self.values[row][column])

    class Book:
        datemode = 0
        nsheets = 1

        def sheets(self) -> list[Sheet]:
            return [Sheet()]

        def release_resources(self) -> None:
            return None

    fake_xlrd = SimpleNamespace(
        XL_CELL_DATE=3,
        open_workbook=lambda path, on_demand: Book(),
        xldate_as_datetime=lambda value, datemode: value,
    )
    monkeypatch.setitem(sys.modules, "xlrd", fake_xlrd)
    path = tmp_path / "price.xls"
    path.write_bytes(b"legacy-xls")

    parsed = extract_programmatic(path, ".xls", LimitsSettings())

    assert "[Таблица: XLS" in parsed.text
    assert '[Лист: "Прайс"' in parsed.text
    assert "[Заголовки: Наименование | Цена]" in parsed.text
    assert "Итог, строка 3: Наименование=Итого; Цена=1500" in parsed.text
