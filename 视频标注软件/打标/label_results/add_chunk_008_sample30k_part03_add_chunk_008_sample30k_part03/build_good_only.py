import json
from pathlib import Path

INPUT_FILE = Path("labeled_with_tag.json")
OUTPUT_FILE = Path("good_only.json")
OUTPUT_SIZE_FILE = Path("good_with_object_size.json")


def normalize_object_size(value):
    if value is None:
        return None
    text = str(value).strip().lower()
    mapping = {
        "large": "large",
        "big": "large",
        "small": "small",
        "tiny": "small",
    }
    return mapping.get(text)


def main():
    if not INPUT_FILE.exists():
        raise SystemExit(f"Missing {INPUT_FILE}")
    data = json.loads(INPUT_FILE.read_text(encoding="utf-8"))
    good = []
    sized_good = []
    for item in data:
        if item.get("tag") == "good":
            row = dict(item)
            row.pop("tag", None)
            if "good_size_tag" in row and "object_size" not in row:
                row["object_size"] = row.pop("good_size_tag")
            size = normalize_object_size(row.get("object_size"))
            if size:
                row["object_size"] = size
                sized_good.append(dict(row))
            good.append(row)
    OUTPUT_FILE.write_text(json.dumps(good, ensure_ascii=False, indent=2), encoding="utf-8")
    OUTPUT_SIZE_FILE.write_text(json.dumps(sized_good, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(good)} items to {OUTPUT_FILE}")
    print(f"Wrote {len(sized_good)} items to {OUTPUT_SIZE_FILE}")


if __name__ == "__main__":
    main()
