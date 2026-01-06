#!/usr/bin/env python3
"""
Merge generated CSV data into vehicles.json for Flutter app.
Run from: scripts/vehicle_data_generator/
"""

import csv
import json
import os
from pathlib import Path
from datetime import date

# Paths
SCRIPT_DIR = Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR / "output"
ASSETS_DIR = SCRIPT_DIR.parent.parent / "assets" / "data"
VEHICLES_JSON = ASSETS_DIR / "vehicles.json"


def load_csv(filename: str) -> list[dict]:
    """Load CSV file from output directory."""
    filepath = OUTPUT_DIR / filename
    if not filepath.exists():
        print(f"Warning: {filename} not found")
        return []
    
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return list(reader)


def load_existing_json() -> dict:
    """Load existing vehicles.json or create empty structure."""
    if VEHICLES_JSON.exists():
        with open(VEHICLES_JSON, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        "version": "1.0.0",
        "last_updated": str(date.today()),
        "makes": [],
        "models": [],
        "generations": [],
        "variants": []
    }


def csv_to_make(row: dict) -> dict:
    """Convert makes CSV row to JSON format."""
    return {
        "id": row["id"],
        "name": row["name"],
        "country": row.get("country", "")
    }


def csv_to_model(row: dict) -> dict:
    """Convert models CSV row to JSON format."""
    return {
        "id": row["id"],
        "make_id": row["make_id"],
        "name": row["name"],
        "body_type": row.get("body_type", "").split("|")[0],  # Take first body type
        "segment": row.get("segment", "")
    }


def csv_to_generation(row: dict) -> dict:
    """Convert generations CSV row to JSON format."""
    gen = {
        "id": row["id"],
        "model_id": row["model_id"],
        "name": row["name"],
        "start_year": int(row["start_year"]) if row.get("start_year") else None,
    }
    
    # Handle end_year
    end_year = row.get("end_year", "")
    if end_year and end_year.isdigit():
        gen["end_year"] = int(end_year)
    else:
        gen["end_year"] = None  # Current/ongoing
    
    # Optional fields
    if row.get("facelift_year"):
        gen["facelift_year"] = row["facelift_year"]
    if row.get("platform"):
        gen["platform"] = row["platform"]
    
    return gen


def csv_to_variant(row: dict) -> dict:
    """Convert variants CSV row to JSON format."""
    variant = {
        "id": row["id"],
        "generation_id": row["generation_id"],
        "name": row["name"],
        "engine_type": row.get("engine_type", "gasoline"),
    }
    
    # Optional fields
    if row.get("engine_code"):
        variant["engine_code"] = row["engine_code"]
    
    if row.get("displacement_cc"):
        try:
            variant["displacement_cc"] = int(row["displacement_cc"])
        except ValueError:
            pass
    
    if row.get("horsepower"):
        try:
            variant["horsepower"] = int(row["horsepower"])
        except ValueError:
            pass
    
    if row.get("torque_nm"):
        try:
            variant["torque_nm"] = int(row["torque_nm"])
        except ValueError:
            pass
    
    if row.get("transmission"):
        variant["transmission"] = row["transmission"]
    
    if row.get("drive_type"):
        variant["drive_type"] = row["drive_type"]
    
    return variant


def merge_by_id(existing: list, new_items: list) -> list:
    """Merge lists, replacing existing items with same ID."""
    existing_ids = {item["id"]: i for i, item in enumerate(existing)}
    result = list(existing)
    
    for item in new_items:
        if item["id"] in existing_ids:
            # Replace existing
            result[existing_ids[item["id"]]] = item
        else:
            # Add new
            result.append(item)
    
    return result


def main():
    print("Loading CSV files...")
    
    # Load CSV data
    makes_csv = load_csv("makes.csv")
    models_csv = load_csv("models.csv")
    generations_csv = load_csv("generations.csv")
    variants_csv = load_csv("variants.csv")
    
    print(f"  Makes: {len(makes_csv)}")
    print(f"  Models: {len(models_csv)}")
    print(f"  Generations: {len(generations_csv)}")
    print(f"  Variants: {len(variants_csv)}")
    
    # Convert to JSON format
    makes_json = [csv_to_make(row) for row in makes_csv]
    models_json = [csv_to_model(row) for row in models_csv]
    generations_json = [csv_to_generation(row) for row in generations_csv]
    variants_json = [csv_to_variant(row) for row in variants_csv]
    
    # Load existing JSON
    print(f"\nLoading existing {VEHICLES_JSON}...")
    data = load_existing_json()
    
    existing_counts = {
        "makes": len(data.get("makes", [])),
        "models": len(data.get("models", [])),
        "generations": len(data.get("generations", [])),
        "variants": len(data.get("variants", []))
    }
    print(f"  Existing: {existing_counts}")
    
    # Merge data
    print("\nMerging data...")
    data["makes"] = merge_by_id(data.get("makes", []), makes_json)
    data["models"] = merge_by_id(data.get("models", []), models_json)
    data["generations"] = merge_by_id(data.get("generations", []), generations_json)
    data["variants"] = merge_by_id(data.get("variants", []), variants_json)
    
    # Update metadata
    data["version"] = "1.1.0"
    data["last_updated"] = str(date.today())
    
    # Sort for consistency
    data["makes"].sort(key=lambda x: x["name"])
    data["models"].sort(key=lambda x: (x["make_id"], x["name"]))
    data["generations"].sort(key=lambda x: (x["model_id"], x.get("start_year", 0)))
    data["variants"].sort(key=lambda x: (x["generation_id"], x["name"]))
    
    # Write output
    print(f"\nWriting to {VEHICLES_JSON}...")
    os.makedirs(ASSETS_DIR, exist_ok=True)
    
    with open(VEHICLES_JSON, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    # Summary
    final_counts = {
        "makes": len(data["makes"]),
        "models": len(data["models"]),
        "generations": len(data["generations"]),
        "variants": len(data["variants"])
    }
    
    print("\n✅ Merge complete!")
    print(f"   Makes: {existing_counts['makes']} → {final_counts['makes']}")
    print(f"   Models: {existing_counts['models']} → {final_counts['models']}")
    print(f"   Generations: {existing_counts['generations']} → {final_counts['generations']}")
    print(f"   Variants: {existing_counts['variants']} → {final_counts['variants']}")
    
    # Also merge DTC codes if present
    dtc_csv = load_csv("dtc_codes.csv")
    if dtc_csv:
        merge_dtc_codes(dtc_csv)


def merge_dtc_codes(dtc_csv: list[dict]):
    """Merge DTC codes into the existing DTC database."""
    dtc_csv_path = ASSETS_DIR / "dtc_codes.csv"
    
    print(f"\nProcessing {len(dtc_csv)} DTC codes...")
    
    # Define canonical fieldnames for the new enhanced format
    fieldnames = [
        "code", "make_id", "description", "detailed_description", 
        "system", "severity", "common_causes", "symptoms",
        "applicable_models", "applicable_years", "powertrain_type"
    ]
    
    # Read existing DTC codes (handle both old and new formats)
    existing_codes = set()  # (code, make_id) tuples
    existing_rows = []
    
    if dtc_csv_path.exists():
        with open(dtc_csv_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if content:
                f.seek(0)
                reader = csv.DictReader(f)
                for row in reader:
                    # Normalize row to new format
                    normalized = {fn: row.get(fn, "") for fn in fieldnames}
                    existing_rows.append(normalized)
                    existing_codes.add((row.get("code", ""), row.get("make_id", "")))
    
    # Add new codes
    new_codes = 0
    updated_codes = 0
    
    for row in dtc_csv:
        key = (row.get("code", ""), row.get("make_id", ""))
        normalized = {fn: row.get(fn, "") for fn in fieldnames}
        
        if key not in existing_codes:
            existing_rows.append(normalized)
            existing_codes.add(key)
            new_codes += 1
        else:
            # Update existing entry with new data (manufacturer-specific overrides generic)
            for i, existing in enumerate(existing_rows):
                if (existing.get("code"), existing.get("make_id")) == key:
                    existing_rows[i] = normalized
                    updated_codes += 1
                    break
    
    # Sort by code for consistency
    existing_rows.sort(key=lambda x: (x.get("code", ""), x.get("make_id", "")))
    
    # Write merged DTC codes
    with open(dtc_csv_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(existing_rows)
    
    print(f"✅ DTC codes: Added {new_codes} new, updated {updated_codes} (total: {len(existing_rows)})")


if __name__ == "__main__":
    main()
