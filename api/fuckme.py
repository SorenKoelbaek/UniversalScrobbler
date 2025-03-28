import os
import re
from pathlib import Path
from typing import Set

ROOT_PROTO_DIR = Path("scripts/proto").resolve()  # original messy repo
FLAT_OUT_DIR = Path("scripts/proto_flat").resolve()  # clean proto dump
ENTRY_FILE = ROOT_PROTO_DIR / "mercury.proto"  # start here

IMPORT_RE = re.compile(r'import "(.+?)";')

visited_files: Set[Path] = set()

def resolve_dependencies(proto_path: Path):
    if proto_path in visited_files:
        return
    visited_files.add(proto_path)
    content = proto_path.read_text()
    for match in IMPORT_RE.finditer(content):
        import_path = match.group(1)
        resolved_path = (Path(ROOT_PROTO_DIR)  / import_path).resolve()
        if not resolved_path.exists():
            print(f"⚠️ Missing: {resolved_path} (from {proto_path})")
            continue
        resolve_dependencies(resolved_path)

def flatten_and_fix_imports():
    os.makedirs(FLAT_OUT_DIR, exist_ok=True)

    for file in visited_files:
        content = file.read_text()
        # Just replace imports with flat references
        content = IMPORT_RE.sub(lambda m: f'import "{Path(m.group(1)).name}";', content)
        target_path = FLAT_OUT_DIR / file.name
        target_path.write_text(content)
        print(f"📄 Copied: {file.name}")

def build_protoc_command():
    files_str = " ".join([f.name for f in visited_files])
    print("\n🛠️ Run this command to generate Python files:")
    print(f"protoc --proto_path={FLAT_OUT_DIR} --python_out=scripts/protos {files_str}")

if __name__ == "__main__":
    print(f"🔍 Starting from {ENTRY_FILE.relative_to(ROOT_PROTO_DIR)}")
    resolve_dependencies(ENTRY_FILE)
    print(f"🧩 Resolved {len(visited_files)} dependencies")
    flatten_and_fix_imports()
    build_protoc_command()
