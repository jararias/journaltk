
import re
import sys
import json

import bibtexparser  # >=2.0.0
import pikepdf
import requests
from loguru import logger
from thefuzz import fuzz, process


logger.enable(__name__)
logger.remove(0)
logger.add(sys.stdout,
           level="INFO",
           format=("<level>{level}</level>: <level>{message}</level>"))


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


def extract_doi_from_pdf(filename):
    metadata = extract_metadata_from_pdf(filename)
    return metadata.get("doi", metadata.get("DOI", None))


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
            if (db := bibtexparser.parse_string(metadata)).entries:
                return metadata

        if format == "xml":
            return metadata

    return None


def append_bibtex(doi, filename):
    pass


def abbreviate_journal(long_name, scorer=None):
    with open("journals_abbrev/journals.json", "r") as f:
        journals = json.load(f)
    with open("journals_abbrev/custom_journals.json", "r") as f:
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
