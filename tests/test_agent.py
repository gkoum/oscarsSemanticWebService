import httpx

from app.agent import (
    CATALOGUE_PATH,
    describe_semantic_contract,
    fetch_openapi,
    map_panet_to_esrfet,
    normalize_esrfet_term,
    run_interactive,
    search_datasets,
)
from app.main import app


def test_describes_semantic_contract_from_app_openapi() -> None:
    description = describe_semantic_contract(app.openapi())

    assert f"Endpoint discovered: GET {CATALOGUE_PATH}" in description
    assert "Supported vocabularies: ESRFET" in description
    assert "techniquePids" in description
    assert "https://w3id.org/PaN/ESRFET#experimental_technique" in description
    assert "http://www.w3.org/2006/time#Instant" in description


def test_normalizes_esrfet_term_short_forms() -> None:
    assert normalize_esrfet_term("XAS") == "https://w3id.org/PaN/ESRFET#XAS"
    assert normalize_esrfet_term("ESRFET:XAS") == "https://w3id.org/PaN/ESRFET#XAS"


def test_fetch_openapi_and_search_datasets_over_asgi_transport() -> None:
    transport = httpx.ASGITransport(app=app)

    async def run_request_flow() -> tuple[dict, list[dict]]:
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as async_client:
            openapi_response = await async_client.get("/openapi.json")
            datasets_response = await async_client.get(
                CATALOGUE_PATH,
                params={
                    "startDate": "2024-01-01T00:00:00Z",
                    "endDate": "2024-12-31T23:59:59Z",
                    "techniquePids": "https://w3id.org/PaN/ESRFET#XAS",
                    "instrumentName": "ID21",
                },
            )
            return openapi_response.json(), datasets_response.json()

    import anyio

    openapi_schema, datasets = anyio.run(run_request_flow)

    assert fetch_openapi_from_schema_for_test(openapi_schema)["info"]["title"] == "Semantic Web Service POC"
    assert [dataset["id"] for dataset in datasets] == [1001, 1002]


def test_search_datasets_with_mock_transport() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == CATALOGUE_PATH
        assert request.url.params["techniquePids"] == "https://w3id.org/PaN/ESRFET#XAS"
        return httpx.Response(200, json=[{"id": 1001, "name": "XAS dataset"}])

    with httpx.Client(transport=httpx.MockTransport(handler), base_url="http://agent.test") as client:
        datasets = search_datasets(
            "http://agent.test",
            "2024-01-01T00:00:00Z",
            "2024-12-31T23:59:59Z",
            "https://w3id.org/PaN/ESRFET#XAS",
            "ID21",
            client,
        )

    assert datasets == [{"id": 1001, "name": "XAS dataset"}]


def test_maps_panet_term_from_future_mapping_service_contract() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["source"] == "PANET"
        assert request.url.params["target"] == "ESRFET"
        assert request.url.params["term"] == "PaNET01196"
        return httpx.Response(
            200,
            json={"targetTerm": "http://purl.org/pan-science/ESRFET#XAS"},
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        mapped = map_panet_to_esrfet(
            "PaNET01196",
            "http://mapping.test/map",
            client,
        )

    assert mapped == "http://purl.org/pan-science/ESRFET#XAS"


def test_interactive_panet_flow_asks_to_proceed_before_search(monkeypatch) -> None:
    responses = iter(["1", "2", "PaNET01196", "yes", "", "", "ID21"])
    output: list[str] = []
    prompts: list[str] = []

    def input_func(prompt: str) -> str:
        prompts.append(prompt)
        return next(responses)

    monkeypatch.setattr(
        "app.agent.fetch_openapi",
        lambda base_url: app.openapi(),
    )
    monkeypatch.setattr(
        "app.agent.map_panet_to_esrfet",
        lambda panet_term, mapping_url: "http://purl.org/pan-science/ESRFET#XAS",
    )
    monkeypatch.setattr(
        "app.agent.search_datasets",
        lambda base_url, start_date, end_date, technique_pid, instrument_name: [
            {
                "id": 1001,
                "name": "ID21 XAS catalyst oxidation-state dataset",
                "instrumentName": instrument_name,
                "startDate": start_date,
                "endDate": end_date,
                "techniquePids": [technique_pid],
            }
        ],
    )

    exit_code = run_interactive(
        input_func=input_func,
        print_func=output.append,
    )

    assert exit_code == 0
    joined_output = "\n".join(output)
    joined_prompts = "\n".join(prompts)
    assert "Mapped PANET term to ESRFET term: http://purl.org/pan-science/ESRFET#XAS" in joined_output
    assert "Proceed with this ESRFET term for the dataset search?" in joined_prompts
    assert "Searching with techniquePids=http://purl.org/pan-science/ESRFET#XAS" in joined_output
    assert "Found 1 dataset(s):" in joined_output


def test_mapping_service_failure_returns_none() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("not available", request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert map_panet_to_esrfet("PANET:missing", "http://mapping.test/map", client) is None


def fetch_openapi_from_schema_for_test(schema: dict) -> dict:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=schema)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        return fetch_openapi("http://agent.test", client)
