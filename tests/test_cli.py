"""Lesson 3.5: the CLI's --json contract."""
import json

from app import triage
from tests.fakes import FakeAnthropic, triage_json


def test_json_output_is_one_parseable_line(capsys):
    code = triage.main(["charged twice", "--json", "--prompt-version", "v2", "--mode", "native"],
                       client=FakeAnthropic(triage_json()))
    out, err = capsys.readouterr()
    assert code == 0
    lines = out.strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["status"] == "ok"
    assert record["result"]["category"] == "billing"
    assert record["meta"]["prompt_version"] == "v2" and record["meta"]["schema"] == "triage.v2"
    assert "Total:" in err  # human text goes to stderr


def test_batch_continues_after_schema_failure(tmp_path, capsys):
    tickets = tmp_path / "t.json"
    tickets.write_text(json.dumps([{"id": "A", "text": "one"}, {"id": "B", "text": "two"}]))
    out_file = tmp_path / "results.jsonl"
    client = FakeAnthropic('{"nope": 1}', '{"nope": 1}', triage_json())
    code = triage.main(["--file", str(tickets), "--json", "--out", str(out_file),
                        "--prompt-version", "v2"], client=client)
    records = [json.loads(line) for line in out_file.read_text().splitlines()]
    assert [r["status"] for r in records] == ["schema_failure", "ok"]
    assert code == 3


def test_empty_ticket_exits_1_without_calling(capsys):
    client = FakeAnthropic()
    assert triage.main(["", "--json"], client=client) == 1
    assert client.calls == []


def test_unknown_prompt_version_exits_1(capsys):
    assert triage.main(["hi", "--prompt-version", "v99"], client=FakeAnthropic()) == 1
