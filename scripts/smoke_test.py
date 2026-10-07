"""End-to-end smoke test exercising all endpoints without a running server.

Calls the service layer and endpoint functions directly so no HTTP client
dependency is required. Run: python scripts/smoke_test.py
"""
from __future__ import annotations

import asyncio
import io
import json

from starlette.datastructures import Headers
from fastapi import UploadFile

from app.api import (
    get_file_features,
    get_file_info,
    get_file_measurements,
    upload_file,
)


def _upload_file_obj(path: str, filename: str) -> UploadFile:
    with open(path, "rb") as fh:
        data = fh.read()
    headers = Headers({"content-type": "application/octet-stream"})
    return UploadFile(file=io.BytesIO(data), filename=filename, headers=headers)


async def run_case(path: str, filename: str) -> None:
    print(f"\n=== {filename} ===")
    up = await upload_file(file=_upload_file_obj(path, filename))
    print("upload:", json.dumps(up.model_dump(), default=str))
    assert up.status == "COMPLETED", f"expected COMPLETED, got {up.status}: {up.error}"

    info = await get_file_info(up.id)
    print("info:", json.dumps(info.model_dump(), default=str))

    feats = await get_file_features(up.id)
    print(f"features: {len(feats)} ->", json.dumps([f.model_dump() for f in feats], default=str)[:400])

    meas = await get_file_measurements(up.id)
    print("measurements:", json.dumps(meas.model_dump(), default=str))

    # CRS must be projected (metric), not the geographic source CRS.
    assert meas.measurement_crs and "4326" not in meas.measurement_crs, (
        f"measurement_crs should be projected, got {meas.measurement_crs}"
    )
    print("OK")


async def main() -> None:
    await run_case("samples/sample.kml", "sample.kml")
    await run_case("samples/sample_shp.zip", "sample_shp.zip")

    # Error handling: unsupported extension and missing id.
    try:
        await upload_file(file=_upload_file_obj("samples/sample.kml", "bad.txt"))
        raise SystemExit("expected HTTPException for .txt")
    except Exception as exc:  # noqa: BLE001
        print("\nunsupported-type rejected as expected:", type(exc).__name__)

    try:
        await get_file_info("doesnotexist")
        raise SystemExit("expected 404 for missing id")
    except Exception as exc:  # noqa: BLE001
        print("missing-id rejected as expected:", type(exc).__name__)

    print("\nALL CHECKS PASSED")


if __name__ == "__main__":
    asyncio.run(main())
