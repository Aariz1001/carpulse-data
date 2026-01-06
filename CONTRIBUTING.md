# Contributing to CarPulse Vehicle Data Generator

Thank you for your interest in contributing! This project aims to build a comprehensive database of vehicle information and DTC (Diagnostic Trouble Codes) for the automotive community.

## Ways to Contribute

### 1. 🔧 Add DTC Codes via Web Scraping

If you find a manufacturer's DTC code database online:

```bash
# Scrape codes from a website
python scrape_dtc.py --url "https://example.com/dtc-codes" --manufacturer "BrandName" --prepare

# Import and enrich with AI
python fill_dtc_gaps.py --input scraped_brandname_*.csv --enrich

# Merge to main database
python merge_to_json.py
```

### 2. 🚗 Add New Manufacturers

Run the generator for manufacturers not yet in the database:

```bash
python generate_vehicles.py --batch "Manufacturer1,Manufacturer2" --fetch-dtc
```

### 3. 📝 Submit Manual Corrections

If you spot incorrect DTC descriptions or vehicle data:

1. Edit the relevant CSV file in `output/`
2. Run `python merge_to_json.py` to validate
3. Submit a PR with your changes

### 4. 🌍 Add Regional Variants

Help expand market-specific data:

```bash
python generate_vehicles.py --batch "Toyota" --market "Australia" --fetch-dtc
```

## Getting Started

### Prerequisites

- Python 3.8+
- OpenRouter API key (for AI features)

### Setup

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/carpulse-vehicle-data.git
cd carpulse-vehicle-data

# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env and add your OPENROUTER_API_KEY
```

## API Costs

⚠️ **Important**: AI-powered generation uses the OpenRouter API which has costs:

| Operation | Approximate Cost |
|-----------|------------------|
| Single manufacturer (full) | $0.05 - $0.15 |
| DTC codes only (per make) | $0.03 - $0.08 |
| Web scrape + enrich | $0.01 - $0.03 |

The default model (`gemini-2.5-flash-lite`) is chosen for cost efficiency.

## Code Structure

```
vehicle_data_generator/
├── generate_vehicles.py    # Main AI generator for makes/models/variants/DTCs
├── fill_dtc_gaps.py        # AI enrichment for DTC codes
├── scrape_dtc.py           # Web scraper for DTC databases
├── merge_to_json.py        # Merge CSVs to final JSON
├── output/                 # Generated CSV files
│   ├── makes.csv
│   ├── models.csv
│   ├── generations.csv
│   ├── variants.csv
│   └── dtc_codes.csv
└── vehicles.json           # Final merged database
```

## Submission Guidelines

### For DTC Contributions

1. Ensure codes follow the format: `[PBCU][0-9][0-9A-F]{3}` (e.g., P0301, U0100)
2. Include at minimum: `code`, `make_id`, `description`
3. AI enrichment will fill: `detailed_description`, `common_causes`, `symptoms`, `severity`

### For Vehicle Data

1. Use consistent naming (e.g., "BMW" not "Bmw")
2. Include chassis codes where known (e.g., "E90", "W205")
3. Specify market if regional (UK, US, EU, Asia, Australia)

### Pull Request Process

1. Fork the repository
2. Create a feature branch (`git checkout -b add-manufacturer-xyz`)
3. Make your changes
4. Run `python merge_to_json.py` to validate
5. Commit with descriptive message
6. Push and create a Pull Request

## Data Quality Standards

- ✅ Use official manufacturer terminology where possible
- ✅ Include year ranges for DTC applicability
- ✅ Specify powertrain type (Petrol/Diesel/Hybrid/PHEV/EV)
- ✅ Provide sources for manually added codes
- ❌ Don't include speculative or unverified codes
- ❌ Don't copy proprietary databases verbatim

## Questions?

Open an issue for:
- Help with scraping a specific manufacturer's site
- Clarification on data formats
- Feature requests for the generator tools

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
