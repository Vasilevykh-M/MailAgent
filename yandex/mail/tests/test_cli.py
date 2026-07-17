from pathlib import Path

from yandex_mail.cli import main


def test_help_and_safe_diagnose(capsys, tmp_path: Path) -> None:
    assert main(["--env", str(tmp_path / "missing.env"), "diagnose"]) == 0
    assert "Client Secret configured" in capsys.readouterr().out


def test_conflicting_shortcuts_are_rejected() -> None:
    # argparse detects mutually exclusive status shortcut flags before service creation.
    try:
        main(["list", "--read", "--unread"])
    except SystemExit as error:
        assert error.code != 0
    else:
        raise AssertionError("expected argparse to reject conflicting flags")
