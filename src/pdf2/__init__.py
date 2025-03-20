import subprocess as sp
from enum import Enum
from pathlib import Path
from typing import Annotated

import typer

app = typer.Typer(add_completion=False)


class OutputFormat(str, Enum):
    emf = "emf"
    svg = "svg"
    png = "png"


@app.command()
def convert(
    output_format: Annotated[
        OutputFormat, typer.Argument(help="The output format to which the PDF will be converted.")
    ],
    filepath: Annotated[Path, typer.Argument(help="The path to the PDF file.")],
    keep_pdf_pages: Annotated[
        bool,
        typer.Option(
            help="Whether to keep the separate PDF pages after converting them (for svg and emf output format)."
        ),
    ] = False,
    text_to_path: Annotated[
        bool, typer.Option(help="Whether to convert text to paths (for svg and emf output format).")
    ] = True,
) -> None:
    filepath = filepath.resolve(strict=True)

    if not filepath.suffix == ".pdf":
        raise ValueError("Input file is not a PDF file")

    if output_format == OutputFormat.png:
        gs_cmd = [
            "gs",
            "-dSAFER",
            "-dBATCH",
            "-dNOPAUSE",
            "-sDEVICE=png16malpha",
            "-r300",
            f"-sOutputFile={filepath.parent.joinpath(filepath.stem + '-%03d.png')}",
            f"{filepath}",
        ]

        sp.run(gs_cmd)

        return

    # NOTE: Maybe use 'gs -q -dNODISPLAY -dNOSAFER -c "(file.pdf) (r) file runpdfbegin pdfpagecount = quit"' to get the
    # number of pages and iterate over pages with inkscape.

    gs_cmd = [
        "gs",
        "-sDEVICE=pdfwrite",
        "-dSAFER",
        "-dBATCH",
        "-dNOPAUSE",
    ]

    if text_to_path:
        gs_cmd += ["-dNoOutputFonts"]

    gs_cmd += [
        "-q",
        f"-sOutputFile={filepath.parent.joinpath(filepath.stem + '-%03d.pdf')}",
        f"{filepath}",
    ]

    sp.run(gs_cmd)

    pdf_pages = list(filepath.parent.glob(filepath.stem + "-[0-9][0-9][0-9].pdf"))

    match output_format:
        case OutputFormat.emf:
            cmd = "open-page:1; file-open:{fn}; export-type:emf; export-dpi:1200; export-do\n"
        case OutputFormat.svg:
            cmd = "open-page:1; file-open:{fn}; export-type:svg; export-plain-svg; export-do\n"

    inkscape_ps = sp.Popen(["inkscape", "--shell"], stdin=sp.PIPE, stdout=sp.DEVNULL)

    if inkscape_ps.stdin is None:
        raise RuntimeError("Failed to open Inkscape shell")

    for pdf in pdf_pages:
        inkscape_ps.stdin.write(cmd.format(fn=pdf).encode("utf-8"))

    inkscape_ps.stdin.write(b"quit\n")
    inkscape_ps.stdin.flush()

    inkscape_ps.wait()

    if not keep_pdf_pages:
        for pdf in pdf_pages:
            pdf.unlink()
