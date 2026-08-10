import json
import re
import urllib.parse
import requests
from typing import Optional

# Maps prompt-supplied form categories to FDA clean_form values.
# clean_form splits on comma/slash and takes the first token, so all
# "TABLET, *" variants collapse to "TABLET", "INJECTION, *" to "INJECTION", etc.
# Fallback: if input_form is not in this map, it is used as a literal.
FORM_MAP = {
    "TABLET": {"TABLET", "PILL"},
    "CAPSULE": {"CAPSULE"},
    "LIQUID": {"SOLUTION", "LIQUID", "SYRUP", "ELIXIR", "SUSPENSION", "CONCENTRATE"},
    "INHALER": {"AEROSOL"},
    "INHALANT": {"INHALANT"},
    "NEBULIZER": {"INHALATION SOLUTION", "SOLUTION"},
    "INJECTION": {"INJECTION", "INJECTABLE"},
    "PATCH": {"PATCH"},
    "CREAM": {"CREAM"},
    "OINTMENT": {"OINTMENT"},
    "GEL": {"GEL"},
    "LOTION": {"LOTION"},
    "SPRAY": {"SPRAY", "AEROSOL"},
    "DROPS": {"SOLUTION", "SUSPENSION"},
    "POWDER": {"POWDER"},
    "SUPPOSITORY": {"SUPPOSITORY"},
    "LOZENGE": {"LOZENGE", "TROCHE"},
    "FILM": {"FILM"},
    "IMPLANT": {"IMPLANT", "PELLET"},
    "RING": {"RING"},
    "INSERT": {"INSERT"},
    "FOAM": {"AEROSOL", "INJECTABLE FOAM"},
}


# Forms where package size (volume, weight, or dose count) affects the NDC
# and must be resolved before a canonical NDC can be selected.
PACKAGE_AMBIGUOUS_FORMS = {
    "LIQUID", "DROPS", "NEBULIZER", "INJECTION",
    "INHALER", "INHALANT",
    "CREAM", "OINTMENT", "GEL", "LOTION", "FOAM", "SPRAY",
}


def capitalize_words(s: str) -> str:
    if not s:
        return ""
    return " ".join(
        w[0].upper() + w[1:].lower() if w else ""
        for w in s.split(" ")
    )


def clean_brand_name(result: dict) -> str:
    brand_name = (result.get("brand_name") or "").strip()
    generic_name = (result.get("generic_name") or "").strip()

    active_ingredients = result.get("active_ingredients") or []
    ingredient_names = sorted(
        name for name in (
            (ing.get("name") or "").strip()
            for ing in active_ingredients
        )
        if name
    )
    ingredients_string = " + ".join(ingredient_names) or generic_name

    if brand_name and generic_name:
        if generic_name.lower() in brand_name.lower():
            return capitalize_words(ingredients_string)
        else:
            return capitalize_words(brand_name)
    elif brand_name:
        return capitalize_words(brand_name)
    else:
        return capitalize_words(ingredients_string)


def clean_form(raw_form: str) -> str:
    if not raw_form:
        return ""
    form = re.split(r"[,/]", raw_form)[0].strip()
    form = re.sub(r"^FOR\s+", "", form, flags=re.IGNORECASE)
    return form.upper()


def parse_strengths(ingredients: list) -> list:
    results = []
    for ing in ingredients:
        strength = (ing.get("strength") or "").strip()
        if not strength:
            continue
        strength = re.sub(r"/1$", "", strength)
        parts = strength.split(" ")
        try:
            quantity = float(parts[0])
            unit = (parts[1] if len(parts) > 1 else "").upper()
            results.append({"quantity": quantity, "unit": unit})
        except (ValueError, IndexError):
            pass
    return results


def build_drug_label(result: dict) -> str:
    brand = clean_brand_name(result)
    form = clean_form(result.get("dosage_form", ""))
    strengths = parse_strengths(result.get("active_ingredients") or [])
    strength_str = " | ".join(
        f"{s['quantity']:g} {s['unit']}".strip() for s in strengths
    )
    return " ".join(part for part in [brand, form, strength_str] if part)


def normalize_ndc(ndc: str) -> str:
    parts = ndc.split("-")
    if len(parts) == 3:
        return parts[0].zfill(5) + parts[1].zfill(4) + parts[2].zfill(2)
    return ndc


def get_min_ndc_by_start_date(packaging: list) -> Optional[dict]:
    min_pkg = None
    min_date = None
    for p in packaging:
        start_date = p.get("marketing_start_date")
        if not start_date:
            continue
        if min_date is None or start_date < min_date:
            min_date = start_date
            min_pkg = p
        elif start_date == min_date:
            if p.get("package_ndc", "") < min_pkg.get("package_ndc", ""):
                min_pkg = p
    return min_pkg


def extract_and_flatten_packaging(items: list) -> list:
    return [pkg for item in items for pkg in (item.get("packaging") or [])]


def parse_package_size(description: str) -> Optional[tuple]:
    """
    Extract (quantity_float, unit_str) representing the dispensed unit size.
    Handles multi-level descriptions:
      '2.5 mL in 1 BOTTLE'
        -> (2.5, 'ML')
      '30 TABLET in 1 BOTTLE; 1 BOTTLE in 1 CARTON'
        -> (30.0, 'TABLET')
      '1 CANISTER in 1 CARTON (82804-036-67) / 200 AEROSOL, METERED in 1 CANISTER'
        -> (200.0, 'AEROSOL')
    """
    if not description:
        return None
    # Strip parenthetical NDC codes
    desc = re.sub(r'\([^)]+\)', '', description).strip()
    # Take the last slash-separated segment (innermost unit for multi-level packages)
    last_segment = re.split(r'\s*/\s*', desc)[-1].strip()
    # Take the first semicolon-separated part (drops outer carton reference)
    primary = last_segment.split(';')[0].strip()
    m = re.match(r'^([\d.]+)\s*([a-zA-Z]+)', primary)
    if not m:
        return None
    try:
        return (float(m.group(1)), m.group(2).upper())
    except ValueError:
        return None


def get_canonical_packages(packaging: list) -> list:
    """
    Returns one canonical package per distinct size (qty, unit).
    Canonical = earliest marketing_start_date within each size group.
    Result is sorted by quantity ascending.
    """
    groups: dict = {}
    for pkg in packaging:
        size = parse_package_size(pkg.get("description", ""))
        if size is None:
            continue
        existing = groups.get(size)
        if existing is None:
            groups[size] = pkg
        else:
            this_date = pkg.get("marketing_start_date") or ""
            best_date = existing.get("marketing_start_date") or ""
            if this_date and (not best_date or this_date < best_date):
                groups[size] = pkg

    return [
        {
            "ndc": normalize_ndc(pkg.get("package_ndc", "")),
            "description": pkg.get("description", ""),
            "volume_qty": qty,
            "volume_unit": unit,
        }
        for (qty, unit), pkg in sorted(groups.items(), key=lambda x: x[0][0])
    ]


def query_fda(brand_name: Optional[str], generic_name: Optional[str]) -> list:
    """
    Queries FDA NDC API for the given drug name.
    Returns list of FDA result dicts, or empty list on no-results (404 NOT_FOUND).
    Raises RuntimeError on network/HTTP error.

    CRITICAL: URL is constructed manually. Do NOT use requests params dict —
    it encodes '+AND+' as '%2BAND%2B', causing HTTP 500 from FDA.
    """
    search = "finished:true+AND+product_type:PRESCRIPTION"

    # Searches for brand/generic name in both brand_name and generic_name fields
    names = {n.strip() for n in [brand_name, generic_name] if n}
    name_parts = []
    for name in sorted(names):
        encoded = urllib.parse.quote(f'"{name}"', safe="")
        name_parts.extend([f"brand_name:{encoded}", f"generic_name:{encoded}"])
    if name_parts:
        search += f"+AND+({'+OR+'.join(name_parts)})"

    url = f"https://api.fda.gov/drug/ndc.json?search={search}&limit=1000"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 404:
            error_code = resp.json().get("error", {}).get("code", "")
            if error_code == "NOT_FOUND":
                return []
            resp.raise_for_status()
        resp.raise_for_status()
        return resp.json().get("results", [])
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"api_error: {e}") from e


def group_by(results: list, key_fn) -> dict:
    groups = {}
    for r in results:
        groups.setdefault(key_fn(r), []).append(r)
    return groups


def format_strength(r: dict) -> str:
    parts = [f"{s['quantity']:g} {s['unit']}".strip() for s in parse_strengths(r.get("active_ingredients") or [])]
    return " + ".join(parts)


def truncate_list(items: list, max_shown: int = 3) -> str:
    if not items:
        return ""
    shown = ", ".join(items[:max_shown])
    remaining = len(items) - max_shown
    return f"{shown} (+{remaining} more)" if remaining > 0 else shown


def lookup_drug(entry: dict) -> dict:
    """
    FDA query -> exact name match -> NDC selection.
    Returns a result dict with match_status, ndc, drug_label, failure_reason,
    failure_message, and candidate_matches.
    Does not touch Kizen records.
    """
    transcript_name = entry.get("transcript_name", "")
    brand_name = entry.get("brand_name")
    generic_name = entry.get("generic_name")

    _none = {
        "match_status": "No Match",
        "ndc": None,
        "drug_label": None,
        "dosage": None,
        "form": None,
        "package_description": None,
        "failure_reason": None,
        "failure_message": None,
        "candidate_matches": None,
    }

    def fail(reason, candidate_matches=None, drug_label=None):
        status = "Ambiguous" if reason.startswith("ambiguous") else "No Match"
        label = drug_label or transcript_name
        if reason == "api_error":
            msg = f"FDA API error while looking up '{transcript_name}'"
        elif reason == "no_match":
            msg = f"No drug found matching '{transcript_name}'"
        elif reason == "ambiguous_name":
            names = truncate_list(candidate_matches) if candidate_matches else ""
            msg = f"Multiple drugs matched '{transcript_name}': {names}" if names else f"Multiple drugs matched '{transcript_name}'"
        elif reason == "ambiguous_form":
            forms = truncate_list(candidate_matches) if candidate_matches else ""
            msg = f"Multiple dosage forms found for '{transcript_name}': {forms}" if forms else f"Multiple dosage forms found for '{transcript_name}'"
        elif reason == "ambiguous_dosage":
            dosages = truncate_list(candidate_matches) if candidate_matches else ""
            msg = f"Multiple dosage strengths found for '{transcript_name}': {dosages}" if dosages else f"Multiple dosage strengths found for '{transcript_name}'"
        elif reason == "ambiguous_package":
            pkgs = truncate_list(candidate_matches) if candidate_matches else ""
            msg = f"Multiple package sizes for '{label}': {pkgs}" if pkgs else f"Multiple package sizes for '{label}'"
        else:
            msg = f"Lookup failed for '{transcript_name}': {reason}"
        return {**_none, "match_status": status, "failure_reason": reason, "failure_message": msg, "candidate_matches": candidate_matches, "drug_label": drug_label}

    try:
        fda_results = query_fda(brand_name, generic_name)
    except RuntimeError:
        return fail("api_error")

    if not fda_results:
        return fail("no_match")

    # Step 1: Name
    # Phase 1: exact field match on raw brand_name / generic_name fields.
    # Phase 2: if no exact matches, fall back to the full result set.
    # Collapse whichever set we have by clean_brand_name and require a single group.
    if brand_name:
        exact_matched = [
            r for r in fda_results
            if (r.get("brand_name") or "").strip().lower() == brand_name.strip().lower()
        ]
    elif generic_name:
        exact_matched = [
            r for r in fda_results
            if clean_brand_name(r).lower() == generic_name.strip().lower()
        ]
    else:
        exact_matched = []
    name_candidates = exact_matched if exact_matched else fda_results

    name_groups = group_by(name_candidates, lambda r: clean_brand_name(r).lower())
    if len(name_groups) > 1:
        return fail("ambiguous_name", candidate_matches=sorted(name_groups))
    results = list(name_groups.values())[0]

    # Step 2: Form
    # Group by dosage form. If multiple forms remain, filter by input form if provided.
    input_form = clean_form(entry.get("form") or "")
    form_groups = group_by(results, lambda r: clean_form(r.get("dosage_form", "")))

    if len(form_groups) > 1:
        if input_form:
            fda_forms = FORM_MAP.get(input_form, {input_form})
            matched_form_groups = {k: v for k, v in form_groups.items() if k in fda_forms}
            if len(matched_form_groups) == 1:
                results = list(matched_form_groups.values())[0]
            else:
                return fail("ambiguous_form", candidate_matches=sorted(form_groups))
        else:
            return fail("ambiguous_form", candidate_matches=sorted(form_groups))

    # Step 3: Dosage
    # Group by strength profile. If multiple profiles remain, filter by input dosage if provided.
    def dosage_key(r):
        return tuple(sorted(
            (s["quantity"], s["unit"])
            for s in parse_strengths(r.get("active_ingredients") or [])
        ))

    input_dosage_raw = (entry.get("dosage") or "").strip()
    input_dosage_key = dosage_key({"active_ingredients": [{"strength": input_dosage_raw}]})

    dosage_groups = group_by(results, dosage_key)

    if len(dosage_groups) > 1:
        if input_dosage_key:
            matched_dosage_groups = {
                k: v for k, v in dosage_groups.items()
                if k == input_dosage_key
            }
            if len(matched_dosage_groups) == 1:
                results = list(matched_dosage_groups.values())[0]
            else:
                return fail("ambiguous_dosage",
                            candidate_matches=sorted(format_strength(v[0]) for v in dosage_groups.values()))
        else:
            return fail("ambiguous_dosage",
                        candidate_matches=sorted(format_strength(v[0]) for v in dosage_groups.values()))

    all_packaging = extract_and_flatten_packaging(results)
    non_sample = [p for p in all_packaging if not p.get("sample")]
    packaging_candidates = non_sample if non_sample else all_packaging

    drug_label = build_drug_label(results[0])

    # For forms where package size affects the NDC, return canonical candidates
    # so the downstream step can select based on quantity/frequency context.
    if input_form in PACKAGE_AMBIGUOUS_FORMS:
        canonical = get_canonical_packages(packaging_candidates)
        if not canonical:
            return fail("no_match", drug_label=drug_label)
        if len(canonical) == 1:
            return {**_none, "match_status": "Match", "ndc": canonical[0]["ndc"], "drug_label": drug_label, "package_description": canonical[0]["description"]}
        return fail("ambiguous_package", drug_label=drug_label, candidate_matches=[c["description"] for c in canonical])

    best_pkg = get_min_ndc_by_start_date(packaging_candidates)
    if not best_pkg:
        return fail("no_match", drug_label=drug_label)

    ndc = normalize_ndc(best_pkg.get("package_ndc", ""))
    return {**_none, "match_status": "Match", "ndc": ndc, "drug_label": drug_label, "dosage": entry.get("dosage"), "form": entry.get("form"), "package_description": best_pkg.get("description", "")}


# ============== MAIN EXECUTION ==============

entry = {
    "transcript_name": str(inputs.transcript_name),  # noqa: F821
    "brand_name": str(inputs.brand_name) if inputs.brand_name else None,  # noqa: F821
    "generic_name": str(inputs.generic_name) if inputs.generic_name else None,  # noqa: F821
    "dosage": str(inputs.dosage) if inputs.dosage else None,  # noqa: F821
    "form": str(inputs.form) if inputs.form else None,  # noqa: F821
}

result = lookup_drug(entry)

outputs.match_status = result["match_status"]  # noqa: F821
outputs.ndc = result["ndc"]  # noqa: F821
outputs.drug_label = result["drug_label"]  # noqa: F821
outputs.dosage = result["dosage"]  # noqa: F821
outputs.form = result["form"]  # noqa: F821
outputs.package_description = result["package_description"]  # noqa: F821
outputs.failure_reason = result["failure_reason"]  # noqa: F821
outputs.failure_message = result["failure_message"]  # noqa: F821
outputs.candidate_matches = json.dumps(result["candidate_matches"]) if result["candidate_matches"] else None  # noqa: F821

if result["match_status"] == "Match":
    outputs.candidate_count = 1  # noqa: F821
elif result["candidate_matches"]:
    outputs.candidate_count = len(result["candidate_matches"])  # noqa: F821
else:
    outputs.candidate_count = 0  # noqa: F821

outputs.log(  # noqa: F821
    f"{result['match_status'].upper()}: {entry['transcript_name']} — "
    + (f"NDC={result['ndc']}" if result["match_status"] == "Match" else f"reason={result['failure_reason']}")
)
