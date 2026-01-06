import json

with open('assets/data/vehicles.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print(f'Total generations: {len(data["generations"])}')
print(f'With end_year: {sum(1 for g in data["generations"] if g.get("end_year") is not None)}')
print(f'Still null: {sum(1 for g in data["generations"] if g.get("end_year") is None)}')

nulls = [g for g in data['generations'] if g.get('end_year') is None]
print(f'\nRemaining {len(nulls)} null end_years:')
for g in nulls[:20]:
    print(f'  - {g["name"]} ({g["start_year"]}) - model: {g["model_id"]}')

# Check if selectors will work - models with generations
model_ids_with_gens = {g['model_id'] for g in data['generations']}
print(f'\nModels with generations: {len(model_ids_with_gens)}/{len(data["models"])}')

# Sample some with proper end_year
print('\nSample generations with end_year:')
with_years = [g for g in data['generations'] if g.get('end_year') is not None]
for g in with_years[:10]:
    print(f'  - {g["name"]}: {g["start_year"]}-{g["end_year"]}')
