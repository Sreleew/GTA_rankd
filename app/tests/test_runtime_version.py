from pathlib import Path

from fastapi.testclient import TestClient

from studio.config import load_config
from studio.web.app import create_app


def test_health_reads_version_file_even_when_user_config_is_older(tmp_path: Path) -> None:
    source_root = Path(__file__).resolve().parents[1]
    config_text = (source_root / "config.yaml").read_text(encoding="utf-8")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(config_text.replace("database: data/clip_bank.sqlite", f"database: {tmp_path.as_posix()}/clip_bank.sqlite")
                                  .replace("inbox_shorts: inbox/shorts", f"inbox_shorts: {tmp_path.as_posix()}/inbox")
                                  .replace("output_shorts: out/shorts", f"output_shorts: {tmp_path.as_posix()}/out/shorts")
                                  .replace("output_bestof: out/bestof", f"output_bestof: {tmp_path.as_posix()}/out/bestof")
                                  .replace("logs: logs", f"logs: {tmp_path.as_posix()}/logs")
                                  .replace("temp: work/tmp", f"temp: {tmp_path.as_posix()}/tmp")
                                  .replace("fonts: assets/fonts", f"fonts: {tmp_path.as_posix()}/fonts")
                                  .replace("prompts: prompts", f"prompts: {tmp_path.as_posix()}/prompts")
                                  .replace("models: models/whisper", f"models: {tmp_path.as_posix()}/models")
                                  .replace("tools: tools", f"tools: {tmp_path.as_posix()}/tools"), encoding="utf-8")
    (tmp_path / "VERSION.txt").write_text("GTA Ranked Studio\nVersion: 0.2.6\n", encoding="utf-8")
    config = load_config(config_path)
    client = TestClient(create_app(config))
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["app_version"] == "0.2.6"
