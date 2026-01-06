"""
Reconvert CSV files to JSON with proper end_year handling
"""

import json
import pandas as pd
from pathlib import Path

# Paths
SCRIPT_DIR = Path(__file__).parent / "scripts" / "vehicle_data_generator"
OUTPUT_DIR = SCRIPT_DIR / "output"
APP_ASSETS_DIR = Path(__file__).parent / "assets" / "data"

def clean_dict(d):
    """Convert NaN to None and ensure proper types, especially for years."""
    cleaned = {}
    for k, v in d.items():
        if pd.isna(v):
            cleaned[k] = None
        elif isinstance(v, float):
            # For year columns, convert to int if it's a valid year
            if k in ['start_year', 'end_year', 'year', 'facelift_year'] and v > 1900:
                cleaned[k] = int(v)
            elif v == int(v):  # Other floats that are whole numbers
                cleaned[k] = int(v)
            else:
                cleaned[k] = v
        else:
            cleaned[k] = v
    return cleaned

# Load CSVs
print("Loading CSV files...")
makes_df = pd.read_csv(OUTPUT_DIR / "makes.csv")
models_df = pd.read_csv(OUTPUT_DIR / "models.csv")
generations_df = pd.read_csv(OUTPUT_DIR / "generations.csv")
variants_df = pd.read_csv(OUTPUT_DIR / "variants.csv")

print(f"CSV loaded - Generations: {len(generations_df)}")

# Check end_year values before conversion
end_years = generations_df['end_year'].dropna()
print(f"Generations with end_year in CSV: {len(end_years)}")
print(f"Sample end_years: {end_years.head(10).tolist()}")

# Convert to lists of dicts with proper cleaning
makes = [clean_dict(row) for row in makes_df.to_dict('records')]
models = [clean_dict(row) for row in models_df.to_dict('records')]
generations = [clean_dict(row) for row in generations_df.to_dict('records')]
variants = [clean_dict(row) for row in variants_df.to_dict('records')]

# Verify end_years after conversion
generations_with_end = [g for g in generations if g.get('end_year') is not None]
print(f"Generations with end_year after conversion: {len(generations_with_end)}")
print(f"Sample: {[(g['name'], g['end_year']) for g in generations_with_end[:10]]}")

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

print(f"\n✅ Converted to {output_path}")
print(f"   Makes: {len(makes)}")
print(f"   Models: {len(models)}")
print(f"   Generations: {len(generations)}")
print(f"   Variants: {len(variants)}")
print(f"   Generations with end_year: {len(generations_with_end)}")
