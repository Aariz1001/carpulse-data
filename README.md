# CarPulse Vehicle Data Generator

AI-powered tools to generate comprehensive vehicle databases and DTC (Diagnostic Trouble Codes) for automotive applications.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **📱 This is the data generation toolkit for [CarPulse](https://github.com/YOUR_USERNAME/carpulse)** - an OBD-II diagnostic app for iOS and Android.

## 🚀 Quick Start

```bash
# 1. Clone this repo
git clone https://github.com/YOUR_USERNAME/carpulse-data.git
cd carpulse-data

# 2. Install dependencies
pip install -r requirements.txt

# 3. Copy environment template
cp .env.example .env
# Edit .env and add your OpenRouter API key

# 4. Run the GUI
streamlit run gui.py
```

## ⚠️ Cost Warning

This tool uses AI APIs that **cost real money**. Estimated costs:

| Operation | Approximate Cost |
|-----------|------------------|
| Single manufacturer (full data + DTCs) | $0.05 - $0.15 |
| DTC codes only (per manufacturer) | $0.03 - $0.08 |
| Web scrape + AI enrich | $0.01 - $0.03 |
| Fill gaps in 100 codes | ~$0.02 |

**Always monitor your API usage at [OpenRouter Dashboard](https://openrouter.ai/activity)**.

## Features

- 🚗 **Vehicle Database Generation** - Makes, models, generations, variants
- 🔧 **DTC Code Generation** - Manufacturer-specific diagnostic codes
- 🌐 **Web Scraping** - Extract codes from manufacturer websites
- 🤖 **AI Enrichment** - Fill gaps with detailed descriptions, causes, symptoms
- 🌍 **Multi-Market Support** - US, EU, UK, Asia, Australia variants
- ⚡ **Multi-Powertrain** - Petrol, Diesel, Hybrid, PHEV, EV codes

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Create a `.env` file (copy from `.env.example`):
   ```bash
   cp .env.example .env
   ```

3. Add your OpenRouter API key to `.env`:
   ```
   OPENROUTER_API_KEY=sk-or-v1-your-api-key-here
   ```

   Get your key at: https://openrouter.ai/keys

## Quick Start

```bash
# Generate vehicles + DTCs for a manufacturer
python generate_vehicles.py --batch "Toyota" --fetch-dtc

# Scrape DTCs from a website (FREE - no AI)
python scrape_dtc.py --url "https://example.com/codes" --manufacturer honda --prepare

# Enrich scraped codes with AI
python fill_dtc_gaps.py --input scraped_honda_*.csv

# Merge to final JSON
python merge_to_json.py
```

## Usage

### Generate by Manufacturers (5 at a time)
```bash
python generate_vehicles.py --mode manufacturers --batch "Toyota,Honda,Nissan,Mazda,Subaru"
```

### Generate by Country
```bash
python generate_vehicles.py --mode country --country "Germany"
python generate_vehicles.py --mode country --country "Japan"
python generate_vehicles.py --mode country --country "USA"
python generate_vehicles.py --mode country --country "South Korea"
```

### Generate All (Batch by batch)
```bash
python generate_vehicles.py --mode all
```

### Market-Specific Data
Specify a target market to get region-specific variants and specs:
```bash
# US market (no diesels, different trim names)
python generate_vehicles.py --mode manufacturers --batch "BMW,Mercedes-Benz" --market US

# European market (includes diesels, EU specs)
python generate_vehicles.py --mode manufacturers --batch "BMW,Mercedes-Benz" --market EU

# Available markets: Global, US, EU, Asia, UK, Australia
```

### Fetch DTC Codes
Manufacturer-specific DTC codes can also be fetched:
```bash
# Fetch vehicles AND DTC codes
python generate_vehicles.py --mode manufacturers --batch "Toyota,Honda" --fetch-dtc

# Fetch ONLY DTC codes (skip vehicle data)
python generate_vehicles.py --mode manufacturers --batch "BMW,Mercedes-Benz" --dtc-only

# Fetch DTC codes for a whole country's manufacturers
python generate_vehicles.py --mode country --country "Germany" --fetch-dtc
```

The script automatically fetches:
- **General manufacturer codes** (P1xxx, etc.)
- **Hybrid-specific codes** (for Toyota, Honda, Lexus, BMW, etc.)
- **Diesel-specific codes** (for European brands - DPF, EGR, AdBlue codes)
- **EV-specific codes** (for Tesla, NIO, BYD, etc.)

## Output

The script generates/updates these CSV files:
- `output/makes.csv` - Manufacturer data
- `output/models.csv` - Model lines (with market column)
- `output/generations.csv` - Generation/platform codes with years
- `output/variants.csv` - Engine/powertrain variants (with market column)
- `output/dtc_codes.csv` - Manufacturer-specific DTC codes

### DTC Code Structure
Each DTC code includes:
| Field | Description |
|-------|-------------|
| code | The DTC code (e.g., P1234, B1001) |
| make_id | Manufacturer ID |
| description | Short description |
| detailed_description | Full explanation |
| system | Affected system (Engine, Transmission, ABS, etc.) |
| severity | Critical, High, Medium, Low, Info |
| common_causes | JSON array of common causes |
| symptoms | JSON array of symptoms |
| applicable_models | Which models this applies to |
| applicable_years | Year range |
| powertrain_type | All, Gasoline, Diesel, Hybrid, EV |

## Web Scraper for DTC Codes

The `scrape_dtc.py` tool extracts DTC codes from manufacturer-specific websites. This is useful for importing Honda, Toyota, BMW, etc. specific codes from public resources.

### Scraper Usage

```bash
# Scrape from a specific URL
python scrape_dtc.py --url "https://hondacodes.wordpress.com/honda-fault-codes/" --manufacturer honda

# Use known sources (if configured in the script)
python scrape_dtc.py --manufacturer honda

# Follow links on the page to find more codes
python scrape_dtc.py --manufacturer honda --follow-links

# Also prepare the file for the gap filler
python scrape_dtc.py --manufacturer honda --prepare

# List known sources
python scrape_dtc.py --list-sources
```

### Full Workflow: Scrape → Enrich → Merge

```bash
# Step 1: Scrape codes from a website (NO AI, FREE)
python scrape_dtc.py --url "https://example.com/codes" --manufacturer toyota

# Step 2: Import and enrich with AI (COSTS API)
python fill_dtc_gaps.py --input output/scraped/scraped_toyota_dtc_<timestamp>.csv

# Or import without AI enrichment (FREE)
python fill_dtc_gaps.py --input output/scraped/scraped_toyota_dtc_<timestamp>.csv --merge-only

# Step 3: Merge into app data
python merge_to_json.py
```

### What the Scraper Extracts

The scraper uses regex patterns to find DTC codes:
- **P-codes**: P0xxx, P1xxx, P2xxx, P3xxx (Powertrain)
- **B-codes**: B0xxx, B1xxx, B2xxx, B3xxx (Body)
- **C-codes**: C0xxx, C1xxx, C2xxx, C3xxx (Chassis)
- **U-codes**: U0xxx, U1xxx, U2xxx, U3xxx (Network)

Output CSV includes:
- `code`: The DTC code (e.g., P0420)
- `description`: The code description
- `source_url`: Where it was scraped from
- `manufacturer`: The manufacturer name
- `scraped_at`: Timestamp

### Adding New Sources

Edit `KNOWN_SOURCES` in `scrape_dtc.py` to add manufacturer-specific websites:

```python
KNOWN_SOURCES = {
    "honda": [
        "https://hondacodes.wordpress.com/honda-fault-codes/",
    ],
    "toyota": [
        # Add Toyota URLs here
    ],
    # ... add more manufacturers
}
```

## Cost Tracking

The script provides detailed cost tracking at the end of every run:

```
======================================================================
💰 COST & USAGE SUMMARY
======================================================================

📊 API CALLS
   Total Calls:      25
   Successful:       24
   Failed:           1
   Web Searches:     24

   By Category:
      Make            5 calls
      Models          5 calls
      Generations    10 calls
      Variants        4 calls

📝 TOKEN USAGE
   Prompt Tokens:     45,230
   Completion Tokens: 12,450
   Total Tokens:      57,680
   Cached Tokens:     5,000 (saved cost)

💵 COST BREAKDOWN
   Model Usage:       $0.002845
   Web Search (~):    $0.096000 (24 searches @ $0.004/search)
   ─────────────────────────────────
   TOTAL COST:        $0.098845

   By Category:
      Make         $0.000234
      Models       $0.000567
      Generations  $0.001200
      Variants     $0.000844

📈 PROJECTIONS
   Avg Cost/Call:     $0.003954
   Est. 100 Calls:    $0.3954
   Est. 1000 Calls:   $3.9537

======================================================================
💡 Tip: Credits shown are OpenRouter credits (1M credits = $1 USD)
   Raw credits used: 2,845.00
======================================================================
```

### Cost Breakdown
- **Model Usage**: Cost charged by the AI model (varies by model)
- **Web Search**: ~$4 per 1000 searches ($0.004 per search)
- **Cached Tokens**: Tokens served from cache (reduces cost)

## Notes

- Only generates data for models from 2000-present
- Uses OpenRouter web search for accurate, up-to-date information
- Rate limited to avoid API throttling
- Incremental - won't duplicate existing entries
- Cost tracking even works if you interrupt with Ctrl+C

## API Pricing

Web search adds ~$4 per 1000 searches on top of model costs. See:
- https://openrouter.ai/docs/guides/features/plugins/web-search#pricing
- https://openrouter.ai/docs/guides/guides/usage-accounting

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

Ways to help:
- 🔧 Add DTC codes for missing manufacturers
- 🌍 Add regional variants (UK, Australia, etc.)
- 📝 Fix incorrect data
- 🔗 Share working scraper URLs

### Contributor Workflow

1. Fork this repository
2. Run `streamlit run gui.py` to edit data locally
3. Make changes to the CSV files in `output/`
4. Submit a Pull Request with your changes
5. Maintainers will review, merge, and encrypt for the app

> **Note**: Contributors work with raw CSV data. Encryption is handled by maintainers before shipping to the app.

## 🔐 Data Encryption (For App Developers)

If you're using this data in your own app, you can encrypt it to prevent unauthorized use:

```bash
# Create your private keys file (see crypto_keys_private.py.example)
# Then encrypt all data
python encrypt_data.py --verify

# Copy encrypted files to your Flutter assets
python encrypt_data.py --assets /path/to/your/flutter/assets/data/encrypted
```

See `crypto_utils.py` for the encryption implementation. You'll need to:
1. Create `crypto_keys_private.py` with your own secret keys
2. Implement matching decryption in your app
3. Never commit `crypto_keys_private.py` to version control

## License

This project is licensed under the MIT License - see [LICENSE](LICENSE) for details.

## Related Projects

- **[CarPulse App](https://github.com/YOUR_USERNAME/carpulse)** - The Flutter OBD-II diagnostic app that uses this data
