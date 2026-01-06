import json

with open('assets/data/vehicles.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

model_ids = {m['id'] for m in data['models']}
gen_model_ids = {g['model_id'] for g in data['generations']}
orphaned = model_ids - gen_model_ids

print(f'Models without generations: {len(orphaned)}')
for model in data['models']:
    if model['id'] in orphaned:
        print(f"  - {model['name']} (make: {model['make_id']}, id: {model['id']})")

# Check "Present" issue - count generations by end_year
null_count = sum(1 for g in data['generations'] if g['end_year'] is None)
with_year = sum(1 for g in data['generations'] if g['end_year'] is not None)
print(f'\nGeneration end_year stats:')
print(f'  null (Present): {null_count}')
print(f'  with year: {with_year}')
print(f'  total: {len(data["generations"])}')

# Sample some with years
print('\nSample discontinued generations:')
for gen in data['generations'][:20]:
    if gen['end_year'] is not None:
        model = next(m for m in data['models'] if m['id'] == gen['model_id'])
        print(f"  - {model['name']} {gen['name']}: {gen['start_year']}-{gen['end_year']}")
