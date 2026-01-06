import json

# Load the vehicles data
with open('assets/data/vehicles.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print(f"Original makes count: {len(data['makes'])}")
print(f"Original models count: {len(data['models'])}")

# Fix 1: Remove duplicate Mercedes-Benz entry
# Keep "mercedes-benz" and remove "mercedes"
makes_before = len(data['makes'])
data['makes'] = [make for make in data['makes'] if make['id'] != 'mercedes']
makes_after = len(data['makes'])
print(f"\nRemoved {makes_before - makes_after} duplicate Mercedes make entry")

# Fix 2: Update all models that reference "mercedes" to use "mercedes-benz"
models_updated = 0
for model in data['models']:
    if model.get('make_id') == 'mercedes':
        model['make_id'] = 'mercedes-benz'
        models_updated += 1
        print(f"  Updated model: {model['name']}")

print(f"Updated {models_updated} models to reference mercedes-benz")

# Verify no orphaned models
orphaned = [m for m in data['models'] if m.get('make_id') == 'mercedes']
print(f"\nOrphaned models remaining: {len(orphaned)}")

# Save the fixed data
with open('assets/data/vehicles.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print("\n✓ vehicles.json updated successfully")
print(f"Final makes count: {len(data['makes'])}")
print(f"Final models count: {len(data['models'])}")
