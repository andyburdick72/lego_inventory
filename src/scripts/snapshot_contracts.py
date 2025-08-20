#!/usr/bin/env python3
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE = "http://localhost:8000"

ENDPOINTS = [
    ("/api/drawers", {}),
    ("/api/containers", {"drawer_id": 1}),
    # add more here as needed
]


def fetch(path, params=None):
    url = BASE + path
    if params:
        qs = urlencode(params)
        url += "?" + qs
    req = Request(url, headers={"Accept": "application/json"})
    try:
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data
    except HTTPError as e:
        return {"__http_error__": e.code, "__url__": req.full_url, "message": e.reason}
    except URLError as e:
        return {"__http_error__": "network", "__url__": req.full_url, "message": str(e.reason)}
    except json.JSONDecodeError:
        return {
            "__http_error__": "bad_json",
            "__url__": req.full_url,
            "message": "Response was not valid JSON",
        }


def summarize_value(v):
    if v is None:
        return "None"
    t = type(v)
    if t in (int, float, bool, str):
        return t.__name__
    if isinstance(v, list):
        return "list"
    if isinstance(v, dict):
        return "object"
    return t.__name__


def union_keys(items):
    keys = set()
    for it in items:
        if isinstance(it, dict):
            keys.update(it.keys())
    return sorted(keys)


def suggest_field(name, samples):
    # pick a representative type
    types = {summarize_value(s) for s in samples}
    # Prefer int over float if it appears alone
    if types == {"int"}:
        ann = "int"
    elif types == {"float"}:
        ann = "float"
    elif types == {"bool"}:
        ann = "bool"
    elif types == {"str"}:
        ann = "str"
    elif "str" in types and len(types) > 1:
        ann = "str | None"
    elif "int" in types and "None" in types and len(types) == 2:
        ann = "int | None"
    elif "list" in types and len(types) == 1:
        ann = "list"
    elif "object" in types and len(types) == 1:
        ann = "dict"
    else:
        ann = "str | int | None"
    return f"    {name}: {ann} = None" if "None" in types else f"    {name}: {ann}"


def sample_values(items, key):
    vals = []
    for it in items:
        if isinstance(it, dict):
            vals.append(it.get(key))
    return vals


def suggest_model(name, items):
    keys = union_keys(items)
    lines = [f"class {name}(DTOBase):"]
    for k in keys:
        lines.append(suggest_field(k, sample_values(items, k)))
    return "\n".join(lines)


def main():
    for path, params in ENDPOINTS:
        print("=" * 80)
        print(f"GET {path} {params or ''}".strip())
        data = fetch(path, params)
        if isinstance(data, dict) and "__http_error__" in data:
            print(
                f"- ERROR: {data['__http_error__']} ({data.get('message')}) at {data.get('__url__')}"
            )
            print()
            continue
        if isinstance(data, list):
            print(f"- Response: list[{len(data)}]")
            sample = data[:50]  # cap
            if not sample:
                print("  (empty list)")
                continue
            print("\nSuggested DTO:\n")
            print("from pydantic import BaseModel\nfrom core.dtos import DTOBase\n")
            print(suggest_model("SuggestedItemDTO", sample))
        elif isinstance(data, dict):
            print("- Response: object")
            keys = sorted(data.keys())
            print("Top-level keys:", keys)
            # Look for common paging shapes
            if "items" in data and isinstance(data["items"], list):
                print("\nSuggested Item DTO for items[]:\n")
                print(suggest_model("SuggestedItemDTO", data["items"]))
                # Also show what the page/meta structure looks like
                for k in ("page", "meta"):
                    if isinstance(data.get(k), dict):
                        print(f"\nSuggested {k.capitalize()} DTO:\n")
                        print(suggest_model("SuggestedPageDTO", [data[k]]))
            else:
                print("\nSuggested DTO for object:\n")
                print(suggest_model("SuggestedObjectDTO", [data]))
        else:
            print(f"- Response: {type(data).__name__}")
        print()


if __name__ == "__main__":
    main()
