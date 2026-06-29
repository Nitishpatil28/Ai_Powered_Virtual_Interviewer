# ==========================================
# question_generator.py
# UPDATED BY GPT-5 — Phase-2 Dataset Integration
# ==========================================
import json
import random
from pathlib import Path

# Folder where all 10 company datasets are stored
DATA_DIR = Path(__file__).parent / "datasets"
GENERIC_FILE = DATA_DIR / "generic.json"


def load_company_dataset(company_name: str):
    """
    Load dataset JSON for given company name.
    Falls back to generic.json if not found.
    """
    fname = DATA_DIR / f"{company_name.lower()}.json"
    if not fname.exists():
        print(f"[WARN] Dataset for {company_name} not found. Using generic.json instead.")
        fname = GENERIC_FILE

    try:
        with open(fname, "r", encoding="utf-8") as f:
            data = json.load(f)
            print(f"[INFO] Loaded dataset for {company_name}: "
                  f"{len(data.get('aptitude', []))} aptitude, "
                  f"{len(data.get('technical', []))} technical, "
                  f"{len(data.get('gd', []))} gd, "
                  f"{len(data.get('hr', []))} hr.")
            return data
    except Exception as e:
        print(f"[ERROR] Failed loading dataset for {company_name}: {e}")
        return {"aptitude": [], "technical": [], "gd": [], "hr": []}


def get_test_package(company_name: str):
    """
    Returns a dictionary with company-specific questions:
    30 aptitude, 2 technical, 2 GD, and 5 HR questions.
    """
    ds = load_company_dataset(company_name)

    # sample while preserving structure
    aptitude = random.sample(ds.get("aptitude", []), min(30, len(ds.get("aptitude", []))))
    technical = random.sample(ds.get("technical", []), min(2, len(ds.get("technical", []))))
    gd = random.sample(ds.get("gd", []), min(2, len(ds.get("gd", []))))
    hr = random.sample(ds.get("hr", []), min(5, len(ds.get("hr", []))))

    package = {
        "company": company_name,
        "aptitude": aptitude,
        "technical": technical,
        "gd": gd,
        "hr": hr
    }

    print(f"[INFO] Test package generated for {company_name}: "
          f"{len(aptitude)} aptitude, {len(technical)} tech, "
          f"{len(gd)} gd, {len(hr)} hr.")
    return package


# quick test runner
if __name__ == "__main__":
    pkg = get_test_package("Microsoft")
    print(json.dumps(pkg, indent=2)[:1000])  # preview truncated output
