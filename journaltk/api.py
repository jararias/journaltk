
import sys
import pprint
from pathlib import Path

import bibtexparser  # >=2.0.0
import typer
from loguru import logger

from .utils import (
    abbreviate_journal,
    extract_doi_from_pdf,
    extract_metadata_from_pdf,
    fetch_metadata_from_doi,
)


logger.remove()
logger.add(sys.stdout,
           level="INFO",
           format=("<level>{level}</level>: <level>{message}</level>"))

logger.enable(__name__)


app = typer.Typer()


@app.command("bibtex", help="get bibtex from doi")
def __search_bibtex__(
    doi: str = typer.Argument(help="doi number"),
    abbrev_journal: bool = typer.Option(True, "--abbreviate-journal",
                                        help="use abbreviated journal's name")
):

    entries = fetch_metadata_from_doi(doi, "bibtex")
    entry = bibtexparser.parse_string(entries).entries[0]
    patterns= ("  {}={{{}}}\n", "  {}={}\n")
    s_out = f"@{entry.entry_type}" + "{" + f"{entry.key},\n"
    for name, field in entry.fields_dict.items():
        value = (abbreviate_journal(field.value)
                 if abbrev_journal and (name.casefold() == "journal")
                 else field.value)
        pattern = patterns[name.casefold() == "month"]
        s_out += f"{pattern.format(name.lower(), value)},"
    s_out += "}\n"
    print(s_out)
    sys.exit(0)


@app.command("pdf-doi", help="get doi from pdf")
def __extract_doi_from_pdf__(filename: str = typer.Argument(help="filename")):
    doi = extract_doi_from_pdf(filename)
    if not doi:
        if not len(metadata := extract_metadata_from_pdf(filename)):
            logger.error("this file does not have metadata")
            sys.exit(1)
        logger.error("could not find the DOI embedded in the file metadata")
        pprint.pprint(metadata, stream=sys.stderr)
        sys.exit(1)
    print(doi, file=sys.stdout)
    sys.exit(0)


@app.command("pdf-rename", help="rename journal pdf file")
def __rename_pdf__(
    filename: str = typer.Argument(help="filename to be renamed"),
    doi: str = typer.Option(
        None,
        help="doi number of the file. If it is not provided, it is extracted from the input file"),
    custom_format: str = typer.Option(
        "{year}_{authors}_{journal}", "--fmt", help="custom filename format"),
    dry_run: bool = typer.Option(False, help="do not rename the file")
):

    def abbreviate_authors(authors):
        authors_abbrev = ["_".join(author.strip().split(",")[0].strip().lower().split())
                          for author in authors.split("and")]
        if len(authors_abbrev) == 1:
            return authors_abbrev[0]
        if len(authors) == 2:
            return "_".join(authors_abbrev[:2])
        return f"{authors_abbrev[0]}_et_al"

    if not doi:
        if not (doi := extract_doi_from_pdf(filename)):
            logger.error("could not find the DOI embedded in the pdf file")
            sys.exit(1)

    bibtex_metadata = fetch_metadata_from_doi(doi, "bibtex")
    entry_fields = bibtexparser.parse_string(bibtex_metadata).entries[-1].fields_dict
    year = entry_fields.get("year").value
    authors = entry_fields.get("author").value
    journal = entry_fields.get("journal").value
    journal_abbrev = abbreviate_journal(journal)
    new_name = custom_format.format(
        year=year,
        authors=abbreviate_authors(authors),
        journal="_".join(journal_abbrev.lower().replace(".", "").split()))
    new_filename = Path(filename).with_stem(new_name)
    logger.info(f"{filename} -> {new_filename}")
    if not dry_run:
        Path(filename).rename(new_filename)
    sys.exit(0)


if __name__ == "__main__":

    app()
