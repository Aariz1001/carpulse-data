"""
Fix end_year values in vehicles.json using CSV data
WITHOUT breaking the model_id relationships
"""

import json
import pandas as pd
from pathlib import Path

# Paths
CSV_PATH = Path("scripts/vehicle_data_generator/output/generations.csv")
JSON_PATH = Path("assets/data/vehicles.json")

# Load CSV with correct end_year values
csv_df = pd.read_csv(CSV_PATH)
print(f"Loaded CSV: {len(csv_df)} generations")
print(f"CSV generations with end_year: {csv_df['end_year'].notna().sum()}")

# Load existing JSON with correct model_id relationships
with open(JSON_PATH, 'r', encoding='utf-8') as f:
    data = json.load(f)

print(f"\nJSON before: {len(data['generations'])} generations")
print(f"JSON with end_year before: {sum(1 for g in data['generations'] if g.get('end_year') is not None)}")

# Match CSV to JSON generations by model_id, name, and start_year
# Build lookup dictionary from CSV
csv_lookup = {}
for _, row in csv_df.iterrows():
    if pd.notna(row['end_year']):
        # Try multiple key combinations for matching
        keys = [
            (row['model_id'], row['name'], row['start_year']),
            (row['model_id'], row['start_year']),
            (row['name'], row['start_year'])
        ]
        for key in keys:
            csv_lookup[key] = int(row['end_year'])

# Update JSON generations
updated_count = 0
for gen in data['generations']:
    if gen.get('end_year') is None:  # Only update null end_years
        # Try to find match in CSV
        keys_to_try = [
            (gen['model_id'], gen['name'], gen['start_year']),
            (gen['model_id'], gen['start_year']),
            (gen['name'], gen['start_year'])
        ]
        
        for key in keys_to_try:
            if key in csv_lookup:
                old_end = gen.get('end_year')
                gen['end_year'] = csv_lookup[key]
                updated_count += 1
                print(f"  Updated: {gen['name']} ({gen['start_year']}) -> {gen['end_year']}")
                break

print(f"\n✅ Updated {updated_count} generations with end_year values")
print(f"JSON with end_year after: {sum(1 for g in data['generations'] if g.get('end_year') is not None)}")

# Save updated JSON
with open(JSON_PATH, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print(f"\n✅ Saved to {JSON_PATH}")
