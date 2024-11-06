
import json
import importlib
import re
import sys
from pathlib import Path

import bibtexparser  # >=2.0.0b7
import pikepdf
import pymupdf
import requests
from loguru import logger
from thefuzz import fuzz, process


logger.remove()
logger.add(sys.stdout,
           level="INFO",
           format=("<level>{level}</level>: <level>{message}</level>"))
logger.enable(__name__)


def extract_metadata_from_pdf(filename):

    def parse_pdf_metadata_key(key):
        if m := re.match(r"^\{.*\}(.*)$", key):
            return m.groups()[0]
        return key

    with pikepdf.Pdf.open(filename) as pdf:
        pdf_meta = pdf.open_metadata()
        items = {parse_pdf_metadata_key(key): value
                 for key, value in list(pdf_meta.items())}

    return items


def search_doi_in_pdf(filename):
    with pymupdf.open(filename) as doc:
        first_page = doc[0]
        content = first_page.get_text("dict")
        for block in content["blocks"]:
            if "lines" not in block:
                continue
            for line in block.get("lines"):
                for span in line.get("spans"):
                    text = span.get("text")
                    if (m := re.search("http[s]*://.*doi\.org/(.*)", text)):
                        return m.groups()[0].strip()
                    if (m := re.search("DOI[:]*(.*)", text, re.IGNORECASE)):
                        return m.groups()[0].strip()
    return None


def extract_doi_from_pdf(filename):
    metadata = extract_metadata_from_pdf(filename)
    doi = metadata.get("doi", metadata.get("DOI", None))
    if doi is None:
        doi = search_doi_in_pdf(filename)
    return doi


def fetch_metadata_from_doi(doi, format="bibtex"):
    assert format in ("bibtex", "xml")

    DOI_ORG_BIBTEX = {
        "url": "http://dx.doi.org/{doi}",
        "headers": {"accept": "application/x-bibtex"}
    }

    CROSSREF_ORG_BIBTEX = {
        "url": "http://api.crossref.org/works/{doi}/transform/application/x-bibtex",
        "headers": {"accept": "application/x-bibtex"}
    }

    CROSSREF_ORG_XML = {
        "url": "http://api.crossref.org/works/{doi}/transform/application/vnd.crossref.unixsd+xml",
        "headers": {"accept": "application/vnd.crossref.unixsd+xml"}
    }

    endpoints = {
        "bibtex": (DOI_ORG_BIBTEX, CROSSREF_ORG_BIBTEX),
        "xml": (CROSSREF_ORG_XML,)
    }.get(format)

    for endpoint in endpoints:
        url = endpoint.get("url").format(doi=doi)
        headers = endpoint.get("headers")
        req = requests.get(url, headers=headers)
        metadata = req.text

        if format == "bibtex":
            if bibtexparser.parse_string(metadata).entries:
                return metadata

        if format == "xml":
            return metadata

    return None


def append_bibtex(doi, filename):
    pass


def abbreviate_journal(long_name, scorer=None):
    db_abbrev = importlib.resources.files("journaltk.abbrev")
    with db_abbrev.joinpath("journals.json").open(mode="r") as f:
        journals = json.load(f)
    with db_abbrev.joinpath("custom_journals.json").open(mode="r") as f:
        journals.update(json.load(f))

    name_match, score = process.extractOne(
        long_name, list(journals),
        scorer=getattr(fuzz, scorer or "token_sort_ratio")
        # scorer=fuzz.ratio
        # scorer=fuzz.partial_ratio
        # scorer=fuzz.token_set_ratio
        # scorer=fuzz.token_sort_ratio
        # scorer=fuzz.partial_token_sort_ratio
    )
    return journals[name_match]
