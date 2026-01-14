"""Utility script to import leads from Follow Up Boss into Supabase."""

import json
import logging
import os
import sys
from typing import Any, Dict, Iterable, List, Optional, Set

from dotenv import load_dotenv
import requests

# Ensure project modules can be imported when running as a script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)  # Backend folder (parent of scripts)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

load_dotenv()

from app.database.fub_api_client import FUBApiClient
from app.models.lead import Lead
from app.service.lead_service import LeadServiceSingleton
from app.service.lead_source_settings_service import LeadSourceSettingsSingleton


logger = logging.getLogger("fub_import")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    )
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


DEFAULT_PAGE_SIZE = 100
MAX_PAGE_SIZE = 200


def get_active_source_names() -> Set[str]:
    """Return the set of active lead source names configured in Supabase."""
    service = LeadSourceSettingsSingleton.get_instance()
    records = service.get_all(filters={"is_active": True}) or []

    active_sources: Set[str] = set()
    for record in records:
        source_name: Optional[str] = None

        if isinstance(record, dict):
            source_name = record.get("source_name")
        else:
            source_name = getattr(record, "source_name", None)

        if source_name:
            active_sources.add(source_name.strip())

    return active_sources


def fetch_people(client: FUBApiClient, page_size: int = DEFAULT_PAGE_SIZE) -> Iterable[Dict[str, Any]]:
    """
    Yield people from Follow Up Boss using pagination.

    Args:
        client: Authenticated FUB API client.
        page_size: Number of records to request per page.
    """
    if page_size > MAX_PAGE_SIZE:
        logger.warning(
            "Requested page size %s exceeds FUB maximum of %s. Using %s.",
            page_size,
            MAX_PAGE_SIZE,
            MAX_PAGE_SIZE,
        )
        page_size = MAX_PAGE_SIZE

    page = 1
    while True:
        try:
            response = client.get_people(limit=page_size, page=page)
        except requests.HTTPError as exc:
            logger.error("HTTP error fetching FUB people (page %s): %s", page, exc)
            break
        except Exception as exc:  # noqa: BLE001
            logger.error("Unexpected error fetching FUB people (page %s): %s", page, exc)
            break

        people: List[Dict[str, Any]] = response.get("people", []) or []
        if not people:
            logger.info("No more people returned from FUB (page %s).", page)
            break

        for person in people:
            yield person

        metadata = response.get("_metadata") or {}
        next_page = metadata.get("nextPage")
        has_more = metadata.get("hasMore")

        if next_page:
            page = int(next_page)
        elif has_more:
            page += 1
        else:
            logger.info("Reached last page at %s.", page)
            break


def import_leads(page_size: int = DEFAULT_PAGE_SIZE) -> Dict[str, int]:
    """Import leads from FUB into Supabase."""
    client = FUBApiClient()
    lead_service = LeadServiceSingleton.get_instance()
    active_sources = get_active_source_names()

    if active_sources:
        logger.info("Active lead sources: %s", ", ".join(sorted(active_sources)))
    else:
        logger.warning(
            "No active lead sources found. All leads will be imported without source filtering."
        )

    stats = {
        "fetched": 0,
        "considered": 0,
        "inserted": 0,
        "updated": 0,
        "skipped_existing": 0,
        "skipped_source": 0,
        "errors": 0,
    }

    for person in fetch_people(client, page_size=page_size):
        stats["fetched"] += 1

        source = (person.get("source") or "").strip()
        if active_sources and source not in active_sources:
            stats["skipped_source"] += 1
            continue

        stats["considered"] += 1

        fub_person_id = str(person.get("id"))
        try:
            if lead_service.exists_by_fub_id(fub_person_id):
                updated = lead_service.update_from_fub(person)
                if updated:
                    stats["updated"] += 1
                else:
                    stats["skipped_existing"] += 1
                continue

            lead = Lead.from_fub(person)
            lead_service.create(lead)
            stats["inserted"] += 1
        except Exception as exc:  # noqa: BLE001
            stats["errors"] += 1
            logger.error("Failed to process FUB person %s: %s", fub_person_id, exc)

    logger.info("FUB import complete: %s", json.dumps(stats, indent=2))
    return stats


def main() -> None:
    page_size_env = os.getenv("FUB_IMPORT_PAGE_SIZE")
    page_size = DEFAULT_PAGE_SIZE

    if page_size_env:
        try:
            page_size = int(page_size_env)
        except ValueError:
            logger.warning(
                "Invalid FUB_IMPORT_PAGE_SIZE value '%s'. Using default %s.",
                page_size_env,
                DEFAULT_PAGE_SIZE,
            )

    stats = import_leads(page_size=page_size)
    logger.info("Import finished. Summary: %s", json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()

