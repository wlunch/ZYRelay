import json

from zyrelay.plugin.cli import main


def test_cli_manifest_and_execute(
    sample_docx, tmp_path, monkeypatch, capsys
) -> None:
    monkeypatch.setenv("ZYRELAY_DATA_ROOT", str(tmp_path / "data"))
    assert main(["manifest"]) == 0
    assert json.loads(capsys.readouterr().out)["version"] == "0.4.0"

    output = tmp_path / "result.json"
    assert (
        main(
            [
                "execute",
                "--file",
                str(sample_docx),
                "--mode",
                "contract",
                "--output-detail",
                "standard",
                "--output",
                str(output),
            ]
        )
        == 0
    )
    assert json.loads(output.read_text(encoding="utf-8"))["status"] == "completed"


def test_cli_validation_exit_code(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("ZYRELAY_DATA_ROOT", str(tmp_path / "data"))
    invalid = tmp_path / "notes.txt"
    invalid.write_text("hello", encoding="utf-8")
    assert main(["validate", "--file", str(invalid)]) == 3
    assert json.loads(capsys.readouterr().out)["valid"] is False
