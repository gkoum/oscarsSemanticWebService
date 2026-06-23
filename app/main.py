from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Annotated, Any

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel, ConfigDict, Field

from app.icat import ICAT_PUBLIC_DATASETS_URL, fetch_icat_public_datasets
from app.ontology import query_panet_to_esrfet

ESRFET = "https://w3id.org/PaN/ESRFET#"
ESRFET_PURL = "http://purl.org/pan-science/ESRFET#"
PANET = "http://purl.org/pan-science/PaNET/"
OWL_TIME = "http://www.w3.org/2006/time#"
OWL = "http://www.w3.org/2002/07/owl#"
XSD = "http://www.w3.org/2001/XMLSchema#"
DCAT = "http://www.w3.org/ns/dcat#"
DCTERMS = "http://purl.org/dc/terms/"
SCHEMA = "https://schema.org/"


class Dataset(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "x-semantic-type": DCAT + "Dataset",
            "x-jsonld-context": {
                "dcat": DCAT,
                "dcterms": DCTERMS,
                "schema": SCHEMA,
                "esrfet": ESRFET,
                "time": OWL_TIME,
                "id": "@id",
                "name": "dcterms:title",
                "startDate": {
                    "@id": SCHEMA + "startDate",
                    "@type": XSD + "dateTime",
                },
                "endDate": {
                    "@id": SCHEMA + "endDate",
                    "@type": XSD + "dateTime",
                },
                "instrumentName": "schema:instrument",
                "techniquePids": {
                    "@id": "esrfet:usesTechnique",
                    "@type": "@id",
                },
                "sampleName": "schema:sampleType",
            },
        }
    )

    id: int = Field(
        examples=[1001],
        json_schema_extra={"x-semantic-type": DCTERMS + "identifier"},
    )
    name: str = Field(
        examples=["ID21 XAS catalyst oxidation-state dataset"],
        json_schema_extra={"x-semantic-type": DCTERMS + "title"},
    )
    startDate: datetime = Field(
        examples=["2024-03-18T09:15:00Z"],
        json_schema_extra={
            "x-semantic-type": OWL_TIME + "Instant",
            "x-datatype": XSD + "dateTime",
        },
    )
    endDate: datetime = Field(
        examples=["2024-03-18T11:45:00Z"],
        json_schema_extra={
            "x-semantic-type": OWL_TIME + "Instant",
            "x-datatype": XSD + "dateTime",
        },
    )
    instrumentName: str = Field(
        examples=["ID21"],
        json_schema_extra={"x-semantic-type": SCHEMA + "instrument"},
    )
    techniquePids: list[str] = Field(
        examples=[["https://w3id.org/PaN/ESRFET#XAS"]],
        json_schema_extra={
            "x-semantic-type": ESRFET + "experimental_technique",
            "x-value-kind": "iri-list",
            "x-ontology": ESRFET.rstrip("#"),
        },
    )
    sampleName: str = Field(
        examples=["lysozyme microcrystals"],
        json_schema_extra={"x-semantic-type": SCHEMA + "sampleType"},
    )


class MappingResult(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "x-semantic-type": OWL + "Class",
            "x-semantic-relation": OWL + "equivalentClass",
        }
    )

    sourceTerm: str = Field(
        examples=["http://purl.org/pan-science/PaNET/PaNET01196"],
        json_schema_extra={"x-semantic-type": PANET + "PaNETConcept"},
    )
    sourceCompact: str = Field(examples=["PaNET:PaNET01196"])
    targetTerm: str = Field(
        examples=["http://purl.org/pan-science/ESRFET#XAS"],
        json_schema_extra={"x-semantic-type": ESRFET_PURL + "experimental_technique"},
    )
    targetCompact: str = Field(examples=["ESRFET:XAS"])
    targetLabel: str = Field(examples=["XAS"])
    relation: str = Field(
        examples=["owl:equivalentClass"],
        json_schema_extra={"x-semantic-type": OWL + "equivalentClass"},
    )


class MappingResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "x-semantic-type": "https://schema.org/DefinedTermSet",
            "x-source-ontology": PANET.rstrip("/"),
            "x-target-ontology": ESRFET_PURL.rstrip("#"),
        }
    )

    source: str = Field(examples=["PANET"])
    target: str = Field(examples=["ESRFET"])
    term: str = Field(examples=["http://purl.org/pan-science/PaNET/PaNET01196"])
    targetTerm: str | None = Field(
        default=None,
        examples=["http://purl.org/pan-science/ESRFET#XAS"],
        json_schema_extra={"x-semantic-type": ESRFET_PURL + "experimental_technique"},
    )
    mappings: list[MappingResult]


FAKE_DATASETS = [
    Dataset(
        id=1001,
        name="ID21 XAS catalyst oxidation-state dataset",
        startDate=datetime(2024, 3, 18, 9, 15, tzinfo=timezone.utc),
        endDate=datetime(2024, 3, 18, 11, 45, tzinfo=timezone.utc),
        instrumentName="ID21",
        techniquePids=["https://w3id.org/PaN/ESRFET#XAS"],
        sampleName="ceria-supported platinum catalyst",
    ),
    Dataset(
        id=1002,
        name="ID21 energy-dispersive XAS reference scan",
        startDate=datetime(2024, 3, 19, 14, 0, tzinfo=timezone.utc),
        endDate=datetime(2024, 3, 19, 18, 30, tzinfo=timezone.utc),
        instrumentName="ID21",
        techniquePids=[
            "https://w3id.org/PaN/ESRFET#ED-XAS",
            "https://w3id.org/PaN/ESRFET#XAS",
        ],
        sampleName="iron oxide calibration foil",
    ),
    Dataset(
        id=1003,
        name="ID24 dispersive XAS battery electrode dataset",
        startDate=datetime(2024, 5, 2, 8, 30, tzinfo=timezone.utc),
        endDate=datetime(2024, 5, 2, 15, 10, tzinfo=timezone.utc),
        instrumentName="ID24",
        techniquePids=["https://w3id.org/PaN/ESRFET#ED-XAS"],
        sampleName="lithium nickel manganese cobalt oxide electrode",
    ),
    Dataset(
        id=1004,
        name="High-resolution tomography of heritage material",
        startDate=datetime(2024, 9, 12, 7, 45, tzinfo=timezone.utc),
        endDate=datetime(2024, 9, 12, 12, 20, tzinfo=timezone.utc),
        instrumentName="ID19",
        techniquePids=["https://w3id.org/PaN/ESRFET#TOMO"],
        sampleName="painted ceramic fragment",
    ),
]


app = FastAPI(
    title="Semantic Web Service POC",
    version="0.1.0",
    description=(
        "Local demonstrator for an ESRF-style catalogue endpoint enriched "
        "with semantic OpenAPI annotations."
    ),
)


def parse_technique_pids(technique_pids: str | None) -> set[str]:
    if not technique_pids:
        return set()
    return {
        canonical_technique_pid(pid.strip())
        for pid in technique_pids.split(",")
        if pid.strip()
    }


def canonical_technique_pid(technique_pid: str) -> str:
    if technique_pid.startswith(ESRFET_PURL):
        return ESRFET + technique_pid.removeprefix(ESRFET_PURL)
    return technique_pid


@app.get(
    "/catalogue/public/datasets",
    response_model=list[Dataset],
    tags=["Catalogue"],
    summary="Returns public datasets",
    description="Returns public datasets filtered by date range, technique, and instrument.",
    operation_id="get_catalogue_public_datasets",
)
def get_public_datasets(
    startDate: Annotated[
        datetime,
        Query(
            description="Start date, ISO 8601 date-time.",
            examples=["2024-01-01T00:00:00Z"],
        ),
    ],
    endDate: Annotated[
        datetime,
        Query(
            description="End date, ISO 8601 date-time.",
            examples=["2024-12-31T23:59:59Z"],
        ),
    ],
    techniquePids: Annotated[
        str | None,
        Query(
            description="Technique PIDs used to filter datasets, comma-separated.",
            examples=["https://w3id.org/PaN/ESRFET#XAS"],
        ),
    ] = None,
    instrumentName: Annotated[
        str | None,
        Query(
            description="Name of the beamline or instrument.",
            examples=["ID21"],
        ),
    ] = None,
) -> list[Dataset]:
    requested_techniques = parse_technique_pids(techniquePids)
    requested_instrument = instrumentName.lower() if instrumentName else None

    return [
        dataset
        for dataset in FAKE_DATASETS
        if dataset.startDate >= startDate
        and dataset.endDate <= endDate
        and (
            not requested_techniques
            or requested_techniques.intersection(
                canonical_technique_pid(pid) for pid in dataset.techniquePids
            )
        )
        and (
            requested_instrument is None
            or dataset.instrumentName.lower() == requested_instrument
        )
    ]


@app.get(
    "/icat/catalogue/public/datasets",
    response_model=None,
    tags=["ICAT Proxy"],
    summary="Returns public datasets from the real ESRF ICAT+ endpoint",
    description=(
        "Forwards only startDate, endDate, techniquePids, and instrumentName "
        "to the real ESRF ICAT+ /catalogue/public/datasets endpoint."
    ),
    operation_id="get_real_icat_public_datasets",
)
def get_real_icat_public_datasets(
    startDate: Annotated[
        date,
        Query(
            description="Start date forwarded to ICAT+ in YYYY-MM-DD format.",
            examples=["2024-01-01"],
        ),
    ],
    endDate: Annotated[
        date,
        Query(
            description="End date forwarded to ICAT+ in YYYY-MM-DD format.",
            examples=["2024-12-31"],
        ),
    ],
    techniquePids: Annotated[
        str | None,
        Query(
            description="Technique PIDs forwarded to ICAT+, comma-separated.",
            examples=["https://w3id.org/PaN/ESRFET#XAS"],
        ),
    ] = None,
    instrumentName: Annotated[
        str | None,
        Query(
            description="Beamline or instrument name forwarded to ICAT+.",
            examples=["ID21"],
        ),
    ] = None,
) -> Any:
    try:
        return fetch_icat_public_datasets(
            start_date=startDate,
            end_date=endDate,
            technique_pids=techniquePids,
            instrument_name=instrumentName,
        )
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code,
            detail={
                "upstream": ICAT_PUBLIC_DATASETS_URL,
                "message": exc.response.text,
            },
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "upstream": ICAT_PUBLIC_DATASETS_URL,
                "message": str(exc),
            },
        ) from exc


@app.get(
    "/map",
    response_model=MappingResponse,
    tags=["Ontology Mapping"],
    summary="Map a PANET term to ESRFET",
    description=(
        "Queries the local ESRFET ontology for owl:equivalentClass mappings "
        "from a PANET term to ESRFET terms."
    ),
    operation_id="map_panet_to_esrfet",
)
def map_panet_to_esrfet(
    term: Annotated[
        str,
        Query(
            description="PANET term IRI, compact term, or local identifier.",
            examples=["http://purl.org/pan-science/PaNET/PaNET01196", "PaNET:PaNET01196", "PaNET01196"],
        ),
    ],
    source: Annotated[
        str,
        Query(
            description="Source ontology. The current demonstrator supports PANET.",
            examples=["PANET"],
        ),
    ] = "PANET",
    target: Annotated[
        str,
        Query(
            description="Target ontology. The current demonstrator supports ESRFET.",
            examples=["ESRFET"],
        ),
    ] = "ESRFET",
) -> MappingResponse:
    mappings = []
    if source.upper() == "PANET" and target.upper() == "ESRFET":
        mappings = [MappingResult(**mapping) for mapping in query_panet_to_esrfet(term)]

    return MappingResponse(
        source=source.upper(),
        target=target.upper(),
        term=term,
        targetTerm=mappings[0].targetTerm if mappings else None,
        mappings=mappings,
    )


@app.get("/health", tags=["Service"], summary="Health check")
def health() -> dict[str, str]:
    return {"status": "ok"}


def add_semantic_annotations(openapi_schema: dict) -> dict:
    openapi_schema["x-supported-ontologies"] = {
        "ESRFET": ESRFET.rstrip("#"),
        "ESRFET-PURL": ESRFET_PURL.rstrip("#"),
        "PaNET": PANET.rstrip("/"),
        "OWL": OWL.rstrip("#"),
        "OWL-Time": OWL_TIME.rstrip("#"),
        "XSD": XSD.rstrip("#"),
        "DCAT": DCAT.rstrip("#"),
        "Dublin Core Terms": DCTERMS.rstrip("/"),
        "schema.org": SCHEMA.rstrip("/"),
    }

    operation = openapi_schema["paths"]["/catalogue/public/datasets"]["get"]
    operation["x-semantic-operation"] = {
        "type": DCAT + "DataService",
        "returns": DCAT + "Dataset",
        "supportedOntologies": ["ESRFET", "OWL-Time", "XSD", "DCAT", "schema.org"],
    }
    operation["x-jsonld-context"] = {
        "dcat": DCAT,
        "dcterms": DCTERMS,
        "schema": SCHEMA,
        "esrfet": ESRFET,
        "time": OWL_TIME,
        "xsd": XSD,
    }

    parameter_annotations = {
        "startDate": {
            "x-semantic-type": OWL_TIME + "Instant",
            "x-datatype": XSD + "dateTime",
            "x-jsonld-property": SCHEMA + "startDate",
        },
        "endDate": {
            "x-semantic-type": OWL_TIME + "Instant",
            "x-datatype": XSD + "dateTime",
            "x-jsonld-property": SCHEMA + "endDate",
        },
        "techniquePids": {
            "x-semantic-type": ESRFET + "experimental_technique",
            "x-ontology": ESRFET.rstrip("#"),
            "x-value-kind": "comma-separated-iri-list",
            "x-jsonld-property": ESRFET + "usesTechnique",
        },
        "instrumentName": {
            "x-semantic-type": SCHEMA + "instrument",
            "x-jsonld-property": SCHEMA + "instrument",
        },
    }

    for parameter in operation.get("parameters", []):
        parameter.update(parameter_annotations.get(parameter["name"], {}))

    icat_operation = openapi_schema["paths"]["/icat/catalogue/public/datasets"]["get"]
    icat_operation["x-semantic-operation"] = {
        "type": DCAT + "DataService",
        "upstream": ICAT_PUBLIC_DATASETS_URL,
        "forwardsOnlyQueryParameters": [
            "startDate",
            "endDate",
            "techniquePids",
            "instrumentName",
        ],
        "returns": DCAT + "Dataset",
        "supportedOntologies": ["ESRFET", "OWL-Time", "XSD", "DCAT", "schema.org"],
    }
    icat_operation["x-jsonld-context"] = operation["x-jsonld-context"]
    icat_parameter_annotations = {
        **parameter_annotations,
        "startDate": {
            "x-semantic-type": OWL_TIME + "Instant",
            "x-datatype": XSD + "date",
            "x-jsonld-property": SCHEMA + "startDate",
        },
        "endDate": {
            "x-semantic-type": OWL_TIME + "Instant",
            "x-datatype": XSD + "date",
            "x-jsonld-property": SCHEMA + "endDate",
        },
    }
    for parameter in icat_operation.get("parameters", []):
        parameter.update(icat_parameter_annotations.get(parameter["name"], {}))

    mapping_operation = openapi_schema["paths"]["/map"]["get"]
    mapping_operation["x-semantic-operation"] = {
        "type": "https://schema.org/Action",
        "sourceOntology": PANET.rstrip("/"),
        "targetOntology": ESRFET_PURL.rstrip("#"),
        "mappingPredicate": OWL + "equivalentClass",
        "queryEngine": "OWL/XML ontology loaded with owlready2 and queried as RDF with SPARQL",
    }
    mapping_parameter_annotations = {
        "term": {
            "x-semantic-type": PANET + "PaNETConcept",
            "x-ontology": PANET.rstrip("/"),
            "x-value-kind": "iri-or-curie",
            "x-query-role": "source ontology term",
        },
        "source": {
            "x-semantic-type": "https://schema.org/DefinedTermSet",
            "x-default-ontology": PANET.rstrip("/"),
        },
        "target": {
            "x-semantic-type": "https://schema.org/DefinedTermSet",
            "x-default-ontology": ESRFET_PURL.rstrip("#"),
        },
    }
    for parameter in mapping_operation.get("parameters", []):
        parameter.update(mapping_parameter_annotations.get(parameter["name"], {}))

    return openapi_schema


def custom_openapi() -> dict:
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    app.openapi_schema = add_semantic_annotations(openapi_schema)
    return app.openapi_schema


app.openapi = custom_openapi
