import logging
import re
import time
from typing import Optional, Tuple, Dict, List
import httpx

logger = logging.getLogger(__name__)

# In-memory cache to strictly adhere to Nominatim usage policy (prevent repeated requests for same query)
_GEOCODE_CACHE: Dict[str, Tuple[Optional[float], Optional[float], Optional[str]]] = {}
_LAST_REQUEST_TIME: float = 0.0

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "RESQ-OS-Disaster-Response-Coordination/1.0 (hackathon-mvp; simulation)"


def _clean_query(text: str) -> str:
    """Strip extraneous whitespace and punctuation."""
    cleaned = re.sub(r"\s+", " ", text).strip(" ,.-")
    return cleaned


def _build_candidates(address: str) -> List[str]:
    """
    Builds progressive candidate queries from most specific to broader locality.
    Preserves city/town names like 'Pakala' before falling back to district.
    """
    candidates = [address.strip()]
    parts = [p.strip() for p in address.split(",") if p.strip()]

    # If address has multiple parts (e.g. "13-87/A1, Chargemenline street, Pakala, Tirupati District, Andhra Pradesh, India")
    if len(parts) >= 3:
        # Candidate A: Drop door/house number (parts[1:])
        candidates.append(", ".join(parts[1:]))

        # Candidate B: Drop door number and street name (parts[2:]) -> e.g. "Pakala, Tirupati District, Andhra Pradesh, India"
        candidates.append(", ".join(parts[2:]))

        # Candidate C: Try city + state + country if 4+ parts
        if len(parts) >= 4:
            # Look for town/city index
            candidates.append(f"{parts[2]}, {parts[-2]}, {parts[-1]}")
            candidates.append(f"{parts[2]}, {parts[-1]}")

    elif len(parts) == 2:
        candidates.append(parts[0])
        candidates.append(parts[1])

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for c in candidates:
        cleaned = _clean_query(c)
        if cleaned and cleaned.lower() not in seen:
            seen.add(cleaned.lower())
            unique.append(cleaned)

    return unique


def geocode_address(address: str) -> Tuple[Optional[float], Optional[float], Optional[str]]:
    """
    Geocodes an address string to (latitude, longitude, display_name).
    Uses caching and progressive fallback queries.
    Never fabricates coordinates or silently returns an unrelated default location.
    Returns (None, None, None) on failure.
    """
    global _LAST_REQUEST_TIME

    if not address or not address.strip():
        return (None, None, None)

    normalized_key = address.strip().lower()
    if normalized_key in _GEOCODE_CACHE:
        logger.info(f"Geocode cache hit for: {address}")
        return _GEOCODE_CACHE[normalized_key]

    candidates = _build_candidates(address)

    for query in candidates:
        now = time.time()
        elapsed = now - _LAST_REQUEST_TIME
        if elapsed < 1.1:
            time.sleep(1.1 - elapsed)

        try:
            _LAST_REQUEST_TIME = time.time()
            response = httpx.get(
                NOMINATIM_URL,
                params={
                    "q": query,
                    "format": "json",
                    "limit": 1,
                    "addressdetails": 1,
                },
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept-Language": "en",
                },
                timeout=6.0,
            )

            if response.status_code == 200:
                results = response.json()
                if results and len(results) > 0:
                    first = results[0]
                    lat = round(float(first["lat"]), 6)
                    lon = round(float(first["lon"]), 6)
                    display_name = first.get("display_name", query)
                    logger.info(f"Geocoded '{address}' via candidate '{query}' -> ({lat}, {lon}) [{display_name}]")
                    result = (lat, lon, display_name)
                    _GEOCODE_CACHE[normalized_key] = result
                    return result
        except Exception as e:
            logger.warning(f"Geocoding network error for '{query}': {e}")
            continue

    # If all candidates fail, cache negative result to prevent repeated requests
    logger.info(f"Geocoding could not locate coordinates for address: {address}")
    negative_result = (None, None, None)
    _GEOCODE_CACHE[normalized_key] = negative_result
    return negative_result
