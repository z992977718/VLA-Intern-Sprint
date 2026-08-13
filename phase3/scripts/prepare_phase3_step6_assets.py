#!/usr/bin/env python3
"""Convert existing LIBERO OBJ assets to USD with Isaac Sim's bundled converter."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path

os.environ.setdefault("OMNI_KIT_ACCEPT_EULA", "YES")

from isaacsim import SimulationApp


PROJECT = Path("/root/autodl-tmp/VLA-Intern-Sprint")
RESULT = PROJECT / "results/phase3_step6"
ASSET_ROOT = Path("/root/.cache/libero/assets")
SOURCES = {
    "alphabet_soup": ASSET_ROOT / "stable_hope_objects/alphabet_soup/textured.obj",
    "tomato_sauce": ASSET_ROOT / "stable_hope_objects/tomato_sauce/textured.obj",
    "basket": ASSET_ROOT / "stable_scanned_objects/basket/basket.obj",
    "living_room_table": ASSET_ROOT / "scenes/living_room_table/living_room_table.obj",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


async def convert_all() -> dict:
    import omni.kit.asset_converter
    from pxr import Usd

    output_dir = RESULT / "assets_usd"
    output_dir.mkdir(parents=True, exist_ok=True)
    context = omni.kit.asset_converter.AssetConverterContext()
    context.ignore_materials = False
    context.ignore_animation = True
    context.ignore_cameras = True
    context.single_mesh = True
    context.smooth_normals = True
    context.preview_surface = True
    context.use_meter_as_world_unit = True
    context.create_world_as_default_root_prim = False
    converter = omni.kit.asset_converter.get_instance()
    records = {}
    for name, source in SOURCES.items():
        if not source.is_file():
            raise FileNotFoundError(source)
        destination = output_dir / f"{name}.usd"
        if not destination.is_file():
            task = converter.create_converter_task(str(source), str(destination), None, context)
            success = await task.wait_until_finished()
            if not success:
                raise RuntimeError(f"{name}: {task.get_status()} {task.get_error_message()}")
        usd_stage = Usd.Stage.Open(str(destination))
        if usd_stage is None:
            raise RuntimeError(f"Could not open converted USD: {destination}")
        prims = [str(prim.GetPath()) for prim in usd_stage.Traverse()]
        records[name] = {
            "source": str(source.resolve()),
            "source_sha256": sha256(source),
            "usd": str(destination.resolve()),
            "usd_sha256": sha256(destination),
            "usd_size_bytes": destination.stat().st_size,
            "prims": prims,
            "conversion": "Isaac Sim 6.0.1 omni.kit.asset_converter; materials retained",
        }
    return records


def main() -> int:
    if (RESULT / "asset_conversion.json").exists():
        raise FileExistsError("Refusing to overwrite asset_conversion.json")
    app = SimulationApp({"headless": True})
    try:
        records = asyncio.get_event_loop().run_until_complete(convert_all())
        (RESULT / "asset_conversion.json").write_text(
            json.dumps(records, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps(records, indent=2))
    finally:
        app.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
