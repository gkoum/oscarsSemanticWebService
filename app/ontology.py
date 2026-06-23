from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from owlready2 import PREDEFINED_ONTOLOGIES, World
from rdflib import Graph


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ESRFET_ONTOLOGY_PATH = PROJECT_ROOT / "ontologies" / "ESRFET.owl"
ESRFET_PURL_PREFIX = "http://purl.org/pan-science/ESRFET#"
PANET_PURL_PREFIX = "http://purl.org/pan-science/PaNET/"
PANET_IMPORT_IRI = "http://purl.org/pan-science/PaNET/PaNET.owl"


def normalize_panet_term(term: str) -> str:
    cleaned = term.strip()
    if cleaned.startswith("http://") or cleaned.startswith("https://"):
        return cleaned
    if cleaned.startswith("PaNET:"):
        cleaned = cleaned.split(":", 1)[1]
    return PANET_PURL_PREFIX + cleaned.lstrip("#/")


def compact_iri(iri: str) -> str:
    if iri.startswith(ESRFET_PURL_PREFIX):
        return "ESRFET:" + iri.removeprefix(ESRFET_PURL_PREFIX)
    if iri.startswith(PANET_PURL_PREFIX):
        return "PaNET:" + iri.removeprefix(PANET_PURL_PREFIX)
    return iri


def label_from_iri(iri: str) -> str:
    fragment = iri.rsplit("#", 1)[-1].rsplit("/", 1)[-1]
    return fragment.replace("_", " ")


def _register_panet_import_placeholder() -> None:
    if PANET_IMPORT_IRI in PREDEFINED_ONTOLOGIES:
        return

    placeholder = NamedTemporaryFile("w", suffix=".owl", delete=False)
    placeholder.write(
        """<?xml version="1.0"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
         xmlns:owl="http://www.w3.org/2002/07/owl#">
  <owl:Ontology rdf:about="http://purl.org/pan-science/PaNET/PaNET.owl"/>
</rdf:RDF>
"""
    )
    placeholder.close()
    PREDEFINED_ONTOLOGIES[PANET_IMPORT_IRI] = placeholder.name


@lru_cache(maxsize=1)
def load_esrfet_graph() -> Graph:
    _register_panet_import_placeholder()
    world = World()
    ontology = world.get_ontology(ESRFET_ONTOLOGY_PATH.resolve().as_uri()).load()
    ontology.loaded = True
    return world.as_rdflib_graph()


def query_panet_to_esrfet(term: str) -> list[dict[str, Any]]:
    panet_iri = normalize_panet_term(term)
    query = f"""
PREFIX owl: <http://www.w3.org/2002/07/owl#>

SELECT DISTINCT ?esrfet WHERE {{
  {{
    <{panet_iri}> owl:equivalentClass ?esrfet .
  }}
  UNION
  {{
    ?esrfet owl:equivalentClass <{panet_iri}> .
  }}
  FILTER(STRSTARTS(STR(?esrfet), "{ESRFET_PURL_PREFIX}"))
}}
ORDER BY ?esrfet
"""
    graph = load_esrfet_graph()
    return [
        {
            "sourceTerm": panet_iri,
            "sourceCompact": compact_iri(panet_iri),
            "targetTerm": str(row.esrfet),
            "targetCompact": compact_iri(str(row.esrfet)),
            "targetLabel": label_from_iri(str(row.esrfet)),
            "relation": "owl:equivalentClass",
        }
        for row in graph.query(query)
    ]
