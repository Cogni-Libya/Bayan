"""Pull the fonts and cover page out of the SIC Final Report template.

The template embeds SamsungOne and Samsung Sharp Sans (obfuscated, as Word
does for every embedded font) and draws its cover from header artwork. This
recovers both so the LaTeX report can use the template's own typeface and
cover instead of imitations:

    fonts/*.ttf           gitignored -- Samsung's fonts are not ours to publish
    assets/sic_cover.pdf  page 1 of the template, rendered by LibreOffice

    python extract_template_assets.py "path/to/SIC_AI_Capstone Project_Final Report.docx"

The build still works without fonts/: bayan.sty falls back to Liberation Sans.
"""
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from lxml import etree

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
HERE = Path(__file__).resolve().parent

# Embedded name in the template -> file name bayan.sty looks for.
WANTED = {
    ("SamsungOne-400", "Regular"): "SamsungOne-400.ttf",
    ("SamsungOne-700", "Regular"): "SamsungOne-700.ttf",
    ("Samsung Sharp Sans", "Regular"): "SamsungSharpSans-Bold.ttf",
}


def deobfuscate(data: bytes, font_key: str) -> bytes:
    """ECMA-376 font obfuscation: the first 32 bytes are XORed with the GUID."""
    key = bytes.fromhex(font_key.strip("{}").replace("-", ""))[::-1]
    head = bytes(b ^ key[i % 16] for i, b in enumerate(data[:32]))
    return head + data[32:]


def extract_fonts(docx: zipfile.ZipFile, out: Path) -> None:
    table = etree.fromstring(docx.read("word/fontTable.xml"))
    rels = etree.fromstring(docx.read("word/_rels/fontTable.xml.rels"))
    target = {r.get("Id"): r.get("Target") for r in rels}
    out.mkdir(exist_ok=True)
    for font in table:
        name = font.get(W + "name")
        for embed in font:
            style = etree.QName(embed).localname.removeprefix("embed")
            if (name, style) not in WANTED:
                continue
            raw = docx.read("word/" + target[embed.get(R + "id")])
            path = out / WANTED[(name, style)]
            path.write_bytes(deobfuscate(raw, embed.get(W + "fontKey")))
            print("font ", path.relative_to(HERE))


def render_cover(template: Path, out: Path) -> None:
    out.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "template.docx"
        shutil.copy(template, src)
        # A private profile, so a LibreOffice window already open cannot block it.
        subprocess.run(["soffice", f"-env:UserInstallation=file://{tmp}/lo",
                        "--headless", "--convert-to", "pdf", "--outdir", tmp,
                        str(src)], check=True,
                       stdout=subprocess.DEVNULL)
        subprocess.run(["pdfseparate", "-f", "1", "-l", "1",
                        str(Path(tmp) / "template.pdf"), str(out / "sic_cover.pdf")],
                       check=True)
    print("cover", (out / "sic_cover.pdf").relative_to(HERE))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    template = Path(sys.argv[1])
    with zipfile.ZipFile(template) as docx:
        extract_fonts(docx, HERE / "fonts")
    render_cover(template, HERE / "assets")
