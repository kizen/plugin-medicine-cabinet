import json
import re
import requests
import urllib.parse

ZIPCODES_BASE_URL = "/external-integrations/proxy/drug_search_dev/zipcodes_api"
NLM_BASE_URL = "https://clinicaltables.nlm.nih.gov/api/npi_idv/v3/search"
NLM_EXTRA_FIELDS = (
    "NPI,name.first,name.last,name.middle,name.credential,"
    "name_other.first,name_other.last,"
    "provider_type,addr_practice.line1,addr_practice.line2,"
    "addr_practice.city,addr_practice.state,addr_practice.zip,"
    "addr_practice.phone,gender"
)
NLM_MAX_RESULTS = 500
GENDER_MAP = {
    "male": "M",
    "female": "F"
}


# ============== UTILITIES ==============

def format_zip(zip_raw: str) -> str:
    if not zip_raw:
        return ""
    return "".join(c for c in str(zip_raw) if c.isdigit())[:5]


def normalize_address(text: str) -> str:
    if not text:
        return ""
    text = text.upper().replace(".", "").strip()
    patterns = {
        # Directions
        r'\bNORTH\b': 'N', r'\bSOUTH\b': 'S', r'\bEAST\b': 'E', r'\bWEST\b': 'W',
        r'\bNORTHEAST\b': 'NE', r'\bNORTHWEST\b': 'NW', r'\bSOUTHEAST\b': 'SE', r'\bSOUTHWEST\b': 'SW',
        # Primary suffixes
        r'\bSTREET\b': 'ST', r'\bAVENUE\b': 'AVE', r'\bBOULEVARD\b': 'BLVD', r'\bROAD\b': 'RD',
        r'\bDRIVE\b': 'DR', r'\bLANE\b': 'LN', r'\bCOURT\b': 'CT', r'\bPARKWAY\b': 'PKWY',
        r'\bCIRCLE\b': 'CIR', r'\bPLACE\b': 'PL', r'\bTRAIL\b': 'TRL', r'\bHIGHWAY\b': 'HWY',
        r'\bTERRACE\b': 'TER', r'\bROUTE\b': 'RTE', r'\bFREEWAY\b': 'FWY', r'\bALLEY\b': 'ALY',
        # Secondary units
        r'\bAPARTMENT\b': 'APT', r'\bSUITE\b': 'STE', r'\bUNIT\b': '#', r'\bBUILDING\b': 'BLDG',
        r'\bFLOOR\b': 'FL',
        # Ordinals
        r'\bFIRST\b': '1ST', r'\bSECOND\b': '2ND', r'\bTHIRD\b': '3RD', r'\bFOURTH\b': '4TH',
        r'\bFIFTH\b': '5TH', r'\bSIXTH\b': '6TH', r'\bSEVENTH\b': '7TH', r'\bEIGHTH\b': '8TH',
        r'\bNINTH\b': '9TH', r'\bTENTH\b': '10TH',
    }
    for pattern, replacement in patterns.items():
        text = re.sub(pattern, replacement, text)
    return re.sub(r'\s+', ' ', text).strip()


def parse_csv(val: str) -> list:
    if not val:
        return []
    return [v.strip() for v in val.split(",") if v.strip()]


def clean_street_name(street_raw: str) -> str:
    """Strip leading house number and common suffixes, leaving the meaningful street name."""
    if not street_raw:
        return ""
    name = re.sub(r'^\d+[-\w/]*\s+', '', street_raw)
    suffixes = r'\b(STREET|ST|AVENUE|AVE|BOULEVARD|BLVD|ROAD|RD|HIGHWAY|HWY|LANE|LN|COURT|CT|DRIVE|DR|PARKWAY|PKWY)\b'
    name = re.sub(suffixes, '', name, flags=re.IGNORECASE)
    return name.strip()


def _specialty_term_to_query(term: str) -> str:
    """Wildcards word stems and quotes multi-word terms, e.g Internal Medicine -> "Internal Medicine" and Cardio -> Cardio*"""
    term = term.strip()
    if " " in term:
        return f'"{term}"'
    return f'{term}*'


# ============== NLM QUERY ==============

def _get_field(extra_fields: dict, key: str, index: int) -> str:
    arr = extra_fields.get(key) or []
    return arr[index] if index < len(arr) else ""


def parse_nlm_response(data) -> list:
    if not isinstance(data, list) or len(data) < 3:
        return []

    npi_codes = data[1]
    extra_fields = data[2]

    if not npi_codes:
        return []

    providers = []
    for i, npi in enumerate(npi_codes):
        providers.append({
            "npi": npi,
            "first_name": _get_field(extra_fields, "name.first", i),
            "last_name": _get_field(extra_fields, "name.last", i),
            "middle_name": _get_field(extra_fields, "name.middle", i),
            "credential": _get_field(extra_fields, "name.credential", i),
            "other_first_name": _get_field(extra_fields, "name_other.first", i),
            "other_last_name": _get_field(extra_fields, "name_other.last", i),
            "specialty": _get_field(extra_fields, "provider_type", i),
            "street": normalize_address(_get_field(extra_fields, "addr_practice.line1", i)),
            "street2": normalize_address(_get_field(extra_fields, "addr_practice.line2", i)),
            "city": _get_field(extra_fields, "addr_practice.city", i),
            "state": _get_field(extra_fields, "addr_practice.state", i),
            "zipcode": format_zip(_get_field(extra_fields, "addr_practice.zip", i)),
            "phone": _get_field(extra_fields, "addr_practice.phone", i),
            "gender": _get_field(extra_fields, "gender", i),
        })
    return providers


def query_nlm_names(
    last_variants: list = None,
    first_variants: list = None,
    zip_codes: list = None,
    specialty_terms: list = None,
    gender: str = "",
    state: str = "",
    city: str = "",
) -> list:
    """
    Single NLM query combining all filters as AND clauses:
      name.last:(A OR B) AND name.first:(X OR Y)
        AND addr_practice.zip:(z1 OR z2)
        AND provider_type:("Internal Medicine" OR "Family Medicine")
    Name/specialty filters omitted when lists are empty/None.
    zip_codes takes priority over state/city for location filtering.
    """
    filters = []

    if last_variants:
        lasts_or = "+OR+".join(urllib.parse.quote(v, safe="") for v in last_variants)
        filters.append(f"(name.last:({lasts_or}) OR name_other.last:({lasts_or}))")

    if first_variants:
        firsts_or = "+OR+".join(urllib.parse.quote(v, safe="") for v in first_variants)
        filters.append(f"(name.first:({firsts_or}) OR name_other.first:({firsts_or}))")

    if not zip_codes and state:
        filters.append(f"addr_practice.state:{urllib.parse.quote(state, safe='')}")
        if city:
            filters.append(f'addr_practice.city:"{urllib.parse.quote(city, safe="")}"')

    if specialty_terms:
        specs_or = "+OR+".join(urllib.parse.quote(_specialty_term_to_query(t), safe="") for t in specialty_terms)
        filters.append(f"provider_type:({specs_or})")

    if gender_code := GENDER_MAP.get(gender.lower()):
        filters.append(f"gender:{urllib.parse.quote(gender_code, safe='')}")

    # Build base URL with all non-zip filters so we can measure available space
    base_url = (
        f"{NLM_BASE_URL}?terms="
        f"&maxList={NLM_MAX_RESULTS}"
        f"&ef={urllib.parse.quote(NLM_EXTRA_FIELDS, safe=',.')}"
    )
    if filters:
        base_url += "&q=" + "+AND+".join(filters)

    used_zip_count = 0
    last_distance = None
    if zip_codes:
        # zip_codes is a list of (code, distance_miles) tuples; distance may be None.
        # Use +OR+ so no %20 inflation (NLM treats + as space, same as +AND+ separators).
        # Each zip is 5 chars + 4-char +OR+ separator = 9 chars per zip after the first.
        # Measure the base URL, then fill zips to hit ~4000 chars total.
        # Overhead: "addr_practice.zip:()" = 20 chars, "+AND+" = 5 or "&q=" = 3
        zip_overhead = 20 + (5 if filters else 3)
        available = 4000 - len(base_url) - zip_overhead
        max_zips = max(1, (available + 4) // 9)
        used_pairs = zip_codes[:max_zips]
        used_zip_count = len(used_pairs)
        zips_or = "+OR+".join(code for code, _ in used_pairs)
        last_distance = used_pairs[-1][1]
        zip_filter = f"addr_practice.zip:({zips_or})"
        url = base_url + ("+AND+" if filters else "&q=") + zip_filter
    else:
        url = base_url

    total_zips = len(zip_codes) if zip_codes else 0
    zip_summary = (
        f"zips={used_zip_count}/{total_zips}"
        + (f", farthest={last_distance} mi" if last_distance is not None else "")
        if total_zips else "zips=0"
    )
    outputs.log(  # noqa: F821
        f"NLM query: last_variants={len(last_variants or [])} "
        f"first_variants={len(first_variants or [])} "
        f"specialties={len(specialty_terms or [])} "
        f"has_state={bool(state)} has_city={bool(city)} {zip_summary}"
    )
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return parse_nlm_response(resp.json())
    except Exception as e:
        outputs.log(f"ERROR: NLM query failed ({type(e).__name__})")  # noqa: F821
        return []


def get_nearby_zips(zip_code: str) -> list:
    # Use a large radius to cast a wide net; take the 100 nearest zip codes
    # Limit is 100 miles because it's max for 1 credit cost.
    url = f"{ZIPCODES_BASE_URL}/radius?code={zip_code}&max=100"
    try:
        resp = kizen.api.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])
        if not results:
            return []
        matches = results[0].get("matches", [])
        return [
            (m["code"], m.get("distance_miles"))
            for m in matches
            if m.get("code") and m.get("code_type") == "ZIP"
        ]
    except Exception as e:
        outputs.log(f"ERROR: Failed to fetch nearby zips ({type(e).__name__})")  # noqa: F821
        return []


# ============== MAIN EXECUTION ==============

first_name = str(inputs.provider_first_name).strip() if inputs.provider_first_name else ""  # noqa: F821
last_name = str(inputs.provider_last_name).strip() if inputs.provider_last_name else ""  # noqa: F821
alt_firsts = parse_csv(str(inputs.alternate_first_names) if inputs.alternate_first_names else "")  # noqa: F821
alt_lasts = parse_csv(str(inputs.alternate_last_names) if inputs.alternate_last_names else "")  # noqa: F821
specialty_terms = parse_csv(str(inputs.specialty_search_terms) if inputs.specialty_search_terms else "")  # noqa: F821

gender = str(getattr(inputs.gender, "name", inputs.gender) or "").strip().lower() if inputs.gender else ""  # noqa: F821
if gender == "unknown":
    gender = ""

zip_code = format_zip(str(inputs.zip)) if inputs.zip else ""  # noqa: F821
state = str(inputs.state).strip() if inputs.state else ""  # noqa: F821
city = str(inputs.city).strip() if inputs.city else ""  # noqa: F821
street_number = str(inputs.street_number).strip() if inputs.street_number else ""  # noqa: F821
streets = [clean_street_name(normalize_address(s)) for s in parse_csv(str(inputs.streets) if inputs.streets else "")]  # noqa: F821
search_strategy = str(getattr(inputs.search_strategy, "name", inputs.search_strategy) or "").strip().lower() if inputs.search_strategy else ""  # noqa: F821

all_lasts = ([last_name] if last_name else []) + alt_lasts
all_firsts = ([first_name] if first_name else []) + alt_firsts

outputs.log(  # noqa: F821
    f"Lookup: has_first={bool(first_name)} has_last={bool(last_name)} "
    f"has_zip={bool(zip_code)} has_state={bool(state)} has_city={bool(city)} "
    f"street_hints={len(streets)} strategy={search_strategy!r}"
)

zip_codes = None
if zip_code:
    if search_strategy == "radius":
        nearby_zip_pairs = get_nearby_zips(zip_code)
        if nearby_zip_pairs:
            zip_codes = nearby_zip_pairs
            state = ""
            city = ""
        else:
            outputs.log("No nearby zips found, falling back to exact zip")  # noqa: F821
            zip_codes = [(zip_code, None)]
    else:
        zip_codes = [(zip_code, None)]

candidates = query_nlm_names(
    last_variants=all_lasts or None,
    first_variants=all_firsts or None,
    zip_codes=zip_codes,
    specialty_terms=specialty_terms or None,
    gender=gender,
    state=state,
    city=city,
)

# When radius returned multiple candidates, try filtering to exact zip for a unique match
if len(candidates) > 1 and search_strategy == "radius" and zip_code:
    exact_zip_matches = [c for c in candidates if c["zipcode"] == zip_code]
    outputs.log(f"Radius returned {len(candidates)} candidates; {len(exact_zip_matches)} in exact zip")  # noqa: F821
    if len(exact_zip_matches) > 0:
        candidates = exact_zip_matches

# When still multiple candidates, try filtering by street name hints
if len(candidates) > 1 and streets:
    street_matches = [c for c in candidates if any(hint in clean_street_name(c["street"]) for hint in streets)]
    outputs.log(f"Street name filter applied: {len(street_matches)} of {len(candidates)} candidates match")  # noqa: F821
    if len(street_matches) > 0:
        candidates = street_matches

# When still multiple candidates, try filtering by street number as a final disambiguator
if len(candidates) > 1 and street_number:
    number_matches = [c for c in candidates if c["street"].split()[0] == street_number]
    outputs.log(f"Street number filter applied: {len(number_matches)} of {len(candidates)} candidates match")  # noqa: F821
    if len(number_matches) > 0:
        candidates = number_matches

provider_query = f"{first_name} {last_name}".strip()
location = zip_code or (f"{city}, {state}".strip(", ") if city or state else "")

def _fmt_provider(p):
    name = f"{p['first_name']} {p['last_name']}".strip()
    if p.get("credential"):
        name += f", {p['credential']}"
    parts = [name]
    if p.get("specialty"):
        parts.append(p["specialty"])
    loc = f"{p['city']}, {p['state']}".strip(", ")
    if loc:
        parts.append(loc)
    return " - ".join(parts)

if len(candidates) == 0:
    outputs.log("No matches found")  # noqa: F821
    outputs.match_status = "No Match"  # noqa: F821
    outputs.failure_message = f"No provider found matching '{provider_query}'" + (f" near {location}" if location else "")  # noqa: F821
    outputs.candidate_matches = None  # noqa: F821
elif len(candidates) == 1:
    provider = candidates[0]
    outputs.log("Unique match found, setting provider_npi output")  # noqa: F821
    outputs.match_status = "Match"  # noqa: F821
    outputs.failure_message = None  # noqa: F821
    outputs.candidate_matches = None  # noqa: F821
    outputs.provider_npi = provider["npi"]  # noqa: F821
    outputs.provider_name = f"{provider['first_name']} {provider['last_name']}"  # noqa: F821
    outputs.provider_specialty = provider["specialty"]  # noqa: F821
    alias = None
    if provider["other_first_name"] or provider["other_last_name"]:
        alias = f"{provider['other_first_name'] or provider['first_name']} {provider['other_last_name'] or provider['last_name']}"
    outputs.provider_alias = alias  # noqa: F821
    outputs.provider_street = f"{provider['street']}{' ' + provider['street2'] if provider['street2'] else ''}"  # noqa: F821
    outputs.provider_city = provider["city"]  # noqa: F821
    outputs.provider_state = provider["state"]  # noqa: F821
    outputs.provider_zipcode = provider["zipcode"]  # noqa: F821
    outputs.provider_phone = provider["phone"]  # noqa: F821
else:
    outputs.log("Multiple matches found")  # noqa: F821
    outputs.match_status = "Ambiguous"  # noqa: F821
    outputs.failure_message = f"{len(candidates)} providers found matching '{provider_query}'" + (f" near {location}" if location else "")  # noqa: F821
    outputs.candidate_matches = json.dumps([_fmt_provider(c) for c in candidates])  # noqa: F821

outputs.candidate_count = len(candidates)  # noqa: F821
