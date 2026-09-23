from __future__ import annotations

from pathlib import Path

from cv_engine.application.commands import (
    IngestCommand,
)


def test_csv_export_declares_its_schema_version(services, tmp_path: Path) -> None:
    import json as _json

    from cv_engine.application.maintenance import EXPORT_SCHEMA_VERSION
    from cv_engine.infrastructure.exports import export_csv

    ingested = services.applications.ingest(
        IngestCommand(
            company="Acme", target_role="Developer", job_text="Python developer role", client="web"
        )
    )
    app_id = ingested.application_id
    output = export_csv(services.queries.list_applications(), tmp_path / "applications.csv")
    text = output.read_text(encoding="utf-8")
    assert "current_status" in text
    assert app_id in text

    metadata = _json.loads(
        output.with_suffix(output.suffix + ".meta.json").read_text(encoding="utf-8")
    )
    assert metadata["export_schema_version"] == EXPORT_SCHEMA_VERSION
    assert metadata["row_count"] == 1
    assert metadata["columns"][0] == "id"
    assert "current_status" in metadata["columns"]
