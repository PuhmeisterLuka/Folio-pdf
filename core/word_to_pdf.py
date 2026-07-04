from __future__ import annotations

import platform
import shutil
import subprocess
import tempfile
from pathlib import Path


def word_to_pdf(
    input_path: str,
    output_path: str,
    progress_callback=None,
) -> tuple[bool, str | None]:
    """Convert a .docx to PDF through Word. Returns (success, error message)."""
    try:
        from docx2pdf import convert  # type: ignore
    except ImportError:
        return False, "docx2pdf is not installed. Run: pip install docx2pdf"

    src = Path(input_path).resolve()
    if not src.exists():
        return False, f"File not found: {src}"
    if src.suffix.lower() != ".docx":
        return False, f"Expected a .docx file, got: {src.suffix}"
    if not src.is_file():
        return False, f"Not a file: {src}"

    dest = Path(output_path).resolve()

    if progress_callback:
        progress_callback(0.05)

    if platform.system() == "Darwin":
        perm_err = _check_word_automation_permission()
        if perm_err:
            return False, perm_err

        # Files downloaded from the internet carry com.apple.quarantine, which
        # makes Word open them in Protected View with an "Enable Editing" dialog
        # that blocks automation. Convert from a temp copy with the flag stripped.
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_src = Path(tmpdir) / src.name
            shutil.copy2(str(src), str(tmp_src))
            subprocess.run(
                ["xattr", "-d", "com.apple.quarantine", str(tmp_src)],
                capture_output=True,
            )
            err = _convert(convert, tmp_src, dest)
    else:
        err = _convert(convert, src, dest)

    if err:
        return False, err

    if not dest.exists():
        return False, (
            "Conversion finished but no PDF was created.\n"
            "Make sure Folio PDF has permission to control Microsoft Word:\n"
            "System Settings → Privacy & Security → Automation"
        )

    if progress_callback:
        progress_callback(1.0)

    return True, None


def _convert(convert, src: Path, dest: Path) -> str | None:
    # docx2pdf calls sys.exit on some Word errors instead of raising,
    # so SystemExit has to be caught too
    try:
        convert(str(src), str(dest))
    except SystemExit:
        return (
            "Conversion failed, Microsoft Word reported an error.\n"
            "Make sure the file isn't open in Word and try again."
        )
    except Exception as exc:
        msg = str(exc)
        if "Microsoft Word" in msg or "word" in msg.lower():
            return (
                "Microsoft Word must be installed to convert .docx files.\n"
                "Install Word from the Mac App Store, then try again."
            )
        return msg
    return None


def is_word_available() -> bool:
    system = platform.system()
    try:
        if system == "Darwin":
            # Spotlight lookup, doesn't need automation permission
            result = subprocess.run(
                ["mdfind", "kMDItemCFBundleIdentifier == 'com.microsoft.Word'"],
                capture_output=True, text=True, timeout=5,
            )
            return bool(result.stdout.strip())
        elif system == "Windows":
            result = subprocess.run(
                ["reg", "query",
                 r"HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\WINWORD.EXE"],
                capture_output=True, timeout=5,
            )
            return result.returncode == 0
        else:
            result = subprocess.run(
                ["which", "soffice"], capture_output=True, timeout=5,
            )
            return result.returncode == 0
    except Exception:
        return False


def _check_word_automation_permission() -> str | None:
    # returns an error message if macOS hasn't granted automation permission yet
    try:
        result = subprocess.run(
            ["osascript", "-e", 'tell application "Microsoft Word" to get version'],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            stderr = result.stderr.lower()
            if "not authorized" in stderr or "not allowed" in stderr or "1743" in stderr:
                return (
                    "Folio PDF needs permission to control Microsoft Word.\n"
                    "Go to System Settings → Privacy & Security → Automation\n"
                    "and enable Folio PDF → Microsoft Word."
                )
    except Exception:
        pass
    return None
