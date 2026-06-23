from datetime import date, datetime, timezone

from fastapi.testclient import TestClient

from app.icat import build_icat_public_dataset_params
from app.main import app


client = TestClient(app)


def test_filters_public_datasets_by_date_technique_and_instrument() -> None:
    response = client.get(
        "/catalogue/public/datasets",
        params={
            "startDate": datetime(2024, 1, 1, tzinfo=timezone.utc).isoformat(),
            "endDate": datetime(2024, 12, 31, 23, 59, tzinfo=timezone.utc).isoformat(),
            "techniquePids": "https://w3id.org/PaN/ESRFET#XAS",
            "instrumentName": "ID21",
        },
    )

    assert response.status_code == 200
    datasets = response.json()
    assert [dataset["id"] for dataset in datasets] == [1001, 1002]


def test_openapi_contains_semantic_annotations() -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    operation = schema["paths"]["/catalogue/public/datasets"]["get"]
    parameters = {parameter["name"]: parameter for parameter in operation["parameters"]}

    assert "ESRFET" in schema["x-supported-ontologies"]
    assert operation["x-semantic-operation"]["returns"] == "http://www.w3.org/ns/dcat#Dataset"
    assert (
        parameters["techniquePids"]["x-semantic-type"]
        == "https://w3id.org/PaN/ESRFET#experimental_technique"
    )
    assert parameters["startDate"]["x-semantic-type"] == "http://www.w3.org/2006/time#Instant"


def test_maps_panet_term_to_esrfet_from_local_ontology() -> None:
    response = client.get(
        "/map",
        params={"term": "http://purl.org/pan-science/PaNET/PaNET01196"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "PANET"
    assert payload["target"] == "ESRFET"
    assert payload["targetTerm"] == "http://purl.org/pan-science/ESRFET#XAS"
    assert payload["mappings"][0]["relation"] == "owl:equivalentClass"


def test_catalogue_search_accepts_purl_esrfet_alias_from_mapping_endpoint() -> None:
    response = client.get(
        "/catalogue/public/datasets",
        params={
            "startDate": datetime(2024, 1, 1, tzinfo=timezone.utc).isoformat(),
            "endDate": datetime(2024, 12, 31, 23, 59, tzinfo=timezone.utc).isoformat(),
            "techniquePids": "http://purl.org/pan-science/ESRFET#XAS",
            "instrumentName": "ID21",
        },
    )

    assert response.status_code == 200
    datasets = response.json()
    assert [dataset["id"] for dataset in datasets] == [1001, 1002]


def test_openapi_contains_mapping_endpoint_semantic_annotations() -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    operation = schema["paths"]["/map"]["get"]
    parameters = {parameter["name"]: parameter for parameter in operation["parameters"]}

    assert operation["x-semantic-operation"]["mappingPredicate"] == "http://www.w3.org/2002/07/owl#equivalentClass"
    assert parameters["term"]["x-ontology"] == "http://purl.org/pan-science/PaNET"
    assert parameters["target"]["x-default-ontology"] == "http://purl.org/pan-science/ESRFET"


def test_builds_real_icat_params_with_only_supported_query_params() -> None:
    params = build_icat_public_dataset_params(
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
        technique_pids="https://w3id.org/PaN/ESRFET#XAS",
        instrument_name="ID21",
    )

    assert params == {
        "startDate": "2024-01-01",
        "endDate": "2024-12-31",
        "techniquePids": "https://w3id.org/PaN/ESRFET#XAS",
        "instrumentName": "ID21",
    }


def test_real_icat_proxy_endpoint_forwards_only_four_query_params(monkeypatch) -> None:
    captured: dict = {}

    def fake_fetch_icat_public_datasets(
        start_date: date,
        end_date: date,
        technique_pids: str | None = None,
        instrument_name: str | None = None,
    ) -> list[dict]:
        captured.update(
            {
                "start_date": start_date,
                "end_date": end_date,
                "technique_pids": technique_pids,
                "instrument_name": instrument_name,
            }
        )
        return [{"id": "real-icat-example", "instrumentName": instrument_name}]

    monkeypatch.setattr(
        "app.main.fetch_icat_public_datasets",
        fake_fetch_icat_public_datasets,
    )

    response = client.get(
        "/icat/catalogue/public/datasets",
        params={
            "startDate": "2024-01-01",
            "endDate": "2024-12-31",
            "techniquePids": "https://w3id.org/PaN/ESRFET#XAS",
            "instrumentName": "ID21",
            "limit": "100",
        },
    )

    assert response.status_code == 200
    assert response.json() == [{"id": "real-icat-example", "instrumentName": "ID21"}]
    assert captured["start_date"] == date(2024, 1, 1)
    assert captured["end_date"] == date(2024, 12, 31)
    assert captured["technique_pids"] == "https://w3id.org/PaN/ESRFET#XAS"
    assert captured["instrument_name"] == "ID21"


def test_openapi_contains_real_icat_proxy_annotations() -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    operation = schema["paths"]["/icat/catalogue/public/datasets"]["get"]
    parameters = {parameter["name"]: parameter for parameter in operation["parameters"]}

    assert operation["x-semantic-operation"]["upstream"] == "https://icatplus.esrf.fr/catalogue/public/datasets"
    assert operation["x-semantic-operation"]["forwardsOnlyQueryParameters"] == [
        "startDate",
        "endDate",
        "techniquePids",
        "instrumentName",
    ]
    assert set(parameters) == {"startDate", "endDate", "techniquePids", "instrumentName"}
    assert parameters["startDate"]["schema"]["format"] == "date"
    assert parameters["startDate"]["x-datatype"] == "http://www.w3.org/2001/XMLSchema#date"
    assert parameters["techniquePids"]["x-semantic-type"] == "https://w3id.org/PaN/ESRFET#experimental_technique"
