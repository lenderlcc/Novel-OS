import json
import shutil


def edit_manifest(path, **changes):
    data = json.loads(path.read_text()) | changes
    path.write_text(json.dumps(data))
    return data


def add_role_v2(root, *, status="EXPERIMENTAL"):
    original = root / "agents/simulation-role/v1"
    destination = original.with_name("v2")
    shutil.copytree(original, destination)
    edit_manifest(destination / "manifest.json", version=2, status=status)
    return destination / "manifest.json"
