import json
import urllib.parse
import re
import requests

NLM_BASE_URL = "https://clinicaltables.nlm.nih.gov/api/npi_org/v3/search"
NLM_EXTRA_FIELDS = "NPI,name,addr_practice,misc.last_update_date"
NLM_MAX_RESULTS = 200

ZIPCODES_PROXY_URL = "/external-integrations/proxy/drug_search_dev/zipcodes_api"

RETAIL_TAXONOMY = "(3336C0003X+OR+3336C0002X+OR+3336I0012X)"
DIGITAL_TAXONOMY = "(3336M0002X+OR+3336S0011X+OR+3336H0001X)"


# ============== UTILITIES ==============

def format_zip(zip_raw: str) -> str:
    if not zip_raw:
        return ""
    return "".join(c for c in str(zip_raw) if c.isdigit())[:5]


def clean_street_name(street_raw):
    if not street_raw:
        return ""
    # Strip leading house numbers
    name = re.sub(r'^\d+[-\w/]*\s+', '', street_raw)
    # Strip common street suffixes
    suffixes = r'\b(STREET|ST|AVENUE|AVE|BOULEVARD|BLVD|ROAD|RD|HIGHWAY|HWY|LANE|LN|COURT|CT|DRIVE|DR|PARKWAY|PKWY)\b'
    name = re.sub(suffixes, '', name, flags=re.IGNORECASE)
    return name.strip()


# ============== NLM QUERY ==============

def parse_nlm_org_response(data) -> list:
    """
    Parses NLM Clinical Tables npi_org response into list of pharmacy dicts.
    Response format: [totalCount, npiCodes, extraFieldsHash, displayStrings]
    """
    if not isinstance(data, list) or len(data) < 3:
        return []

    npi_codes = data[1]
    extra_fields = data[2]

    if not npi_codes:
        return []

    names_arr = extra_fields.get("name") or []
    addrs_arr = extra_fields.get("addr_practice") or []
    updates_arr = extra_fields.get("misc.last_update_date") or []

    results = []
    for i, npi in enumerate(npi_codes):
        name_obj = names_arr[i] if i < len(names_arr) else {}
        name = name_obj.get("full", "") if isinstance(name_obj, dict) else str(name_obj or "")

        addr = addrs_arr[i] if i < len(addrs_arr) else {}
        if not isinstance(addr, dict):
            addr = {}

        last_update = updates_arr[i] if i < len(updates_arr) else ""
        if isinstance(last_update, list) and last_update:
            last_update = last_update[0]

        results.append({
            "npi": npi,
            "name": name or "",
            "street": addr.get("line1", ""),
            "street2": addr.get("line2", ""),
            "city": addr.get("city", ""),
            "state": addr.get("state", ""),
            "zipcode": format_zip(addr.get("zip", "")),
            "phone": addr.get("phone", ""),
            "last_update": last_update,
        })
    return results


def _fit_zip_filter(zip_codes: list, filters: list) -> tuple:
    """
    Fits as many zip codes as possible into the remaining URL budget (~4000 chars).
    Returns (filter_str, used_count, last_distance_miles).
    Each zip is 5 chars; +OR+ separator adds 4 chars after the first (9 chars/zip).
    """
    base = f"{NLM_BASE_URL}?terms=&count={NLM_MAX_RESULTS}&ef={urllib.parse.quote(NLM_EXTRA_FIELDS, safe=',')}&q="
    q_prefix = "+AND+".join(filters) + ("+AND+" if filters else "")
    zip_clause_overhead = len("addr_practice.zip:()")
    available = 4000 - len(base) - len(q_prefix) - zip_clause_overhead
    max_zips = max(1, (available + 4) // 9)
    used_pairs = zip_codes[:max_zips]
    zips_or = "+OR+".join(code for code, _ in used_pairs)
    return f"addr_practice.zip:({zips_or})", len(used_pairs), used_pairs[-1][1]


def query_nlm_pharmacy(
    name: str,
    pharmacy_type: str = "",
    zip_codes: list = None,
    state: str = "",
    city: str = "",
    streets: str = "",
    alternative_names: str = "",
) -> list:
    """
    Queries NLM Clinical Tables npi_org API by pharmacy name with optional filters.
    zip_codes is a list of (code, distance_miles) tuples; fills as many as fit in ~4000 char URL.
    Falls back to state/city when zip_codes is None or empty.
    """
    filters = []

    if pharmacy_type == "digital":
        filters.append(f"licenses.taxonomy.code:{DIGITAL_TAXONOMY}")
    elif pharmacy_type == "retail":
        filters.append(f"licenses.taxonomy.code:{RETAIL_TAXONOMY}")

    all_names = [name.strip()]
    if alternative_names:
        all_names += [n.strip() for n in alternative_names.split(",") if n.strip()]
    name_terms_encoded = "+OR+".join(urllib.parse.quote(n, safe='') for n in all_names if n)
    filters.append(f"name.full:({name_terms_encoded})")

    if streets:
        street_list = [s.strip() for s in streets.split(",") if s.strip()]
        street_clauses = []
        for s in street_list:
            terms = "+AND+".join(urllib.parse.quote(w, safe="") for w in clean_street_name(s).split())
            if terms:
                street_clauses.append(terms)
        if street_clauses:
            filters.append(f"addr_practice.line1:({'+OR+'.join(street_clauses)})")

    used_zip_count = 0
    last_distance = None
    if not zip_codes:
        if state:
            filters.append(f"addr_practice.state:{urllib.parse.quote(state, safe='')}")
        if city:
            filters.append(f'addr_practice.city:"{urllib.parse.quote(city, safe="")}"')
    else:
        zip_filter, used_zip_count, last_distance = _fit_zip_filter(zip_codes, filters)
        filters.append(zip_filter)

    base = f"{NLM_BASE_URL}?terms=&count={NLM_MAX_RESULTS}&ef={urllib.parse.quote(NLM_EXTRA_FIELDS, safe=',')}"
    url = base + "&q=" + "+AND+".join(filters)

    total_zips = len(zip_codes) if zip_codes else 0
    zip_summary = (
        f"zips={used_zip_count}/{total_zips}"
        + (f", farthest={last_distance} mi" if last_distance is not None else "")
        if total_zips else "zips=0"
    )
    outputs.log(  # noqa: F821
        f"NLM query: name='{name}' type='{pharmacy_type}' "
        f"state='{state}' city='{city}' streets='{streets}' {zip_summary}"
    )

    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return parse_nlm_org_response(resp.json())
    except requests.exceptions.RequestException as e:
        outputs.log(f"ERROR: NLM query failed: {e}")  # noqa: F821
        return []


def get_nearby_zips(zip_code: str) -> list:
    # Limit is 100 miles because it's max for 1 credit cost.
    url = f"{ZIPCODES_PROXY_URL}/radius?code={zip_code}&max=100"
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
        outputs.log(f"ERROR: Failed to fetch nearby zips for {zip_code}: {e}")  # noqa: F821
        return []


# ============== MAIN EXECUTION ==============

pharmacy_name = str(inputs.pharmacy_name).strip() if inputs.pharmacy_name else ""  # noqa: F821
pharmacy_type = str(getattr(inputs.pharmacy_type, "name", inputs.pharmacy_type) or "").strip().lower() if inputs.pharmacy_type else ""  # noqa: F821
zip_code = format_zip(str(inputs.zip)) if inputs.zip else ""  # noqa: F821
state = str(inputs.state).strip() if inputs.state else ""  # noqa: F821
city = str(inputs.city).strip() if inputs.city else ""  # noqa: F821
streets = str(inputs.streets).strip() if inputs.streets else ""  # noqa: F821
street_number = str(inputs.street_number).strip() if inputs.street_number else ""  # noqa: F821
search_strategy = str(getattr(inputs.search_strategy, "name", inputs.search_strategy) or "").strip().lower() if inputs.search_strategy else ""  # noqa: F821
alternative_names = str(inputs.alternative_names).strip() if inputs.alternative_names else ""  # noqa: F821

outputs.log(  # noqa: F821
    f"Lookup: name='{pharmacy_name}' type='{pharmacy_type}' "
    f"zip='{zip_code}' state='{state}' city='{city}' streets='{streets}' "
    f"strategy='{search_strategy}'"
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
            outputs.log(f"No nearby zips found for {zip_code}, falling back to exact zip")  # noqa: F821
            zip_codes = [(zip_code, None)]
    else:
        zip_codes = [(zip_code, None)]

candidates = query_nlm_pharmacy(
    name=pharmacy_name,
    alternative_names=alternative_names,
    pharmacy_type=pharmacy_type,
    zip_codes=zip_codes,
    state=state,
    city=city,
    streets=streets,
)
outputs.log(f"NLM returned {len(candidates)} candidates")  # noqa: F821
outputs.log(f"Search strategy: {search_strategy}, zip_code: {zip_code}")  # noqa: F821

# When radius returned multiple candidates, try filtering to exact zip for a unique match
if len(candidates) > 1 and search_strategy == "radius" and zip_code:
    exact_zip_matches = [c for c in candidates if c["zipcode"] == zip_code]
    outputs.log(f"Radius returned {len(candidates)} candidates; {len(exact_zip_matches)} in exact zip {zip_code}")  # noqa: F821
    if len(exact_zip_matches) > 0:
        candidates = exact_zip_matches

# When still multiple candidates, try filtering by street number as a final disambiguator
if len(candidates) > 1 and street_number:
    number_matches = [c for c in candidates if c["street"].split()[0] == street_number]
    outputs.log(f"Street number filter '{street_number}': {len(number_matches)} of {len(candidates)} candidates match")  # noqa: F821
    if len(number_matches) > 0:
        candidates = number_matches

location = zip_code or (f"{city}, {state}".strip(", ") if city or state else "")

def _fmt_pharmacy(p):
    addr = p["street"] + (" " + p["street2"] if p.get("street2") else "")
    return f"{p['name']} — {addr}, {p['city']}, {p['state']} {p['zipcode']}"

if len(candidates) == 0:
    outputs.log("No matches found")  # noqa: F821
    outputs.match_status = "No Match"  # noqa: F821
    outputs.failure_message = f"No pharmacy found matching '{pharmacy_name}'" + (f" near {location}" if location else "")  # noqa: F821
    outputs.candidate_matches = None  # noqa: F821
elif len(candidates) == 1:
    pharmacy = candidates[0]
    outputs.log("Unique match found")  # noqa: F821
    outputs.match_status = "Match"  # noqa: F821
    outputs.failure_message = None  # noqa: F821
    outputs.candidate_matches = None  # noqa: F821
    outputs.pharmacy_npi = pharmacy["npi"]  # noqa: F821
    outputs.pharmacy_name = pharmacy["name"]  # noqa: F821
    outputs.pharmacy_street = pharmacy["street"] + (" " + pharmacy["street2"] if pharmacy.get("street2") else "")  # noqa: F821
    outputs.pharmacy_city = pharmacy["city"]  # noqa: F821
    outputs.pharmacy_state = pharmacy["state"]  # noqa: F821
    outputs.pharmacy_zipcode = pharmacy["zipcode"]  # noqa: F821
    outputs.pharmacy_phone = pharmacy["phone"]  # noqa: F821
else:
    outputs.log(f"Multiple matches found: {len(candidates)}")  # noqa: F821
    outputs.match_status = "Ambiguous"  # noqa: F821
    outputs.failure_message = f"{len(candidates)} pharmacies found matching '{pharmacy_name}'" + (f" near {location}" if location else "")  # noqa: F821
    outputs.candidate_matches = json.dumps([_fmt_pharmacy(c) for c in candidates])  # noqa: F821

outputs.candidate_count = len(candidates)  # noqa: F821
