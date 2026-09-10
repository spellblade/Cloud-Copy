from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Install paths that must copy the unofficial-library pins from requirements.txt.
_PINNED_PATHS = (
    "scripts/install.sh",
    "scripts/install.ps1",
    "README.md",
    "docs/setup.md",
    ".github/workflows/ci.yml",
)


def _requirement_pin(package: str) -> str:
    prefix = f"{package}=="
    for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines():
        if line.startswith(prefix):
            return line.strip()
    raise AssertionError(f"requirements.txt has no {prefix} pin")


def test_install_paths_pin_unofficial_libs():
    pikpak = _requirement_pin("pikpakapi")
    mega = _requirement_pin("mega.py")
    for rel in _PINNED_PATHS:
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert pikpak in text, f"{rel} is missing {pikpak}"
        assert mega in text, f"{rel} is missing {mega}"
