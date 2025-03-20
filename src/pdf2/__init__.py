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

    # Check the number of pages in the PDF
    num_pages = int(
        sp.check_output(
            [
                "gs",
                "-q",
                "-dNODISPLAY",
                "-dNOSAFER",
                "-c",
                f"({filepath.as_posix()}) (r) file runpdfbegin pdfpagecount = quit",
            ]
        )
    )

    # If the output format is PNG, using Ghostscript is sufficient.
    if output_format == OutputFormat.png:
        if num_pages == 1:
            # For single page PDF files, the output file name is the same as the input
            output_filepath = filepath.with_suffix(".png")
        else:
            # For multi-page PDF files, the output file name is the input file name suffixed with a three digit counter
            output_filepath = filepath.parent.joinpath(filepath.stem + "-%03d.png")

        gs_cmd = [
            "gs",
            "-dSAFER",
            "-dBATCH",
            "-dNOPAUSE",
            "-sDEVICE=png16malpha",  # Use a PNG writer with alpha (transparency) channel
            "-r1200",  # Render at a high resolution
            "-dDownScaleFactor=4",  # Downscale the image to get a smoother result
            f"-sOutputFile={output_filepath}",
            f"{filepath}",
        ]

        # Suppress the output of Ghostscript
        gs_ps = sp.Popen(gs_cmd, stdout=sp.DEVNULL)

        gs_ps.wait()

        return

    match output_format:
        case OutputFormat.emf:
            cmd = "open-page:1; file-open:{fn}; export-type:emf; export-dpi:1200; export-do\n"
        case OutputFormat.svg:
            cmd = "open-page:1; file-open:{fn}; export-type:svg; export-plain-svg; export-do\n"

    if num_pages == 1:
        pdf_pages = [filepath]

    else:
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

        gs_ps = sp.Popen(gs_cmd, stdout=sp.DEVNULL)

        gs_ps.wait()

        pdf_pages = list(filepath.parent.glob(filepath.stem + "-[0-9][0-9][0-9].pdf"))

    inkscape_ps = sp.Popen(["inkscape", "--shell"], stdin=sp.PIPE, stdout=sp.DEVNULL)

    if inkscape_ps.stdin is None:
        raise RuntimeError("Failed to open Inkscape shell")

    for pdf in pdf_pages:
        inkscape_ps.stdin.write(cmd.format(fn=pdf).encode("utf-8"))

    inkscape_ps.stdin.write(b"quit\n")
    inkscape_ps.stdin.flush()

    inkscape_ps.wait()

    if not keep_pdf_pages and num_pages > 1:
        for pdf in pdf_pages:
            pdf.unlink()
