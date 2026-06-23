from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Callable

import httpx


CATALOGUE_PATH = "/catalogue/public/datasets"
ESRFET_PREFIX = "https://w3id.org/PaN/ESRFET#"
DEFAULT_MAPPING_SERVICE_URL = "http://127.0.0.1:8000/map"


@dataclass(frozen=True)
class Synchrotron:
    name: str
    base_url: str
    description: str
    available: bool = False


SYNCHROTRONS = [
    Synchrotron(
        name="ESRF",
        base_url=os.getenv("ESRF_SEMANTIC_SERVICE_URL", "http://127.0.0.1:8000"),
        description="Local semantic POC for the ESRF ICAT+ public datasets endpoint.",
        available=True,
    ),
    Synchrotron(
        name="Diamond Light Source",
        base_url="https://example.invalid/diamond",
        description="Placeholder option for the demonstrator.",
    ),
    Synchrotron(
        name="MAX IV",
        base_url="https://example.invalid/max-iv",
        description="Placeholder option for the demonstrator.",
    ),
]


def normalize_esrfet_term(term: str) -> str:
    cleaned = term.strip()
    if cleaned.startswith("http://") or cleaned.startswith("https://"):
        return cleaned
    if cleaned.startswith("ESRFET:"):
        cleaned = cleaned.split(":", 1)[1]
    if cleaned.startswith("#"):
        cleaned = cleaned[1:]
    return ESRFET_PREFIX + cleaned


def get_catalogue_operation(openapi_schema: dict[str, Any]) -> dict[str, Any]:
    return openapi_schema["paths"][CATALOGUE_PATH]["get"]


def fetch_openapi(base_url: str, client: httpx.Client | None = None) -> dict[str, Any]:
    close_client = client is None
    client = client or httpx.Client(timeout=10)
    try:
        response = client.get(f"{base_url.rstrip('/')}/openapi.json")
        response.raise_for_status()
        return response.json()
    finally:
        if close_client:
            client.close()


def describe_semantic_contract(openapi_schema: dict[str, Any]) -> str:
    operation = get_catalogue_operation(openapi_schema)
    supported_ontologies = openapi_schema.get("x-supported-ontologies", {})
    semantic_operation = operation.get("x-semantic-operation", {})

    lines = [
        f"Endpoint discovered: GET {CATALOGUE_PATH}",
        f"Summary: {operation.get('summary', 'No summary provided')}",
        "",
        "Semantic service description:",
        f"- Returns: {semantic_operation.get('returns', 'unknown')}",
        "- Supported vocabularies: "
        + ", ".join(supported_ontologies.keys() or ["none advertised"]),
        "",
        "Parameters:",
    ]

    for parameter in operation.get("parameters", []):
        details = [parameter.get("description", "No description")]
        if parameter.get("x-semantic-type"):
            details.append(f"semantic type {parameter['x-semantic-type']}")
        if parameter.get("x-datatype"):
            details.append(f"datatype {parameter['x-datatype']}")
        if parameter.get("x-ontology"):
            details.append(f"ontology {parameter['x-ontology']}")
        if parameter.get("x-value-kind"):
            details.append(f"value kind {parameter['x-value-kind']}")

        required = "required" if parameter.get("required") else "optional"
        lines.append(f"- {parameter['name']} ({required}): " + "; ".join(details))

    return "\n".join(lines)


def search_datasets(
    base_url: str,
    start_date: str,
    end_date: str,
    technique_pid: str,
    instrument_name: str | None,
    client: httpx.Client | None = None,
) -> list[dict[str, Any]]:
    close_client = client is None
    client = client or httpx.Client(timeout=10)
    try:
        params = {
            "startDate": start_date,
            "endDate": end_date,
            "techniquePids": technique_pid,
        }
        if instrument_name:
            params["instrumentName"] = instrument_name

        response = client.get(f"{base_url.rstrip('/')}{CATALOGUE_PATH}", params=params)
        response.raise_for_status()
        return response.json()
    finally:
        if close_client:
            client.close()


def map_panet_to_esrfet(
    panet_term: str,
    mapping_service_url: str = DEFAULT_MAPPING_SERVICE_URL,
    client: httpx.Client | None = None,
) -> str | None:
    close_client = client is None
    client = client or httpx.Client(timeout=10)
    try:
        response = client.get(
            mapping_service_url,
            params={
                "source": "PANET",
                "target": "ESRFET",
                "term": panet_term,
            },
        )
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPError:
        return None
    finally:
        if close_client:
            client.close()

    for key in ("targetTerm", "esrfetTerm", "mappedTerm", "iri"):
        mapped = payload.get(key)
        if isinstance(mapped, str) and mapped:
            return mapped

    mappings = payload.get("mappings")
    if isinstance(mappings, list) and mappings:
        first = mappings[0]
        if isinstance(first, str):
            return first
        if isinstance(first, dict):
            for key in ("targetTerm", "esrfetTerm", "mappedTerm", "iri"):
                mapped = first.get(key)
                if isinstance(mapped, str) and mapped:
                    return mapped

    return None


def choose_option(
    prompt: str,
    options: list[str],
    input_func: Callable[[str], str] = input,
    print_func: Callable[[str], None] = print,
) -> int:
    while True:
        print_func(prompt)
        for index, option in enumerate(options, start=1):
            print_func(f"{index}. {option}")

        choice = input_func("> ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(options):
            return int(choice) - 1

        print_func("Please choose one of the listed numbers.")


def confirm(
    prompt: str,
    input_func: Callable[[str], str] = input,
    print_func: Callable[[str], None] = print,
) -> bool:
    while True:
        answer = input_func(f"{prompt} [Y/n]\n> ").strip().lower()
        if answer in ("", "y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        print_func("Please answer yes or no.")


def run_interactive(
    input_func: Callable[[str], str] = input,
    print_func: Callable[[str], None] = print,
) -> int:
    print_func("Semantic experiment finder")
    print_func("")

    selected_index = choose_option(
        "Select a synchrotron:",
        [
            f"{synchrotron.name} - {synchrotron.description}"
            for synchrotron in SYNCHROTRONS
        ],
        input_func,
        print_func,
    )
    synchrotron = SYNCHROTRONS[selected_index]

    if not synchrotron.available:
        print_func(
            f"{synchrotron.name} is present as a demonstrator option, "
            "but only ESRF is wired to a local semantic endpoint right now."
        )
        return 1

    print_func("")
    print_func(f"Inspecting OpenAPI from {synchrotron.base_url}/openapi.json ...")
    try:
        openapi_schema = fetch_openapi(synchrotron.base_url)
    except httpx.HTTPError as exc:
        print_func(f"Could not inspect the OpenAPI document: {exc}")
        print_func("Start the FastAPI server first, then run this agent again.")
        return 1

    print_func("")
    print_func(describe_semantic_contract(openapi_schema))
    print_func("")

    term_mode = choose_option(
        "Search using which vocabulary?",
        ["ESRFET term", "PANET term"],
        input_func,
        print_func,
    )

    if term_mode == 0:
        raw_term = input_func("Enter ESRFET term or IRI, for example XAS or ESRFET:XAS:\n> ")
        technique_pid = normalize_esrfet_term(raw_term)
    else:
        panet_term = input_func("Enter PANET term or IRI, for example PaNET01196:\n> ").strip()
        mapping_url = os.getenv("PANET_MAPPING_SERVICE_URL", DEFAULT_MAPPING_SERVICE_URL)
        print_func(f"Contacting mapping service at {mapping_url} ...")
        mapped_term = map_panet_to_esrfet(panet_term, mapping_url)
        if mapped_term is None:
            print_func(
                "No ESRFET mapping could be retrieved for that PANET term."
            )
            return 1
        technique_pid = mapped_term
        print_func(f"Mapped PANET term to ESRFET term: {technique_pid}")
        if not confirm("Proceed with this ESRFET term for the dataset search?", input_func, print_func):
            print_func("Search cancelled.")
            return 0

    start_date = input_func("Start date-time [2024-01-01T00:00:00Z]:\n> ").strip()
    end_date = input_func("End date-time [2024-12-31T23:59:59Z]:\n> ").strip()
    instrument_name = input_func("Instrument name, optional, for example ID21:\n> ").strip()

    start_date = start_date or "2024-01-01T00:00:00Z"
    end_date = end_date or "2024-12-31T23:59:59Z"
    instrument_name = instrument_name or None

    print_func("")
    print_func(f"Searching with techniquePids={technique_pid}")
    datasets = search_datasets(
        synchrotron.base_url,
        start_date=start_date,
        end_date=end_date,
        technique_pid=technique_pid,
        instrument_name=instrument_name,
    )

    if not datasets:
        print_func("No datasets matched the query.")
        return 0

    print_func(f"Found {len(datasets)} dataset(s):")
    for dataset in datasets:
        print_func(
            f"- {dataset['id']}: {dataset['name']} | "
            f"{dataset['instrumentName']} | "
            f"{dataset['startDate']} to {dataset['endDate']} | "
            f"{', '.join(dataset['techniquePids'])}"
        )

    return 0


def main() -> None:
    raise SystemExit(run_interactive())


if __name__ == "__main__":
    main()
