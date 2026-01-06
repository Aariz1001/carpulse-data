"""
Convert generated CSV files to the vehicles.json format used by the app.
"""

import json
import pandas as pd
from pathlib import Path

# Paths
SCRIPT_DIR = Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR / "output"
APP_ASSETS_DIR = SCRIPT_DIR.parent.parent / "assets" / "data"


def convert_to_app_json():
    """Convert CSV files to the app's vehicles.json format."""
    
    # Check if CSV files exist
    required_files = ["makes.csv", "models.csv", "generations.csv", "variants.csv"]
    for filename in required_files:
        if not (OUTPUT_DIR / filename).exists():
            print(f"❌ Missing file: {OUTPUT_DIR / filename}")
            print("   Run generate_vehicles.py first!")
            return
    
    # Load CSVs
    makes_df = pd.read_csv(OUTPUT_DIR / "makes.csv")
    models_df = pd.read_csv(OUTPUT_DIR / "models.csv")
    generations_df = pd.read_csv(OUTPUT_DIR / "generations.csv")
    variants_df = pd.read_csv(OUTPUT_DIR / "variants.csv")
    
    # Convert to lists of dicts, handling NaN values
    def clean_dict(d):
        """Convert NaN to None and ensure proper types."""
        cleaned = {}
        for k, v in d.items():
            if pd.isna(v):
                cleaned[k] = None
            elif isinstance(v, float) and v == int(v):
                cleaned[k] = int(v)
            else:
                cleaned[k] = v
        return cleaned
    
    makes = [clean_dict(row) for row in makes_df.to_dict('records')]
    models = [clean_dict(row) for row in models_df.to_dict('records')]
    generations = [clean_dict(row) for row in generations_df.to_dict('records')]
    variants = [clean_dict(row) for row in variants_df.to_dict('records')]
    
    # Build the JSON structure
    output = {
        "version": "1.0.0",
        "last_updated": pd.Timestamp.now().strftime("%Y-%m-%d"),
        "makes": makes,
        "models": models,
        "generations": generations,
        "variants": variants
    }
    
    # Save to app assets
    output_path = APP_ASSETS_DIR / "vehicles.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Converted to {output_path}")
    print(f"   Makes: {len(makes)}")
    print(f"   Models: {len(models)}")
    print(f"   Generations: {len(generations)}")
    print(f"   Variants: {len(variants)}")


def merge_with_existing():
    """Merge new CSV data with existing vehicles.json."""
    
    existing_path = APP_ASSETS_DIR / "vehicles.json"
    
    if not existing_path.exists():
        print("No existing vehicles.json found, creating new one...")
        convert_to_app_json()
        return
    
    # Load existing
    with open(existing_path, 'r', encoding='utf-8') as f:
        existing = json.load(f)
    
    # Load new CSVs
    makes_df = pd.read_csv(OUTPUT_DIR / "makes.csv")
    models_df = pd.read_csv(OUTPUT_DIR / "models.csv")
    generations_df = pd.read_csv(OUTPUT_DIR / "generations.csv")
    variants_df = pd.read_csv(OUTPUT_DIR / "variants.csv")
    
    def clean_dict(d):
        cleaned = {}
        for k, v in d.items():
            if pd.isna(v):
                cleaned[k] = None
            elif isinstance(v, float) and v == int(v):
                cleaned[k] = int(v)
            else:
                cleaned[k] = v
        return cleaned
    
    # Merge function - add new items that don't exist
    def merge_lists(existing_list, new_list, key="id"):
        existing_ids = {item[key] for item in existing_list}
        for item in new_list:
            if item[key] not in existing_ids:
                existing_list.append(item)
        return existing_list
    
    new_makes = [clean_dict(row) for row in makes_df.to_dict('records')]
    new_models = [clean_dict(row) for row in models_df.to_dict('records')]
    new_generations = [clean_dict(row) for row in generations_df.to_dict('records')]
    new_variants = [clean_dict(row) for row in variants_df.to_dict('records')]
    
    existing["makes"] = merge_lists(existing.get("makes", []), new_makes)
    existing["models"] = merge_lists(existing.get("models", []), new_models)
    existing["generations"] = merge_lists(existing.get("generations", []), new_generations)
    existing["variants"] = merge_lists(existing.get("variants", []), new_variants)
    existing["last_updated"] = pd.Timestamp.now().strftime("%Y-%m-%d")
    
    # Save
    with open(existing_path, 'w', encoding='utf-8') as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Merged into {existing_path}")
    print(f"   Total Makes: {len(existing['makes'])}")
    print(f"   Total Models: {len(existing['models'])}")
    print(f"   Total Generations: {len(existing['generations'])}")
    print(f"   Total Variants: {len(existing['variants'])}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--merge":
        merge_with_existing()
    else:
        convert_to_app_json()
