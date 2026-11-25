"""Attach and check the reviewed Godot notices for P06's embedded Windows export."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
NOTICES = ROOT / "发布维护/godot-4.7.2"
VERSION = "4.7.2"
README = "README_许可说明.txt"
PAYLOAD = ("LICENSE.txt", "COPYRIGHT.json", "THIRD_PARTY_LICENSES.txt", README)
PACKAGE_MANIFEST = "licenses/p06-windows-license-manifest.json"
PYTHON_LICENSE = "sidecar/runtime/LICENSE.txt"
P03_MANIFEST = "sidecar/p03-bundle.json"
EXE = "P06.exe"
PCK_MAGIC = b"GDPC"


class PackageError(ValueError):
    """The release contents could not be verified."""


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def notice_payload(notices: Path = NOTICES) -> tuple[dict, dict[str, bytes]]:
    """Check the canonical source bytes before creating any release files."""
    try:
        metadata_bytes = (notices / "provenance.json").read_bytes()
        metadata = json.loads(metadata_bytes)
        if metadata["godot_version"] != VERSION or set(metadata["files"]) != set(PAYLOAD):
            raise PackageError("许可清单版本或必需文件集合不符")
        release_sha = metadata["accepted_executables"]["release_x86_64"]
        binding = metadata["p06_windows_template"]
        if not all(re.fullmatch(r"[0-9a-f]{64}", value) for value in (release_sha, binding["body_sha256"])):
            raise PackageError("官方模板哈希无效")
        if not 256 <= binding["headers_size"] <= 16384 or binding["template_size"] <= binding["headers_size"]:
            raise PackageError("模板边界无效")
        payload = {}
        for name in PAYLOAD:
            data = (notices / name).read_bytes()
            record = metadata["files"][name]
            if not data or len(data) != record["bytes"] or digest(data) != record["sha256"]:
                raise PackageError(f"许可源文件内容或哈希不符：{name}")
            payload[name] = data
        if len(json.loads(payload["COPYRIGHT.json"])) != metadata["copyright_groups"]:
            raise PackageError("组件版权表不完整")
        payload["provenance.json"] = metadata_bytes
        return metadata, payload
    except (OSError, KeyError, TypeError, UnicodeError, json.JSONDecodeError) as error:
        raise PackageError(f"许可源文件缺失或无效：{error}") from error


def preflight(template: Path) -> dict:
    metadata, _ = notice_payload()
    binding = metadata["p06_windows_template"]
    if not template.is_file() or template.stat().st_size != binding["template_size"]:
        raise PackageError(f"Godot 4.7.2 Windows 发布模板缺失或大小不符：{template}")
    if sha256(template) != metadata["accepted_executables"]["release_x86_64"]:
        raise PackageError("Godot Windows 发布模板与已核实的 4.7.2 官方模板不符")
    return {"godot_version": VERSION, "template_sha256": metadata["accepted_executables"]["release_x86_64"]}


def package_directory(package: Path) -> Path:
    if not package.is_dir() or package.is_symlink() or package.is_junction():
        raise PackageError(f"需要实际的 Windows 发布目录：{package}")
    return package.resolve()


def release_path(package: Path, name: str) -> Path:
    path = package / name
    for parent in (path, *path.parents):
        if parent == package:
            break
        if parent.is_symlink() or parent.is_junction():
            raise PackageError(f"发布目录内的校验目标不能为链接：{parent.relative_to(package)}")
    return path


def required_file(package: Path, name: str) -> Path:
    path = release_path(package, name)
    if not path.is_file():
        raise PackageError(f"发布文件缺失：{name}")
    return path


def pck_section(header: bytes) -> tuple[int, int]:
    if len(header) < 64 or header[:2] != b"MZ":
        raise PackageError("P06.exe 不是有效的 Windows PE 文件")
    start = struct.unpack_from("<I", header, 60)[0]
    if start < 64 or start + 24 > len(header) or header[start:start + 4] != b"PE\0\0":
        raise PackageError("P06.exe 的 PE 头无效")
    machine, count = struct.unpack_from("<HH", header, start + 4)
    optional_size = struct.unpack_from("<H", header, start + 20)[0]
    optional = start + 24
    sections = optional + optional_size
    if (machine != 0x8664 or optional_size < 64 or sections + count * 40 > len(header)
            or struct.unpack_from("<H", header, optional)[0] != 0x20B
            or struct.unpack_from("<I", header, optional + 60)[0] != len(header)):
        raise PackageError("P06.exe 的 Windows x86_64 节表不符")
    matches = []
    for start in range(sections, sections + count * 40, 40):
        if header[start:start + 8].rstrip(b"\0") == b"pck":
            raw_size, offset = struct.unpack_from("<II", header, start + 16)
            matches.append((offset, raw_size))
    if len(matches) != 1:
        raise PackageError("P06.exe 缺少唯一的嵌入 PCK 节")
    return matches[0]


def embedded_pck(exe: Path, binding: dict) -> dict:
    """Godot can change PE headers on export. The template body stays byte-identical."""
    size = exe.stat().st_size
    with exe.open("rb") as stream:
        header = stream.read(binding["headers_size"])
        if len(header) != binding["headers_size"]:
            raise PackageError("P06.exe 的 PE 头被截断")
        offset, raw_size = pck_section(header)
        if offset != binding["template_size"] or raw_size < 32 or offset + raw_size != size:
            raise PackageError("P06.exe 的嵌入 PCK 节边界不符")
        stream.seek(-12, 2)
        pack_size, magic = struct.unpack("<Q4s", stream.read(12))
        if magic != PCK_MAGIC or pack_size + 12 != raw_size:
            raise PackageError("P06.exe 的嵌入 PCK 页脚不符")
        stream.seek(offset)
        version = struct.unpack("<4s4I", stream.read(20))
        if version != (PCK_MAGIC, 4, 4, 7, 2):
            raise PackageError("P06.exe 的嵌入 PCK 格式或 Godot 4.7.2 版本不符")

        body = hashlib.sha256()
        stream.seek(len(header))
        remaining = offset - len(header)
        while remaining:
            block = stream.read(min(1 << 20, remaining))
            if not block:
                raise PackageError("P06.exe 的模板内容被截断")
            remaining -= len(block)
            body.update(block)
        if body.hexdigest() != binding["body_sha256"]:
            raise PackageError("P06.exe 的 Windows 运行时内容与已核实的官方模板不符")
    return {"offset": offset, "bytes": pack_size, "format": 4}


def runtime_fingerprint(package: Path, metadata: dict) -> dict:
    exe = required_file(package, EXE)
    if release_path(package, "P06.pck").exists():
        raise PackageError("P06 Windows 发布版应将 PCK 嵌入 P06.exe")
    python_license = required_file(package, PYTHON_LICENSE)
    p03_manifest = required_file(package, P03_MANIFEST)
    try:
        declared = json.loads(p03_manifest.read_bytes())["files"]["runtime/LICENSE.txt"]
        license_sha = sha256(python_license)
        if python_license.stat().st_size != declared["bytes"] or license_sha != declared["sha256"]:
            raise PackageError(f"Python 运行时许可与旁载清单不符：{PYTHON_LICENSE}")
    except (KeyError, TypeError, UnicodeError, json.JSONDecodeError) as error:
        raise PackageError(f"无法核对 Python 运行时许可：{error}") from error
    return {
        "schema_version": 1,
        "godot_version": VERSION,
        "template_sha256": metadata["accepted_executables"]["release_x86_64"],
        "embedded_pck": embedded_pck(exe, metadata["p06_windows_template"]),
        "runtime_sha256": {EXE: sha256(exe), PYTHON_LICENSE: license_sha, P03_MANIFEST: sha256(p03_manifest)},
    }


def destinations(package: Path, payload: dict[str, bytes]) -> dict[Path, bytes]:
    return {
        release_path(package, name if name == README else f"licenses/godot-{VERSION}/{name}"): data
        for name, data in payload.items()
    }


def check_package(package: Path) -> dict:
    package = package_directory(package)
    metadata, payload = notice_payload()
    for path, data in destinations(package, payload).items():
        if not path.is_file() or path.read_bytes() != data:
            raise PackageError(f"随包许可缺失或内容不符：{path.relative_to(package)}")
    manifest = required_file(package, PACKAGE_MANIFEST)
    expected = runtime_fingerprint(package, metadata)
    try:
        if json.loads(manifest.read_bytes()) != expected:
            raise PackageError("发布文件与随包许可校验清单不符")
    except (UnicodeError, json.JSONDecodeError) as error:
        raise PackageError(f"随包许可校验清单无效：{error}") from error
    return {**expected, "notice_files": len(payload), "passed": True}


def attach_notices(package: Path) -> dict:
    package = package_directory(package)
    metadata, payload = notice_payload()
    before = runtime_fingerprint(package, metadata)
    targets = destinations(package, payload)
    manifest = release_path(package, PACKAGE_MANIFEST)
    targets[manifest] = (json.dumps(before, sort_keys=True, indent=2) + "\n").encode("utf-8")
    # Check every destination before writing. Existing differing files are preserved.
    for path, data in targets.items():
        if path.exists() and (not path.is_file() or path.read_bytes() != data):
            raise PackageError(f"拒绝覆盖已有的不同文件：{path.relative_to(package)}")
    for path, data in targets.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            with path.open("xb") as stream:
                stream.write(data)
    return check_package(package)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="mode", required=True)
    commands.add_parser("preflight").add_argument("--template", type=Path, required=True)
    for mode in ("attach", "check"):
        commands.add_parser(mode).add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.mode == "preflight":
            result = preflight(args.template)
        elif args.mode == "attach":
            result = attach_notices(args.output)
        else:
            result = check_package(args.output)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except (PackageError, OSError) as error:
        print(f"P06 许可校验失败：{error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
