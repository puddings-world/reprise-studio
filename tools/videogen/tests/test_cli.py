import json

from PIL import Image

from videogen import cli
from videogen.state import State


def _seed_candidates(project):
    st = State(project / "work" / "state.json")
    (project / "work" / "keys").mkdir(parents=True)
    for sid in ("S01", "S02", "S03"):
        for k in (1, 2):
            Image.new("RGB", (32, 18)).save(project / "work" / "keys" / f"{sid}_s{k}.png")
            st.add_candidate(sid, f"keys/{sid}_s{k}.png")
    st.save()


def test_feedback_then_status_through_the_cli(project, tmp_path, capsys):
    _seed_candidates(project)
    fb = tmp_path / "fb.txt"
    fb.write_text("videogen-feedback stage=keyframes\npick S01=s2\nredo S03: 只要背影\n", encoding="utf-8")
    cli.main(["--project", str(project), "feedback", "--file", str(fb)])
    out = capsys.readouterr().out
    assert "S01: pick keys/S01_s2.png" in out and "S03: redo keyframes (只要背影)" in out

    cli.main(["--project", str(project), "status"])
    rows = {line.split()[0]: line for line in capsys.readouterr().out.splitlines()[1:]}
    assert "S01_s2.png" in rows["S01"]
    assert rows["S03"].rstrip().endswith("keyframes: 只要背影")


def test_show_config_reflects_host_profile(project, capsys):
    cli.main(["--project", str(project), "--host", "gpu", "show-config"])
    cfg = json.loads(capsys.readouterr().out)
    assert cfg["host"] == "gpu" and cfg["workdir"] == "/remote/work"


def test_review_command_writes_the_page(project, capsys):
    _seed_candidates(project)
    cli.main(["--project", str(project), "review", "keyframes"])
    path = capsys.readouterr().out.strip()
    assert path.endswith("keyframes.html")


def test_attach_without_a_previous_job_explains_itself(project):
    import pytest
    with pytest.raises(SystemExit, match="no job has been sent to host 'gpu'"):
        cli.main(["--project", str(project), "--host", "gpu", "attach"])
