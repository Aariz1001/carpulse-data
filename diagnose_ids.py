import json

with open('assets/data/vehicles.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print(f'Total makes: {len(data["makes"])}')
print(f'Total models: {len(data["models"])}')
print(f'Total generations: {len(data["generations"])}')
print(f'\nBrands: {[m["name"] for m in data["makes"]]}')

# Check mismatches
model_ids = {m['id'] for m in data['models']}
gen_model_ids = {g['model_id'] for g in data['generations']}
orphaned_gens = gen_model_ids - model_ids
orphaned_models = model_ids - gen_model_ids

print(f'\nGenerations referencing missing models: {len(orphaned_gens)}')
if orphaned_gens:
    print('Sample orphaned gen model_ids:', list(orphaned_gens)[:10])

print(f'\nModels without generations: {len(orphaned_models)}')
if orphaned_models:
    print('Sample models without gens:', list(orphaned_models)[:10])
