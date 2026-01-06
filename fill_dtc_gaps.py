"""
DTC Code Gap Filler

This script analyzes existing DTC codes and fills in missing codes for manufacturers.
Uses OpenRouter API with a configurable model optimized for factual technical data.

Usage:
    python fill_dtc_gaps.py --manufacturer toyota     # Fill gaps for one manufacturer
    python fill_dtc_gaps.py --country Japan           # Fill gaps for all Japanese makes
    python fill_dtc_gaps.py --all                     # Fill all gaps across all manufacturers
    python fill_dtc_gaps.py --analyze                 # Just show analysis, don't fill
    python fill_dtc_gaps.py --code-range P0xxx        # Fill specific code range

Environment Variables:
    OPENROUTER_API_KEY      - Required API key
    DTC_FILLER_MODEL        - Model to use (default: google/gemini-2.0-flash-001)
"""

import os
import sys
import json
import argparse
import requests
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Set, Tuple
from dotenv import load_dotenv
from dataclasses import dataclass, field
import re
import time

# Load environment variables
load_dotenv()

# Configuration
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
DTC_FILLER_MODEL = os.getenv("DTC_FILLER_MODEL", "google/gemini-2.0-flash-001")
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Paths
SCRIPT_DIR = Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR / "output"
ASSETS_DIR = SCRIPT_DIR.parent.parent / "assets" / "data"
DTC_REFERENCE_DIR = SCRIPT_DIR.parent.parent / "DTC_codes_list"

# Standard OBD-II reference codes (loaded from DTC_codes_list)

# DTC Code Categories
DTC_CATEGORIES = {
    "P0": "Generic Powertrain (OBD-II Standard)",
    "P1": "Manufacturer-Specific Powertrain",
    "P2": "Generic Powertrain (ISO/SAE Reserved)",
    "P3": "Generic/Manufacturer Powertrain",
    "B0": "Generic Body",
    "B1": "Manufacturer-Specific Body", 
    "B2": "Manufacturer-Specific Body",
    "B3": "Generic Body (ISO/SAE Reserved)",
    "C0": "Generic Chassis",
    "C1": "Manufacturer-Specific Chassis",
    "C2": "Manufacturer-Specific Chassis",
    "C3": "Generic Chassis (ISO/SAE Reserved)",
    "U0": "Generic Network Communication",
    "U1": "Manufacturer-Specific Network",
    "U2": "Manufacturer-Specific Network",
    "U3": "Generic Network (ISO/SAE Reserved)",
}

# Manufacturer-specific keywords for identifying codes
# These are technology/system names unique to each manufacturer
MANUFACTURER_KEYWORDS = {
    "honda": [
        "vtec", "vvt", "i-vtec", "vtc", "ima", "i-mmd", "e:hev", "vsa", "cmbs", "lkas",
        "sh-awd", "honda", "acura", "clarity", "insight", "accord", "civic", "cr-v",
        "earth dreams", "dpf regeneration", "idling stop"
    ],
    "toyota": [
        "vvt-i", "vvt-ie", "d-4s", "d-4st", "tss", "toyota", "lexus", "prius", "hybrid synergy",
        "ths", "ths ii", "ecvt", "e-cvt", "camry", "corolla", "rav4", "highlander",
        "smart key", "star safety", "entune"
    ],
    "bmw": [
        "vanos", "valvetronic", "dsc", "dde", "dme", "ihk", "ihka", "cas", "ews",
        "bmw", "mini", "rolls-royce", "efficient dynamics", "xdrive", "idrive",
        "comfort access", "servotronic", "active steering"
    ],
    "mercedes-benz": [
        "mercedes", "benz", "amg", "4matic", "airmatic", "abc", "me-sfi", "cdi",
        "bluetec", "eq boost", "eq power", "distronic", "parktronic", "mbux",
        "pre-safe", "attention assist", "active brake assist"
    ],
    "volkswagen": [
        "tsi", "tdi", "tfsi", "fsi", "dsg", "s-tronic", "haldex", "4motion", "vw",
        "volkswagen", "vag", "audi", "seat", "skoda", "golf", "passat", "tiguan",
        "adblue", "scr", "dpf", "climatronic", "discover"
    ],
    "audi": [
        "audi", "tfsi", "tdi", "fsi", "s-tronic", "quattro", "mmi", "virtual cockpit",
        "matrix led", "pre sense", "side assist", "adaptive cruise", "a3", "a4", "a6", "q5", "q7"
    ],
    "ford": [
        "ford", "lincoln", "ecoboost", "powershift", "selectshift", "sync",
        "myford", "adaptive cruise", "blis", "cross traffic", "focus", "fiesta",
        "mondeo", "kuga", "puma", "mustang", "mach-e"
    ],
    "nissan": [
        "nissan", "infiniti", "cvt", "xtronic", "e-power", "propilot", "nissan connect",
        "intelligent key", "around view", "juke", "qashqai", "leaf", "ariya",
        "vq", "vr", "qr", "mr"
    ],
    "mazda": [
        "mazda", "skyactiv", "skyactiv-x", "skyactiv-g", "skyactiv-d", "i-activ",
        "i-activsense", "i-stop", "g-vectoring", "cx-5", "cx-30", "mx-5", "mazda3",
        "kodo", "zoom-zoom"
    ],
    "hyundai": [
        "hyundai", "kia", "genesis", "gdi", "t-gdi", "cvvt", "cvvd", "htrac",
        "blue link", "smart cruise", "blind spot", "ioniq", "kona", "tucson",
        "santa fe", "smartstream"
    ],
    "kia": [
        "kia", "hyundai", "gdi", "t-gdi", "cvvt", "sportage", "sorento", "niro",
        "ev6", "uvo", "drive wise"
    ],
    "volvo": [
        "volvo", "polestar", "drive-e", "sensus", "pilot assist", "city safety",
        "intellisafe", "xc40", "xc60", "xc90", "s60", "v60", "recharge"
    ],
    "peugeot": [
        "peugeot", "citroen", "ds", "psa", "hdi", "thp", "puretech", "e-hdi",
        "blue hdi", "eat6", "eat8", "i-cockpit", "grip control", "208", "308", "3008", "5008"
    ],
    "vauxhall": [
        "vauxhall", "opel", "ecotec", "cdti", "intellilink", "onstar", "flexride",
        "astra", "corsa", "insignia", "mokka", "grandland"
    ],
}

# Manufacturer-specific code prefixes (where known)
# Some manufacturers use specific P1xxx ranges
MANUFACTURER_CODE_RANGES = {
    "honda": ["P15", "P16", "P17"],  # Honda commonly uses P15xx-P17xx
    "toyota": ["P13", "P14"],  # Toyota commonly uses P13xx-P14xx
    "ford": ["P12", "P18", "P19"],  # Ford commonly uses P12xx, P18xx-P19xx
    "gm": ["P16", "P17"],  # GM/Vauxhall uses P16xx-P17xx
}

# Manufacturer groups by country
MANUFACTURERS_BY_COUNTRY = {
    "Germany": ["mercedes-benz", "bmw", "audi", "volkswagen", "porsche"],
    "Japan": ["toyota", "honda", "nissan", "mazda", "subaru", "mitsubishi"],
    "USA": ["ford", "chevrolet", "gmc", "dodge", "tesla"],
    "South Korea": ["hyundai", "kia", "genesis"],
    "UK": ["vauxhall", "jaguar", "land-rover", "mini"],
    "France": ["peugeot", "renault", "citroen"],
    "Sweden": ["volvo", "polestar"],
    "Italy": ["fiat", "alfa-romeo", "ferrari"],
}

# Recommended code counts by manufacturer type
RECOMMENDED_CODE_COUNTS = {
    "premium": 80,    # BMW, Mercedes, Audi
    "standard": 60,   # Toyota, Honda, Ford
    "compact": 40,    # Smaller manufacturers
}

# Powertrain types with UK terminology
POWERTRAIN_TYPES = [
    "Petrol",           # Standard petrol/gasoline engine
    "Diesel",           # Standard diesel engine
    "Petrol Hybrid",    # HEV - Petrol + electric motor (self-charging)
    "Diesel Hybrid",    # Diesel + electric motor (rare but exists)
    "Plug-in Hybrid",   # PHEV - Can charge from mains
    "Electric",         # BEV - Battery only
    "All",              # Generic codes applicable to all
]

# Manufacturer powertrain profiles (what each make commonly offers)
MANUFACTURER_POWERTRAINS = {
    # German premium - all types
    "bmw": ["Petrol", "Diesel", "Petrol Hybrid", "Plug-in Hybrid", "Electric"],
    "mercedes-benz": ["Petrol", "Diesel", "Diesel Hybrid", "Petrol Hybrid", "Plug-in Hybrid", "Electric"],
    "audi": ["Petrol", "Diesel", "Petrol Hybrid", "Plug-in Hybrid", "Electric"],
    "volkswagen": ["Petrol", "Diesel", "Petrol Hybrid", "Plug-in Hybrid", "Electric"],
    "porsche": ["Petrol", "Petrol Hybrid", "Plug-in Hybrid", "Electric"],
    
    # Japanese - strong hybrid focus
    "toyota": ["Petrol", "Diesel", "Petrol Hybrid", "Plug-in Hybrid", "Electric"],
    "honda": ["Petrol", "Diesel", "Petrol Hybrid", "Plug-in Hybrid", "Electric"],
    "nissan": ["Petrol", "Diesel", "Petrol Hybrid", "Electric"],
    "mazda": ["Petrol", "Diesel", "Petrol Hybrid"],
    
    # Korean - EV leaders
    "hyundai": ["Petrol", "Diesel", "Petrol Hybrid", "Plug-in Hybrid", "Electric"],
    "kia": ["Petrol", "Diesel", "Petrol Hybrid", "Plug-in Hybrid", "Electric"],
    "genesis": ["Petrol", "Petrol Hybrid", "Electric"],
    
    # UK brands
    "vauxhall": ["Petrol", "Diesel", "Petrol Hybrid", "Plug-in Hybrid", "Electric"],
    "jaguar": ["Petrol", "Diesel", "Petrol Hybrid", "Plug-in Hybrid", "Electric"],
    "land-rover": ["Petrol", "Diesel", "Diesel Hybrid", "Plug-in Hybrid"],
    "mini": ["Petrol", "Diesel", "Electric"],
    
    # French - diesel strong, EV growing
    "peugeot": ["Petrol", "Diesel", "Petrol Hybrid", "Plug-in Hybrid", "Electric"],
    "renault": ["Petrol", "Diesel", "Petrol Hybrid", "Electric"],
    "citroen": ["Petrol", "Diesel", "Petrol Hybrid", "Plug-in Hybrid", "Electric"],
    
    # Swedish - safety + electrification
    "volvo": ["Petrol", "Diesel", "Petrol Hybrid", "Plug-in Hybrid", "Electric"],
    "polestar": ["Plug-in Hybrid", "Electric"],
    
    # American
    "ford": ["Petrol", "Diesel", "Petrol Hybrid", "Plug-in Hybrid", "Electric"],
    "tesla": ["Electric"],
    
    # Default for unknown manufacturers
    "default": ["Petrol", "Diesel", "All"],
}


@dataclass
class UsageStats:
    """Track API usage and costs with detailed breakdown."""
    # Native token counts (actual billing)
    native_prompt_tokens: int = 0
    native_completion_tokens: int = 0
    native_cached_tokens: int = 0
    native_reasoning_tokens: int = 0
    
    # Actual cost in USD from generation API
    total_cost_usd: float = 0.0
    
    # Call tracking
    api_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    estimated_calls: int = 0  # Calls where we used fallback estimation
    
    # Generation IDs for tracking
    generation_ids: list = field(default_factory=list)
    
    # Per-operation tracking
    calls_by_operation: dict = field(default_factory=lambda: {
        'generate': 0, 'analyze': 0
    })
    cost_by_operation: dict = field(default_factory=lambda: {
        'generate': 0.0, 'analyze': 0.0
    })
    
    # Per-manufacturer tracking
    codes_by_manufacturer: dict = field(default_factory=dict)
    cost_by_manufacturer: dict = field(default_factory=dict)
    
    # Code tracking
    codes_added: int = 0
    codes_updated: int = 0
    
    def add_generation_stats(self, gen_stats: dict, operation: str = 'generate', manufacturer: str = None):
        """Add stats from the generation API response (accurate cost tracking)."""
        if not gen_stats:
            return
        
        self.api_calls += 1
        self.successful_calls += 1
        
        # Native token counts (what you're actually billed for)
        self.native_prompt_tokens += gen_stats.get('native_tokens_prompt') or 0
        self.native_completion_tokens += gen_stats.get('native_tokens_completion') or 0
        self.native_cached_tokens += gen_stats.get('native_tokens_cached') or 0
        self.native_reasoning_tokens += gen_stats.get('native_tokens_reasoning') or 0
        
        # Actual cost in USD
        cost = gen_stats.get('total_cost') or 0
        self.total_cost_usd += cost
        
        # Track generation ID
        gen_id = gen_stats.get('id')
        if gen_id:
            self.generation_ids.append(gen_id)
        
        # Track by operation
        if operation in self.calls_by_operation:
            self.calls_by_operation[operation] += 1
            self.cost_by_operation[operation] += cost
        
        # Track by manufacturer
        if manufacturer:
            self.codes_by_manufacturer[manufacturer] = self.codes_by_manufacturer.get(manufacturer, 0)
            self.cost_by_manufacturer[manufacturer] = self.cost_by_manufacturer.get(manufacturer, 0) + cost
    
    def add_usage_fallback(self, usage_data: dict, operation: str = 'generate', manufacturer: str = None):
        """Fallback: Add usage from response when generation API is unavailable."""
        if not usage_data:
            return
        
        self.api_calls += 1
        self.successful_calls += 1
        self.estimated_calls += 1
        
        # These are normalized tokens (GPT-4o tokenizer), not native
        prompt_tokens = usage_data.get('prompt_tokens') or 0
        completion_tokens = usage_data.get('completion_tokens') or 0
        
        self.native_prompt_tokens += prompt_tokens
        self.native_completion_tokens += completion_tokens
        
        # Estimate cost based on model pricing
        # Gemini Flash: ~$0.075/1M input, ~$0.30/1M output
        # DeepSeek: ~$0.14/1M input, ~$0.28/1M output
        # Claude Sonnet: ~$3/1M input, ~$15/1M output
        estimated_cost = (prompt_tokens * 0.15 / 1_000_000) + (completion_tokens * 0.60 / 1_000_000)
        self.total_cost_usd += estimated_cost
        
        # Track by operation
        if operation in self.calls_by_operation:
            self.calls_by_operation[operation] += 1
            self.cost_by_operation[operation] += estimated_cost
        
        # Track by manufacturer
        if manufacturer:
            self.cost_by_manufacturer[manufacturer] = self.cost_by_manufacturer.get(manufacturer, 0) + estimated_cost
    
    def add_failed_call(self):
        """Track a failed API call."""
        self.api_calls += 1
        self.failed_calls += 1
    
    def add_codes(self, manufacturer: str, count: int):
        """Track codes added for a manufacturer."""
        self.codes_added += count
        self.codes_by_manufacturer[manufacturer] = self.codes_by_manufacturer.get(manufacturer, 0) + count
    
    def print_summary(self):
        """Print a detailed cost and usage summary."""
        print("\n" + "="*70)
        print("💰 DTC GAP FILLER - COST & USAGE SUMMARY")
        print("="*70)
        
        # API Calls
        print("\n📊 API CALLS")
        print(f"   Total Calls:      {self.api_calls}")
        print(f"   Successful:       {self.successful_calls}")
        print(f"   Failed:           {self.failed_calls}")
        if self.estimated_calls > 0:
            print(f"   Estimated Cost:   {self.estimated_calls} (generation API unavailable)")
        
        # Calls by operation
        if any(c > 0 for c in self.calls_by_operation.values()):
            print("\n   By Operation:")
            for op, count in self.calls_by_operation.items():
                if count > 0:
                    cost = self.cost_by_operation.get(op, 0)
                    print(f"      {op.capitalize():12} {count:5} calls  ${cost:.6f}")
        
        # Native Token Usage (actual billing)
        print("\n📝 NATIVE TOKEN USAGE (Actual Billing)")
        total_native = self.native_prompt_tokens + self.native_completion_tokens
        print(f"   Prompt Tokens:     {self.native_prompt_tokens:,}")
        print(f"   Completion Tokens: {self.native_completion_tokens:,}")
        print(f"   Total Tokens:      {total_native:,}")
        if self.native_cached_tokens > 0:
            print(f"   Cached Tokens:     {self.native_cached_tokens:,} (reduced cost)")
        if self.native_reasoning_tokens > 0:
            print(f"   Reasoning Tokens:  {self.native_reasoning_tokens:,}")
        
        # Cost Breakdown
        print("\n💵 ACTUAL COST (from OpenRouter)")
        print(f"   ─────────────────────────────")
        print(f"   TOTAL COST:        ${self.total_cost_usd:.6f}")
        
        # Cost by manufacturer
        if self.cost_by_manufacturer:
            print("\n   By Manufacturer:")
            sorted_makes = sorted(self.cost_by_manufacturer.items(), key=lambda x: -x[1])
            for make, cost in sorted_makes:
                codes = self.codes_by_manufacturer.get(make, 0)
                print(f"      {make:15} ${cost:.6f}  ({codes} codes)")
        
        # DTC Code Stats
        print("\n📋 DTC CODES GENERATED")
        print(f"   New Codes Added:   {self.codes_added}")
        print(f"   Codes Updated:     {self.codes_updated}")
        
        if self.codes_by_manufacturer:
            print("\n   By Manufacturer:")
            sorted_makes = sorted(self.codes_by_manufacturer.items(), key=lambda x: -x[1])
            for make, count in sorted_makes:
                if count > 0:
                    print(f"      {make:15} +{count} codes")
        
        # Projections
        if self.api_calls > 0:
            avg_cost = self.total_cost_usd / self.api_calls
            print("\n📈 PROJECTIONS")
            print(f"   Avg Cost/Call:     ${avg_cost:.6f}")
            print(f"   Est. 100 Calls:    ${avg_cost * 100:.4f}")
            print(f"   Est. 1000 Calls:   ${avg_cost * 1000:.2f}")
        
        print("\n" + "="*70)
        if self.estimated_calls > 0:
            print(f"⚠️  Note: {self.estimated_calls} calls used estimated costs (generation API unavailable)")
            print("   Actual billing may differ. Check your OpenRouter dashboard for exact costs.")
        print("="*70)


# Global stats tracker
stats = UsageStats()

# Global reference codes (loaded once)
REFERENCE_CODES: Dict[str, str] = {}


def load_reference_codes() -> Dict[str, str]:
    """Load the standard OBD-II reference codes from DTC_codes_list folder."""
    global REFERENCE_CODES
    
    if REFERENCE_CODES:  # Already loaded
        return REFERENCE_CODES
    
    csv_path = DTC_REFERENCE_DIR / "obd-trouble-codes.csv"
    json_path = DTC_REFERENCE_DIR / "obd-trouble-codes.json"
    
    if csv_path.exists():
        try:
            # CSV format: "code","description" (no header)
            df = pd.read_csv(csv_path, header=None, names=['code', 'description'])
            REFERENCE_CODES = dict(zip(df['code'].str.upper(), df['description']))
            print(f"📚 Loaded {len(REFERENCE_CODES):,} standard OBD-II reference codes")
        except Exception as e:
            print(f"⚠️  Could not load reference CSV: {e}")
    elif json_path.exists():
        try:
            with open(json_path, 'r') as f:
                data = json.load(f)
                if isinstance(data, list):
                    for item in data:
                        if 'code' in item and 'description' in item:
                            REFERENCE_CODES[item['code'].upper()] = item['description']
                elif isinstance(data, dict):
                    REFERENCE_CODES = {k.upper(): v for k, v in data.items()}
            print(f"📚 Loaded {len(REFERENCE_CODES):,} standard OBD-II reference codes")
        except Exception as e:
            print(f"⚠️  Could not load reference JSON: {e}")
    else:
        print(f"⚠️  No reference codes found in {DTC_REFERENCE_DIR}")
    
    return REFERENCE_CODES


def get_reference_description(code: str) -> Optional[str]:
    """Get the standard description for a DTC code from reference database."""
    if not REFERENCE_CODES:
        load_reference_codes()
    return REFERENCE_CODES.get(code.upper())


def call_openrouter(prompt: str, system_prompt: str = None, temperature: float = 0.3, manufacturer: str = None) -> Optional[dict]:
    """
    Call OpenRouter API with the configured DTC filler model.
    No web search - DTC codes are standard technical data.
    """
    if not OPENROUTER_API_KEY:
        print("❌ Error: OPENROUTER_API_KEY not set in environment")
        sys.exit(1)
    
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://carpulse.app",
        "X-Title": "CarPulse DTC Filler"
    }
    
    payload = {
        "model": DTC_FILLER_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": 8000,
    }
    
    try:
        response = requests.post(OPENROUTER_API_URL, headers=headers, json=payload, timeout=120)
        response.raise_for_status()
        data = response.json()
        
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        generation_id = data.get("id")
        
        # Get generation stats for accurate cost tracking
        if generation_id:
            time.sleep(0.3)  # Brief delay for stats to be available
            gen_response = requests.get(
                f"https://openrouter.ai/api/v1/generation?id={generation_id}",
                headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
                timeout=10
            )
            if gen_response.status_code == 200:
                gen_data = gen_response.json().get("data", {})
                stats.add_generation_stats(gen_data, operation='generate', manufacturer=manufacturer)
                cost = gen_data.get('total_cost') or 0
                tokens_in = gen_data.get('native_tokens_prompt') or 0
                tokens_out = gen_data.get('native_tokens_completion') or 0
                print(f"   💵 Cost: ${cost:.6f} ({tokens_in:,}→{tokens_out:,} tokens)")
            else:
                stats.add_usage_fallback(data.get("usage", {}), operation='generate', manufacturer=manufacturer)
                usage = data.get("usage", {})
                print(f"   💵 Cost: ~estimated ({usage.get('prompt_tokens', 0):,}→{usage.get('completion_tokens', 0):,} tokens)")
        else:
            stats.add_usage_fallback(data.get("usage", {}), operation='generate', manufacturer=manufacturer)
        
        return content
        
    except requests.exceptions.RequestException as e:
        print(f"   ❌ API Error: {e}")
        stats.add_failed_call()
        return None


def load_existing_dtc_codes() -> pd.DataFrame:
    """Load existing DTC codes from both output and assets directories."""
    dtc_files = [
        OUTPUT_DIR / "dtc_codes.csv",
        ASSETS_DIR / "dtc_codes.csv",
    ]
    
    all_codes = []
    for file_path in dtc_files:
        if file_path.exists():
            df = pd.read_csv(file_path)
            all_codes.append(df)
            print(f"📂 Loaded {len(df)} codes from {file_path.name}")
    
    if not all_codes:
        print("⚠️  No existing DTC codes found")
        return pd.DataFrame(columns=[
            'code', 'make_id', 'description', 'detailed_description', 'system',
            'severity', 'common_causes', 'symptoms', 'applicable_models',
            'applicable_years', 'powertrain_type'
        ])
    
    # Combine and deduplicate (prefer output over assets)
    combined = pd.concat(all_codes, ignore_index=True)
    combined = combined.drop_duplicates(subset=['code', 'make_id'], keep='first')
    return combined


def analyze_dtc_coverage(df: pd.DataFrame) -> Dict:
    """Analyze current DTC code coverage by manufacturer and category."""
    # Load reference codes for comparison
    load_reference_codes()
    
    analysis = {
        "total_codes": len(df),
        "total_reference_codes": len(REFERENCE_CODES),
        "manufacturers": {},
        "categories": {},
        "reference_coverage": {},
        "gaps": [],
    }
    
    # Analyze reference code coverage by category
    for code in REFERENCE_CODES.keys():
        if len(code) >= 2:
            prefix = code[:2].upper()
            analysis["reference_coverage"][prefix] = analysis["reference_coverage"].get(prefix, 0) + 1
    
    # Analyze by manufacturer
    for make_id in df['make_id'].unique():
        make_codes = df[df['make_id'] == make_id]
        make_code_set = set(make_codes['code'].str.upper())
        
        make_analysis = {
            "count": len(make_codes),
            "categories": {},
            "has_generic": False,
            "has_manufacturer_specific": False,
            "reference_codes_covered": 0,
            "powertrain_types": list(make_codes['powertrain_type'].dropna().unique()),
        }
        
        # Count how many reference codes this manufacturer has
        reference_overlap = make_code_set.intersection(set(REFERENCE_CODES.keys()))
        make_analysis["reference_codes_covered"] = len(reference_overlap)
        
        for code in make_codes['code']:
            if len(code) >= 2:
                prefix = code[:2].upper()
                category = prefix[0] + prefix[1] if len(prefix) >= 2 else prefix
                make_analysis["categories"][category] = make_analysis["categories"].get(category, 0) + 1
                
                # Check for generic vs manufacturer-specific
                if prefix in ['P0', 'B0', 'C0', 'U0']:
                    make_analysis["has_generic"] = True
                elif prefix in ['P1', 'B1', 'C1', 'U1', 'P2', 'B2', 'C2', 'U2']:
                    make_analysis["has_manufacturer_specific"] = True
        
        analysis["manufacturers"][make_id] = make_analysis
    
    # Analyze overall categories
    for code in df['code']:
        if len(code) >= 2:
            prefix = code[:2].upper()
            analysis["categories"][prefix] = analysis["categories"].get(prefix, 0) + 1
    
    return analysis


def identify_gaps(df: pd.DataFrame, manufacturer: str = None) -> Dict:
    """Identify gaps in DTC code coverage."""
    gaps = {
        "missing_categories": [],
        "low_coverage_manufacturers": [],
        "missing_powertrain_types": [],
        "recommendations": [],
    }
    
    analysis = analyze_dtc_coverage(df)
    
    # Check manufacturers
    manufacturers_to_check = [manufacturer] if manufacturer else list(analysis["manufacturers"].keys())
    
    for make_id in manufacturers_to_check:
        if make_id not in analysis["manufacturers"]:
            gaps["low_coverage_manufacturers"].append({
                "make_id": make_id,
                "count": 0,
                "reason": "No codes found"
            })
            continue
            
        make_data = analysis["manufacturers"][make_id]
        
        # Determine recommended count based on manufacturer type
        premium_makes = ['bmw', 'mercedes-benz', 'audi', 'porsche', 'lexus']
        if make_id in premium_makes:
            recommended = RECOMMENDED_CODE_COUNTS["premium"]
        else:
            recommended = RECOMMENDED_CODE_COUNTS["standard"]
        
        if make_data["count"] < recommended:
            gaps["low_coverage_manufacturers"].append({
                "make_id": make_id,
                "count": make_data["count"],
                "recommended": recommended,
                "deficit": recommended - make_data["count"],
            })
        
        # Check for missing categories
        expected_categories = ['P0', 'P1', 'B1', 'C1', 'U0']
        missing = [cat for cat in expected_categories if cat not in make_data["categories"]]
        if missing:
            gaps["missing_categories"].append({
                "make_id": make_id,
                "missing": missing,
            })
        
        # Check powertrain coverage against manufacturer profile
        make_codes = df[df['make_id'] == make_id]
        existing_powertrains = set(make_codes['powertrain_type'].dropna().unique())
        expected_powertrains = set(MANUFACTURER_POWERTRAINS.get(make_id, MANUFACTURER_POWERTRAINS["default"]))
        
        # Find missing powertrain types (exclude 'All' from comparison)
        missing_powertrains = expected_powertrains - existing_powertrains - {'All'}
        if missing_powertrains:
            gaps["missing_powertrain_types"].append({
                "make_id": make_id,
                "missing": list(missing_powertrains),
                "has": list(existing_powertrains),
            })
    
    return gaps


def generate_dtc_codes_for_manufacturer(
    make_id: str,
    existing_codes: Set[str],
    target_count: int = 20,
    focus_categories: List[str] = None,
    focus_powertrain: str = None
) -> List[Dict]:
    """Generate DTC codes to fill gaps for a manufacturer."""
    
    # If large request, chunk it into smaller batches to avoid truncation
    MAX_BATCH_SIZE = 25
    if target_count > MAX_BATCH_SIZE:
        all_codes = []
        remaining = target_count
        batch_num = 1
        current_existing = existing_codes.copy()
        
        while remaining > 0:
            batch_size = min(remaining, MAX_BATCH_SIZE)
            print(f"   📦 Batch {batch_num}: Generating {batch_size} codes...")
            
            batch_codes = _generate_single_batch(
                make_id, current_existing, batch_size, focus_categories, focus_powertrain
            )
            
            if batch_codes:
                all_codes.extend(batch_codes)
                # Add generated codes to existing to avoid duplicates in next batch
                for code in batch_codes:
                    current_existing.add(code.get('code', '').upper())
            
            remaining -= batch_size
            batch_num += 1
            
            # Small delay between batches
            if remaining > 0:
                time.sleep(0.5)
        
        return all_codes
    else:
        return _generate_single_batch(make_id, existing_codes, target_count, focus_categories, focus_powertrain)


def _generate_single_batch(
    make_id: str,
    existing_codes: Set[str],
    target_count: int,
    focus_categories: List[str] = None,
    focus_powertrain: str = None
) -> List[Dict]:
    """Generate a single batch of DTC codes (max ~25 recommended)."""
    
    # Build context about existing codes
    existing_list = sorted(list(existing_codes))[:50]  # Limit for prompt size
    existing_context = ", ".join(existing_list) if existing_list else "None"
    
    # Determine focus
    category_focus = ""
    if focus_categories:
        category_focus = f"\nFocus on these code categories: {', '.join(focus_categories)}"
    
    powertrain_focus = ""
    if focus_powertrain:
        powertrain_focus = f"\nInclude codes specific to {focus_powertrain} vehicles."
    
    system_prompt = """You are an expert automotive diagnostician with deep knowledge of OBD-II diagnostic trouble codes (DTCs) for all vehicle manufacturers.

You provide accurate, real-world DTC codes with proper technical descriptions. Your codes follow SAE J2012 standards:
- P0xxx: Generic powertrain (OBD-II standard)
- P1xxx-P3xxx: Manufacturer-specific powertrain
- B0xxx: Generic body
- B1xxx-B2xxx: Manufacturer-specific body
- C0xxx: Generic chassis
- C1xxx-C2xxx: Manufacturer-specific chassis
- U0xxx: Generic network
- U1xxx-U2xxx: Manufacturer-specific network

Powertrain types (use UK terminology):
- Petrol: Standard petrol/gasoline internal combustion engine
- Diesel: Standard diesel engine (common in UK/EU)
- Petrol Hybrid: Self-charging hybrid (HEV) with petrol engine + electric motor
- Diesel Hybrid: Self-charging hybrid with diesel engine + electric motor
- Plug-in Hybrid: PHEV that can charge from mains power
- Electric: Battery electric vehicle (BEV), no combustion engine
- All: Generic codes applicable to any powertrain

Return ONLY valid JSON array. No markdown, no explanations outside the JSON."""

    # Determine expected powertrains for this manufacturer
    expected_powertrains = MANUFACTURER_POWERTRAINS.get(make_id, MANUFACTURER_POWERTRAINS["default"])
    powertrain_instruction = f"\nInclude codes for these powertrain types used by {make_id.upper()}: {', '.join(expected_powertrains)}"
    if focus_powertrain:
        powertrain_instruction = f"\nFocus specifically on {focus_powertrain} vehicle codes."

    prompt = f"""Generate {target_count} DTC codes for {make_id.upper()} vehicles that are NOT in this existing list:
{existing_context}

{category_focus}
{powertrain_instruction}

Include a mix of:
- Engine/powertrain codes (P0xxx, P1xxx) - cover different fuel types!
- Body system codes (B1xxx) - airbags, lighting, HVAC
- Chassis codes (C1xxx) - ABS, traction control, steering
- Network communication codes (U0xxx, U1xxx)

For Petrol vehicles: Include fuel injection, ignition, emissions (catalytic converter, O2 sensors)
For Diesel vehicles: Include DPF, EGR, AdBlue/DEF, glow plugs, turbo, high-pressure fuel
For Hybrid vehicles: Include battery management, inverter, regenerative braking, hybrid system codes
For Electric vehicles: Include HV battery, charging system, inverter, thermal management, motor codes

Return a JSON array with this exact structure:
[
  {{
    "code": "P1234",
    "description": "Short description (under 80 chars)",
    "detailed_description": "Detailed technical explanation of what this code means, when it triggers, and its implications.",
    "system": "Engine|Transmission|Fuel System|Emissions|ABS|SRS|Body|Network|HVAC|Hybrid System|EV Battery|EV Charging|EV Motor|etc",
    "severity": "Low|Medium|High|Critical",
    "common_causes": ["Cause 1", "Cause 2", "Cause 3"],
    "symptoms": ["Symptom 1", "Symptom 2"],
    "applicable_models": "Specific models or 'All'",
    "applicable_years": "Year range like '2010+' or '2005-2015'",
    "powertrain_type": "Petrol|Diesel|Petrol Hybrid|Diesel Hybrid|Plug-in Hybrid|Electric|All"
  }}
]

IMPORTANT: Return ONLY the JSON array, no other text."""

    print(f"\n   🔧 Generating {target_count} DTC codes for {make_id}...")
    response = call_openrouter(prompt, system_prompt, temperature=0.4, manufacturer=make_id)
    
    if not response:
        return []
    
    # Parse JSON from response with robust recovery
    codes = parse_json_robustly(response)
    if codes:
        print(f"   ✅ Generated {len(codes)} codes")
    else:
        print(f"   ⚠️  Could not parse any valid codes from response")
    return codes


def parse_json_robustly(response: str) -> List[Dict]:
    """Parse JSON with multiple fallback strategies for malformed responses."""
    
    # Strategy 1: Try direct parse of full array
    try:
        json_match = re.search(r'\[[\s\S]*\]', response)
        if json_match:
            return json.loads(json_match.group())
    except json.JSONDecodeError:
        pass
    
    # Strategy 2: Try to fix truncated JSON by finding last complete object
    try:
        json_match = re.search(r'\[[\s\S]*', response)
        if json_match:
            json_str = json_match.group()
            # Find the last complete object (ends with })
            last_complete = json_str.rfind('}')
            if last_complete > 0:
                # Truncate and close the array
                fixed_json = json_str[:last_complete + 1] + ']'
                # Remove any trailing comma before the ]
                fixed_json = re.sub(r',\s*\]', ']', fixed_json)
                return json.loads(fixed_json)
    except json.JSONDecodeError:
        pass
    
    # Strategy 3: Extract individual objects and build array
    try:
        # Find all complete JSON objects
        objects = []
        # Pattern to match individual DTC objects
        pattern = r'\{\s*"code"\s*:\s*"[^"]+"\s*,[\s\S]*?"powertrain_type"\s*:\s*"[^"]+"\s*\}'
        matches = re.findall(pattern, response)
        for match in matches:
            try:
                obj = json.loads(match)
                if 'code' in obj and 'description' in obj:
                    objects.append(obj)
            except:
                continue
        if objects:
            print(f"   🔧 Recovered {len(objects)} codes via object extraction")
            return objects
    except:
        pass
    
    # Strategy 4: Line-by-line recovery for simpler format
    try:
        objects = []
        lines = response.split('\n')
        current_obj = []
        brace_count = 0
        
        for line in lines:
            if '{' in line:
                brace_count += line.count('{')
            if '}' in line:
                brace_count -= line.count('}')
            
            if brace_count > 0 or '{' in line:
                current_obj.append(line)
            
            if brace_count == 0 and current_obj:
                try:
                    obj_str = '\n'.join(current_obj)
                    # Clean up trailing commas
                    obj_str = re.sub(r',(\s*[}\]])', r'\1', obj_str)
                    obj = json.loads(obj_str)
                    if 'code' in obj:
                        objects.append(obj)
                except:
                    pass
                current_obj = []
        
        if objects:
            print(f"   🔧 Recovered {len(objects)} codes via line-by-line parsing")
            return objects
    except:
        pass
    
    return []


def fill_gaps_for_manufacturer(
    df: pd.DataFrame,
    make_id: str,
    target_count: int = None,
    focus_categories: List[str] = None,
    focus_powertrain: str = None
) -> pd.DataFrame:
    """Fill DTC code gaps for a specific manufacturer."""
    print(f"\n{'='*60}")
    print(f"📋 Filling DTC gaps for: {make_id.upper()}")
    print(f"{'='*60}")
    
    # Get existing codes for this manufacturer
    make_codes = df[df['make_id'] == make_id]
    existing_codes = set(make_codes['code'].str.upper())
    current_count = len(existing_codes)
    
    print(f"   Current codes: {current_count}")
    
    # Determine target
    if target_count is None:
        premium_makes = ['bmw', 'mercedes-benz', 'audi', 'porsche', 'lexus', 'jaguar']
        if make_id in premium_makes:
            target_count = max(RECOMMENDED_CODE_COUNTS["premium"] - current_count, 20)
        else:
            target_count = max(RECOMMENDED_CODE_COUNTS["standard"] - current_count, 15)
    
    print(f"   Target new codes: {target_count}")
    
    # Generate new codes
    new_codes = generate_dtc_codes_for_manufacturer(
        make_id,
        existing_codes,
        target_count,
        focus_categories,
        focus_powertrain
    )
    
    if not new_codes:
        print(f"   ❌ No codes generated")
        return df
    
    # Add make_id and convert to DataFrame
    for code in new_codes:
        code['make_id'] = make_id
        # Ensure common_causes and symptoms are JSON strings
        if isinstance(code.get('common_causes'), list):
            code['common_causes'] = json.dumps(code['common_causes'])
        if isinstance(code.get('symptoms'), list):
            code['symptoms'] = json.dumps(code['symptoms'])
    
    new_df = pd.DataFrame(new_codes)
    
    # Ensure column order matches existing
    expected_cols = [
        'code', 'make_id', 'description', 'detailed_description', 'system',
        'severity', 'common_causes', 'symptoms', 'applicable_models',
        'applicable_years', 'powertrain_type'
    ]
    for col in expected_cols:
        if col not in new_df.columns:
            new_df[col] = ''
    new_df = new_df[expected_cols]
    
    # Filter out any duplicates
    new_df = new_df[~new_df['code'].str.upper().isin(existing_codes)]
    
    stats.add_codes(make_id, len(new_df))
    print(f"   ✅ Adding {len(new_df)} new codes")
    
    # Combine with existing
    combined = pd.concat([df, new_df], ignore_index=True)
    return combined


def fill_gaps_for_country(df: pd.DataFrame, country: str) -> pd.DataFrame:
    """Fill DTC gaps for all manufacturers from a country."""
    if country not in MANUFACTURERS_BY_COUNTRY:
        print(f"❌ Unknown country: {country}")
        print(f"   Available: {', '.join(MANUFACTURERS_BY_COUNTRY.keys())}")
        return df
    
    manufacturers = MANUFACTURERS_BY_COUNTRY[country]
    print(f"\n🌍 Filling gaps for {country} manufacturers: {', '.join(manufacturers)}")
    
    for make_id in manufacturers:
        # Check if manufacturer exists in data
        if make_id not in df['make_id'].unique():
            print(f"\n⚠️  {make_id} not in database, skipping")
            continue
        df = fill_gaps_for_manufacturer(df, make_id)
    
    return df


# Safe generic prefixes that are universal across all manufacturers
SAFE_GENERIC_PREFIXES = ['P0', 'B0', 'C0', 'U0']

def fill_all_gaps(df: pd.DataFrame, use_smart_targets: bool = False) -> pd.DataFrame:
    """Fill DTC gaps for all manufacturers in the database."""
    manufacturers = df['make_id'].unique()
    print(f"\n🌐 Filling gaps for ALL {len(manufacturers)} manufacturers")
    
    if use_smart_targets:
        # Get AI-determined targets for all manufacturers
        targets = get_smart_targets_from_ai(df, list(manufacturers))
        
        for make_id in sorted(manufacturers):
            target = targets.get(make_id, 25)  # Default to 25 if not in AI response
            if target > 0:
                df = fill_gaps_for_manufacturer(df, make_id, target_count=target)
            else:
                print(f"\n⏭️  Skipping {make_id.upper()} - AI determined sufficient coverage")
    else:
        for make_id in sorted(manufacturers):
            df = fill_gaps_for_manufacturer(df, make_id)
    
    return df


def get_smart_targets_from_ai(df: pd.DataFrame, manufacturers: List[str]) -> Dict[str, int]:
    """Use AI to determine optimal target counts for each manufacturer."""
    print("\n" + "="*70)
    print("🧠 AI DETERMINING OPTIMAL TARGET COUNTS")
    print("="*70)
    
    # Build comprehensive context
    load_reference_codes()
    analysis = analyze_dtc_coverage(df)
    gaps = identify_gaps(df)
    
    # Build manufacturer summary
    manufacturer_summaries = []
    for make_id in manufacturers:
        make_data = analysis['manufacturers'].get(make_id, {})
        existing_count = make_data.get('count', 0)
        categories = make_data.get('categories', {})
        powertrains = make_data.get('powertrain_types', [])
        expected_powertrains = MANUFACTURER_POWERTRAINS.get(make_id, MANUFACTURER_POWERTRAINS['default'])
        
        # Find missing categories
        expected_cats = ['P0', 'P1', 'B1', 'C1', 'U0']
        missing_cats = [c for c in expected_cats if c not in categories]
        
        # Find missing powertrains
        missing_pt = set(expected_powertrains) - set(powertrains) - {'All'}
        
        summary = f"""
{make_id.upper()}:
  Current: {existing_count} codes
  Categories: {dict(categories)}
  Missing categories: {missing_cats}
  Powertrains: {powertrains}
  Missing powertrains: {list(missing_pt)}
  Expected powertrains: {expected_powertrains}"""
        manufacturer_summaries.append(summary)
    
    system_prompt = """You are an automotive diagnostics expert determining optimal DTC code coverage.

Analyze each manufacturer and determine how many NEW codes they need based on:
1. Current coverage vs expected (premium brands need 80+, standard need 60+)
2. Missing code categories (P1, B1, C1, U0 are important)
3. Missing powertrain types (especially Diesel, Hybrid, EV for UK market)
4. Manufacturer complexity (luxury/tech brands need more codes)

Return ONLY a valid JSON object with manufacturer targets. Example:
{"toyota": 25, "bmw": 40, "honda": 10, "generic": 0}

Use 0 if manufacturer has sufficient coverage.
Maximum should be 60 per manufacturer to keep costs reasonable."""

    prompt = f"""Analyze these manufacturers and determine how many NEW DTC codes each needs:

{chr(10).join(manufacturer_summaries)}

Reference database has 3,071 standard codes available.

Return a JSON object with each manufacturer's target count (0-60).
Focus on:
- Filling category gaps (especially P1, B1, C1, U0/U1)
- Filling powertrain gaps (Diesel, Hybrid, EV codes)
- Premium brands (BMW, Mercedes, Audi) need more coverage
- Don't waste tokens on manufacturers with good coverage

Return ONLY the JSON object, no explanation."""

    print("   🔍 Analyzing all manufacturers...")
    response = call_openrouter(prompt, system_prompt, temperature=0.3, manufacturer='smart-targets')
    
    if not response:
        print("   ⚠️  AI analysis failed, using default targets")
        return {m: 30 for m in manufacturers}
    
    # Parse JSON response
    try:
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            targets = json.loads(json_match.group())
            # Convert keys to lowercase
            targets = {k.lower(): v for k, v in targets.items()}
            
            print("\n   📊 AI-Determined Targets:")
            total = 0
            for make_id in sorted(manufacturers):
                target = targets.get(make_id, 25)
                targets[make_id] = target  # Ensure all manufacturers have a value
                total += target
                print(f"      {make_id:15} → {target:3} codes")
            
            print(f"\n   📈 Total codes to generate: {total}")
            est_cost = total * 0.0015  # Rough estimate
            print(f"   💰 Estimated cost: ${est_cost:.2f}")
            
            return targets
    except json.JSONDecodeError as e:
        print(f"   ⚠️  Could not parse AI response: {e}")
    
    # Default fallback
    return {m: 30 for m in manufacturers}


def import_all_generic_codes(df: pd.DataFrame) -> pd.DataFrame:
    """
    Import ALL safe generic codes (P0, B0, C0, U0) from reference database.
    These are truly universal codes that work for any vehicle.
    """
    load_reference_codes()
    
    if not REFERENCE_CODES:
        print("❌ No reference codes available")
        return df
    
    print("\n" + "="*70)
    print("📥 IMPORTING ALL GENERIC OBD-II CODES")
    print("="*70)
    print(f"   Safe prefixes: {', '.join(SAFE_GENERIC_PREFIXES)}")
    
    # Get all existing codes across all manufacturers
    all_existing = set(df['code'].str.upper())
    
    # Filter to only safe generic codes
    generic_codes = {}
    for code, desc in REFERENCE_CODES.items():
        code_upper = code.upper()
        if code_upper in all_existing:
            continue
        # Check if starts with a safe generic prefix
        prefix = code_upper[:2] if len(code_upper) >= 2 else ''
        if prefix in SAFE_GENERIC_PREFIXES:
            generic_codes[code] = desc
    
    # Count by prefix
    by_prefix = {}
    for code in generic_codes:
        prefix = code[:2].upper()
        by_prefix[prefix] = by_prefix.get(prefix, 0) + 1
    
    print(f"\n   📊 Generic codes to import:")
    for prefix in sorted(by_prefix.keys()):
        print(f"      {prefix}xxx: {by_prefix[prefix]} codes")
    print(f"      TOTAL: {len(generic_codes)} codes")
    
    if not generic_codes:
        print("   ✅ All generic codes already in database!")
        return df
    
    # Quick import all of them (assigned to 'generic' make_id)
    codes_to_import = list(generic_codes.items())
    new_rows = quick_import_codes(codes_to_import, 'generic')
    
    new_df = pd.DataFrame(new_rows)
    stats.codes_added += len(new_df)
    stats.codes_by_manufacturer['generic'] = stats.codes_by_manufacturer.get('generic', 0) + len(new_df)
    
    print(f"\n   ✅ Imported {len(new_df)} generic codes (make_id='generic')")
    print(f"   💰 Cost: $0.00 (no AI used)")
    
    # Combine
    combined = pd.concat([df, new_df], ignore_index=True)
    return combined


def smart_import_manufacturer_codes(
    df: pd.DataFrame,
    manufacturers: List[str] = None,
    enrich: bool = True
) -> pd.DataFrame:
    """
    Smart import manufacturer-specific codes from reference database.
    ONE PASS: Classifies ALL codes to ALL manufacturers at once.
    Uses keyword matching + AI to identify which codes belong to which manufacturer.
    
    Args:
        df: Existing DTC codes DataFrame
        manufacturers: List of manufacturers to process (None = all known)
        enrich: Whether to use AI to enrich imported codes
    """
    load_reference_codes()
    
    if not REFERENCE_CODES:
        print("❌ No reference codes available")
        return df
    
    # Determine which manufacturers to process
    if manufacturers is None:
        manufacturers = list(MANUFACTURER_KEYWORDS.keys())
    elif isinstance(manufacturers, str):
        manufacturers = [manufacturers.lower()]
    else:
        manufacturers = [m.lower() for m in manufacturers]
    
    print(f"\n🧠 Smart Import: ONE PASS for {len(manufacturers)} manufacturers")
    print(f"   Target: {', '.join(manufacturers)}")
    
    # Get existing codes by manufacturer
    existing_by_make = {}
    for make_id in manufacturers:
        make_codes = df[df['make_id'] == make_id]
        existing_by_make[make_id] = set(make_codes['code'].str.upper())
    
    # Manufacturer-specific prefixes (P1, B1, C1, U1, P2, B2, C2, U2)
    MANUFACTURER_SPECIFIC_PREFIXES = ['P1', 'B1', 'C1', 'U1', 'P2', 'B2', 'C2', 'U2']
    
    # Filter reference codes to only manufacturer-specific ones
    mfr_specific_codes = {}
    for code, desc in REFERENCE_CODES.items():
        code_upper = code.upper()
        prefix = code_upper[:2] if len(code_upper) >= 2 else ''
        if prefix in MANUFACTURER_SPECIFIC_PREFIXES:
            mfr_specific_codes[code_upper] = desc
    
    print(f"   Manufacturer-specific codes in reference: {len(mfr_specific_codes)}")
    
    # Step 1: Keyword-based matching for ALL manufacturers at once (fast, free)
    print("\n   📋 Step 1: Keyword-based matching (all manufacturers)...")
    keyword_matches = {make_id: [] for make_id in manufacturers}
    unmatched_codes = []
    
    for code, desc in mfr_specific_codes.items():
        desc_lower = desc.lower()
        code_lower = code.lower()
        matched = False
        
        for make_id in manufacturers:
            keywords = MANUFACTURER_KEYWORDS.get(make_id, [])
            for keyword in keywords:
                if keyword.lower() in desc_lower or keyword.lower() in code_lower:
                    keyword_matches[make_id].append((code, desc))
                    matched = True
                    break
            if matched:
                break
        
        if not matched:
            unmatched_codes.append((code, desc))
    
    # Show keyword matching results
    total_matched = sum(len(codes) for codes in keyword_matches.values())
    print(f"   ✅ Keyword matched: {total_matched} codes")
    for make_id in sorted(keyword_matches.keys()):
        if keyword_matches[make_id]:
            print(f"      {make_id}: {len(keyword_matches[make_id])} codes")
    print(f"   ❓ Unmatched: {len(unmatched_codes)} codes")
    
    # Step 2: ONE AI classification pass for ALL unmatched codes to ALL manufacturers
    ai_matches = {make_id: [] for make_id in manufacturers}
    if unmatched_codes and len(unmatched_codes) > 20:
        print(f"\n   📋 Step 2: AI classification (ONE PASS for all {len(unmatched_codes)} codes)...")
        ai_matches = classify_codes_with_ai(unmatched_codes, manufacturers)
        
        # Show AI results
        total_ai = sum(len(codes) for codes in ai_matches.values())
        print(f"   ✅ AI classified: {total_ai} codes")
        for make_id in sorted(ai_matches.keys()):
            if ai_matches[make_id]:
                print(f"      {make_id}: {len(ai_matches[make_id])} codes")
    
    # Step 3: Combine matches and filter out existing codes
    print("\n   📋 Step 3: Filtering duplicates and importing...")
    all_new_codes = []
    import_summary = {}
    
    for make_id in manufacturers:
        combined_matches = keyword_matches[make_id] + ai_matches.get(make_id, [])
        
        # Filter out codes that already exist for this manufacturer
        new_for_make = [
            (code, desc) for code, desc in combined_matches 
            if code.upper() not in existing_by_make.get(make_id, set())
        ]
        
        if new_for_make:
            import_summary[make_id] = len(new_for_make)
            
            if enrich:
                # AI enrichment for detailed info
                enriched = enrich_codes_batch(new_for_make, make_id)
                all_new_codes.extend(enriched)
            else:
                # Quick import with smart defaults
                quick = quick_import_codes(new_for_make, make_id)
                all_new_codes.extend(quick)
    
    # Show import summary
    if import_summary:
        print(f"\n   📊 Import Summary:")
        for make_id in sorted(import_summary.keys()):
            print(f"      {make_id}: {import_summary[make_id]} new codes")
    
    if not all_new_codes:
        print("\n   ✅ No new codes to import!")
        return df
    
    # Add to dataframe
    new_df = pd.DataFrame(all_new_codes)
    stats.codes_added += len(new_df)
    
    # Track by manufacturer
    for make_id in manufacturers:
        make_count = len([c for c in all_new_codes if c.get('make_id') == make_id])
        if make_count > 0:
            stats.codes_by_manufacturer[make_id] = stats.codes_by_manufacturer.get(make_id, 0) + make_count
    
    print(f"\n   ✅ Total imported: {len(new_df)} codes")
    
    combined = pd.concat([df, new_df], ignore_index=True)
    return combined


def classify_codes_with_ai(
    unmatched_codes: List[Tuple[str, str]],
    manufacturers: List[str]
) -> Dict[str, List[Tuple[str, str]]]:
    """Use AI to classify unmatched codes to manufacturers."""
    
    # Batch codes for efficiency (process in chunks)
    BATCH_SIZE = 100
    all_classifications = {make_id: [] for make_id in manufacturers}
    
    for i in range(0, len(unmatched_codes), BATCH_SIZE):
        batch = unmatched_codes[i:i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (len(unmatched_codes) + BATCH_SIZE - 1) // BATCH_SIZE
        
        print(f"      Batch {batch_num}/{total_batches}: Classifying {len(batch)} codes...")
        
        # Format codes for AI
        codes_text = "\n".join([f"{code}: {desc}" for code, desc in batch])
        
        system_prompt = """You are an expert automotive diagnostician who can identify which manufacturer a DTC code belongs to based on its description.

Analyze each code's description for manufacturer-specific technologies, systems, or terminology.

Return a JSON object mapping each code to its most likely manufacturer, or "unknown" if unsure.
Example: {"P1259": "honda", "P1234": "ford", "P1567": "unknown"}

Only use these manufacturers: """ + ", ".join(manufacturers)

        prompt = f"""Classify these DTC codes to their manufacturers based on the descriptions:

{codes_text}

Return ONLY a JSON object mapping code to manufacturer (or "unknown").
Be conservative - only match if you're confident about the manufacturer."""

        response = call_openrouter(prompt, system_prompt, temperature=0.2, manufacturer='classify')
        
        if response:
            try:
                json_match = re.search(r'\{[\s\S]*\}', response)
                if json_match:
                    classifications = json.loads(json_match.group())
                    
                    # Add classified codes to appropriate manufacturer
                    for code, desc in batch:
                        make_id = classifications.get(code, classifications.get(code.upper(), 'unknown'))
                        if make_id and make_id.lower() in manufacturers:
                            all_classifications[make_id.lower()].append((code, desc))
            except json.JSONDecodeError:
                print(f"      ⚠️  Could not parse AI classification response")
        
        # Small delay between batches
        if i + BATCH_SIZE < len(unmatched_codes):
            time.sleep(0.3)
    
    # Report AI classification results
    total_ai = sum(len(codes) for codes in all_classifications.values())
    print(f"      ✅ AI classified: {total_ai} codes")
    
    return all_classifications


def enrich_codes_batch(codes: List[Tuple[str, str]], make_id: str) -> List[Dict]:
    """Enrich a batch of codes with AI-generated detailed info."""
    
    # For efficiency, batch process with AI
    BATCH_SIZE = 25
    all_enriched = []
    
    for i in range(0, len(codes), BATCH_SIZE):
        batch = codes[i:i + BATCH_SIZE]
        
        codes_text = "\n".join([f"{code}: {desc}" for code, desc in batch])
        
        system_prompt = f"""You are an expert {make_id.upper()} technician. Enrich these DTC codes with detailed diagnostic information.

For each code, provide:
- detailed_description: Technical explanation
- system: Affected system (Engine, Transmission, SRS, ABS, etc.)
- severity: Low/Medium/High/Critical
- common_causes: List of likely causes
- symptoms: Observable symptoms
- powertrain_type: Petrol/Diesel/Petrol Hybrid/Diesel Hybrid/Plug-in Hybrid/Electric/All

Return a JSON array with enriched codes."""

        prompt = f"""Enrich these {make_id.upper()} DTC codes:

{codes_text}

Return JSON array:
[{{"code": "P1234", "description": "...", "detailed_description": "...", "system": "...", "severity": "...", "common_causes": [...], "symptoms": [...], "applicable_models": "...", "applicable_years": "...", "powertrain_type": "..."}}]"""

        response = call_openrouter(prompt, system_prompt, temperature=0.3, manufacturer=make_id)
        
        if response:
            enriched = parse_json_robustly(response)
            if enriched:
                # Ensure make_id is set
                for code_info in enriched:
                    code_info['make_id'] = make_id
                    # Convert lists to JSON strings if needed
                    if isinstance(code_info.get('common_causes'), list):
                        code_info['common_causes'] = json.dumps(code_info['common_causes'])
                    if isinstance(code_info.get('symptoms'), list):
                        code_info['symptoms'] = json.dumps(code_info['symptoms'])
                all_enriched.extend(enriched)
        
        if i + BATCH_SIZE < len(codes):
            time.sleep(0.3)
    
    # Fallback for any codes not enriched
    enriched_codes = {c.get('code', '').upper() for c in all_enriched}
    for code, desc in codes:
        if code.upper() not in enriched_codes:
            # Quick import fallback
            fallback = quick_import_codes([(code, desc)], make_id)
            all_enriched.extend(fallback)
    
    return all_enriched


def quick_import_codes(codes: List[Tuple[str, str]], make_id: str) -> List[Dict]:
    """Quick import codes without AI enrichment - uses smart defaults."""
    imported = []
    for code, desc in codes:
        code_upper = code.upper()
        
        # Infer system from code prefix
        if code_upper.startswith('P0') or code_upper.startswith('P1') or code_upper.startswith('P2'):
            system = 'Powertrain'
        elif code_upper.startswith('B'):
            system = 'Body'
        elif code_upper.startswith('C'):
            system = 'Chassis'
        elif code_upper.startswith('U'):
            system = 'Network'
        else:
            system = 'Unknown'
        
        imported.append({
            'code': code_upper,
            'make_id': make_id,
            'description': desc,
            'detailed_description': desc,
            'system': system,
            'severity': 'Medium',
            'common_causes': '[]',
            'symptoms': '[]',
            'applicable_models': f'Various {make_id.upper()} models',
            'applicable_years': '2000-2024',
            'powertrain_type': 'All'
        })
    
    return imported


def enrich_existing_codes(
    df: pd.DataFrame,
    manufacturers: List[str] = None
) -> pd.DataFrame:
    """
    Enrich existing codes that have basic/minimal descriptions.
    Identifies codes where detailed_description == description or common_causes is empty.
    """
    if manufacturers is None:
        manufacturers = list(df['make_id'].unique())
    elif isinstance(manufacturers, str):
        manufacturers = [manufacturers.lower()]
    else:
        manufacturers = [m.lower() for m in manufacturers]
    
    print(f"\n🔍 Finding codes to enrich for: {', '.join(manufacturers)}")
    
    # Find codes that need enrichment (basic descriptions)
    codes_to_enrich = []
    
    for make_id in manufacturers:
        make_df = df[df['make_id'] == make_id]
        
        for idx, row in make_df.iterrows():
            needs_enrich = False
            
            # Check if detailed_description is same as description or empty
            if pd.isna(row.get('detailed_description')) or \
               row.get('detailed_description') == row.get('description') or \
               len(str(row.get('detailed_description', ''))) < 50:
                needs_enrich = True
            
            # Check if common_causes is empty
            causes = row.get('common_causes', '[]')
            if causes in ['[]', '', None] or pd.isna(causes):
                needs_enrich = True
            
            if needs_enrich:
                codes_to_enrich.append({
                    'idx': idx,
                    'code': row['code'],
                    'description': row['description'],
                    'make_id': make_id
                })
    
    if not codes_to_enrich:
        print("   ✅ All codes already have detailed descriptions!")
        return df
    
    # Group by manufacturer
    by_make = {}
    for item in codes_to_enrich:
        make_id = item['make_id']
        if make_id not in by_make:
            by_make[make_id] = []
        by_make[make_id].append(item)
    
    print(f"   📋 Found {len(codes_to_enrich)} codes needing enrichment:")
    for make_id in sorted(by_make.keys()):
        print(f"      {make_id}: {len(by_make[make_id])} codes")
    
    # Enrich each manufacturer's codes
    total_enriched = 0
    
    for make_id, items in by_make.items():
        print(f"\n   🔧 Enriching {make_id} ({len(items)} codes)...")
        
        # Convert to tuple format for enrich_codes_batch
        codes_tuples = [(item['code'], item['description']) for item in items]
        
        # Enrich in batches
        enriched = enrich_codes_batch(codes_tuples, make_id)
        
        # Update the dataframe with enriched data
        enriched_by_code = {e['code'].upper(): e for e in enriched}
        
        for item in items:
            code = item['code'].upper()
            idx = item['idx']
            
            if code in enriched_by_code:
                enriched_data = enriched_by_code[code]
                
                # Update fields
                if 'detailed_description' in enriched_data:
                    df.at[idx, 'detailed_description'] = enriched_data['detailed_description']
                if 'system' in enriched_data:
                    df.at[idx, 'system'] = enriched_data['system']
                if 'severity' in enriched_data:
                    df.at[idx, 'severity'] = enriched_data['severity']
                if 'common_causes' in enriched_data:
                    df.at[idx, 'common_causes'] = enriched_data['common_causes']
                if 'symptoms' in enriched_data:
                    df.at[idx, 'symptoms'] = enriched_data['symptoms']
                if 'applicable_models' in enriched_data:
                    df.at[idx, 'applicable_models'] = enriched_data['applicable_models']
                if 'applicable_years' in enriched_data:
                    df.at[idx, 'applicable_years'] = enriched_data['applicable_years']
                if 'powertrain_type' in enriched_data:
                    df.at[idx, 'powertrain_type'] = enriched_data['powertrain_type']
                
                total_enriched += 1
                stats.codes_updated += 1
        
        stats.codes_by_manufacturer[make_id] = stats.codes_by_manufacturer.get(make_id, 0) + len(items)
    
    print(f"\n   ✅ Enriched {total_enriched} codes")
    return df


def cleanup_powertrain_data(df: pd.DataFrame, remove_invalid_codes: bool = True) -> pd.DataFrame:
    """
    Cleanup and normalize powertrain_type values:
    1. Replace 'Gasoline' with 'Petrol' (UK terminology)
    2. Convert combined types (e.g., 'Petrol Hybrid|Plug-in Hybrid' or 'Petrol/Diesel') to 'All'
    3. Remove trailing/leading whitespace
    4. Standardize case
    5. Optionally remove codes with invalid prefixes (not P/B/C/U)
    """
    print("\n" + "="*70)
    print("🧹 CLEANING UP DTC DATA")
    print("="*70)
    
    initial_count = len(df)
    
    # Step 1: Remove invalid DTC codes (not starting with P, B, C, or U)
    if remove_invalid_codes:
        valid_mask = df['code'].str.match(r'^[PBCU][0-9]', na=False)
        invalid_codes = df[~valid_mask]
        if len(invalid_codes) > 0:
            print(f"\n   🗑️  Removing {len(invalid_codes)} invalid codes (not P/B/C/U format):")
            by_make = invalid_codes.groupby('make_id').size()
            for make, count in by_make.items():
                print(f"      {make}: {count} codes")
            # Show sample of what's being removed
            sample = invalid_codes[['code', 'make_id', 'description']].head(5)
            print(f"\n      Sample of removed codes:")
            for _, row in sample.iterrows():
                print(f"         {row['code']} ({row['make_id']}): {row['description'][:50]}...")
            df = df[valid_mask].copy()
            stats.codes_updated += len(invalid_codes)
    
    if 'powertrain_type' not in df.columns:
        print("   ⚠️  No powertrain_type column found")
        return df
    
    # Valid single powertrain types
    VALID_TYPES = {'Petrol', 'Diesel', 'Petrol Hybrid', 'Diesel Hybrid', 'Plug-in Hybrid', 'Electric', 'All'}
    
    # Track changes
    changes = {
        'gasoline_to_petrol': 0,
        'combined_to_all': 0,
        'trimmed': 0,
        'invalid_fixed': 0,
    }
    
    original_values = df['powertrain_type'].copy()
    
    def normalize_powertrain(value):
        if pd.isna(value) or value == '':
            return 'All'
        
        # Clean whitespace
        cleaned = str(value).strip()
        
        # Replace Gasoline with Petrol (case-insensitive)
        if 'gasoline' in cleaned.lower():
            cleaned = re.sub(r'(?i)gasoline', 'Petrol', cleaned)
            changes['gasoline_to_petrol'] += 1
        
        # Check for combined types (contains | or / separator with multiple types)
        if '|' in cleaned:
            changes['combined_to_all'] += 1
            return 'All'
        
        # Check for slash separator (Petrol/Diesel) - but not valid single types
        if '/' in cleaned:
            changes['combined_to_all'] += 1
            return 'All'
        
        # Standardize common variants
        type_mapping = {
            'petrol': 'Petrol',
            'diesel': 'Diesel',
            'electric': 'Electric',
            'hybrid': 'Petrol Hybrid',
            'petrol hybrid': 'Petrol Hybrid',
            'diesel hybrid': 'Diesel Hybrid',
            'plug-in hybrid': 'Plug-in Hybrid',
            'plugin hybrid': 'Plug-in Hybrid',
            'phev': 'Plug-in Hybrid',
            'bev': 'Electric',
            'ev': 'Electric',
            'hev': 'Petrol Hybrid',
            'all': 'All',
            'automatic': 'All',  # This isn't a powertrain type
        }
        
        # Try case-insensitive match
        lower_cleaned = cleaned.lower()
        if lower_cleaned in type_mapping:
            return type_mapping[lower_cleaned]
        
        # If still not valid, default to 'All'
        if cleaned not in VALID_TYPES:
            changes['invalid_fixed'] += 1
            return 'All'
        
        return cleaned
    
    # Apply normalization
    df['powertrain_type'] = df['powertrain_type'].apply(normalize_powertrain)
    
    # Count actual changes
    total_changed = (original_values != df['powertrain_type']).sum()
    
    # Print summary
    print(f"\n   📊 Cleanup Summary:")
    print(f"      Initial records:        {initial_count}")
    print(f"      After invalid removal:  {len(df)}")
    print(f"      Powertrain modified:    {total_changed}")
    print(f"      Gasoline → Petrol:      {changes['gasoline_to_petrol']}")
    print(f"      Combined → All:         {changes['combined_to_all']}")
    print(f"      Invalid → All:          {changes['invalid_fixed']}")
    
    # Show distribution after cleanup
    print(f"\n   📋 Powertrain Distribution (after cleanup):")
    distribution = df['powertrain_type'].value_counts()
    for pt, count in distribution.items():
        print(f"      {pt:20} {count:5} codes")
    
    stats.codes_updated += total_changed
    
    return df


def fill_code_range(df: pd.DataFrame, code_range: str, manufacturer: str = None) -> pd.DataFrame:
    """Fill specific code range (e.g., P0xxx, B1xxx) for manufacturer(s)."""
    # Validate code range format
    match = re.match(r'^([PBCU])([0-3])(?:xxx)?$', code_range.upper())
    if not match:
        print(f"❌ Invalid code range: {code_range}")
        print("   Use format: P0xxx, P1xxx, B1xxx, C1xxx, U0xxx, etc.")
        return df
    
    prefix = match.group(1) + match.group(2)
    category_name = DTC_CATEGORIES.get(prefix, "Unknown")
    print(f"\n📋 Filling {prefix}xxx codes ({category_name})")
    
    if manufacturer:
        manufacturers = [manufacturer]
    else:
        manufacturers = list(df['make_id'].unique())
    
    for make_id in manufacturers:
        df = fill_gaps_for_manufacturer(
            df, make_id,
            target_count=15,
            focus_categories=[prefix]
        )
    
    return df


def save_dtc_codes(df: pd.DataFrame, also_to_assets: bool = False):
    """Save updated DTC codes to output directory and optionally to assets."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / "dtc_codes.csv"
    
    # Sort by make_id, then code
    df = df.sort_values(['make_id', 'code'])
    df = df.drop_duplicates(subset=['code', 'make_id'], keep='last')
    
    df.to_csv(output_path, index=False)
    print(f"\n💾 Saved {len(df)} DTC codes to {output_path}")
    
    # Also save to assets if requested (for cleanup operations)
    if also_to_assets:
        assets_path = ASSETS_DIR / "dtc_codes.csv"
        df.to_csv(assets_path, index=False)
        print(f"💾 Also saved to {assets_path}")


def import_standard_codes(
    df: pd.DataFrame,
    manufacturer: str = None,
    code_prefix: str = None,
    max_codes: int = 50,
    enrich: bool = False
) -> pd.DataFrame:
    """
    Import standard OBD-II codes from reference database.
    These are generic codes that apply to all vehicles.
    
    Args:
        df: Existing DTC codes DataFrame
        manufacturer: If specified, assign codes to this manufacturer. If None, use 'generic'
        code_prefix: Filter by prefix (e.g., 'P0', 'P1', 'B0')
        max_codes: Maximum codes to import per call
        enrich: If True, use AI to enrich codes with detailed info (costs money)
    """
    load_reference_codes()
    
    if not REFERENCE_CODES:
        print("❌ No reference codes available")
        return df
    
    make_id = manufacturer.lower() if manufacturer else 'generic'
    
    print(f"\n{'='*60}")
    print(f"📥 Importing Standard OBD-II Codes")
    print(f"{'='*60}")
    print(f"   Target: {make_id}")
    print(f"   Mode: {'AI-enriched (costs API)' if enrich else 'Quick import (free)'}")
    if code_prefix:
        print(f"   Filter: {code_prefix}xxx codes")
    
    # Get existing codes for this manufacturer
    existing_codes = set(df[df['make_id'] == make_id]['code'].str.upper())
    
    # Filter reference codes
    candidates = {}
    for code, desc in REFERENCE_CODES.items():
        if code.upper() in existing_codes:
            continue
        if code_prefix and not code.upper().startswith(code_prefix.upper()):
            continue
        candidates[code] = desc
    
    if not candidates:
        print(f"   ✅ All matching reference codes already imported!")
        return df
    
    print(f"   Found {len(candidates)} new codes to import")
    
    # Limit import count
    codes_to_import = list(candidates.items())[:max_codes]
    
    if enrich:
        # Use AI to enrich codes in batches
        new_rows = enrich_codes_with_ai(codes_to_import, make_id)
    else:
        # Quick import with smart defaults
        new_rows = quick_import_codes(codes_to_import, make_id)
    
    new_df = pd.DataFrame(new_rows)
    stats.codes_added += len(new_df)
    if manufacturer:
        stats.codes_by_manufacturer[make_id] = stats.codes_by_manufacturer.get(make_id, 0) + len(new_df)
    
    print(f"   ✅ Imported {len(new_df)} standard codes")
    
    # Combine
    combined = pd.concat([df, new_df], ignore_index=True)
    return combined


def quick_import_codes(codes_to_import: List[Tuple[str, str]], make_id: str) -> List[Dict]:
    """Quick import with smart defaults based on code patterns (no AI)."""
    new_rows = []
    
    for code, description in codes_to_import:
        code_upper = code.upper()
        
        # Smart system detection from code and description
        system = detect_system_from_code(code_upper, description)
        severity = detect_severity_from_code(code_upper, description)
        powertrain = detect_powertrain_from_code(code_upper, description)
        
        new_rows.append({
            'code': code,
            'make_id': make_id,
            'description': description,
            'detailed_description': f"Standard OBD-II code: {description}",
            'system': system,
            'severity': severity,
            'common_causes': '[]',
            'symptoms': '[]',
            'applicable_models': 'All',
            'applicable_years': '1996+',
            'powertrain_type': powertrain,
        })
    
    return new_rows


def detect_system_from_code(code: str, description: str) -> str:
    """Detect system from DTC code prefix and description."""
    desc_lower = description.lower()
    
    # Check description keywords first
    system_keywords = {
        'Fuel System': ['fuel', 'injector', 'pump', 'rail pressure', 'lean', 'rich'],
        'Ignition': ['ignition', 'misfire', 'spark', 'coil'],
        'Emissions': ['catalyst', 'catalytic', 'o2', 'oxygen', 'evap', 'egr', 'emission', 'nox', 'dpf', 'particulate'],
        'Transmission': ['transmission', 'gear', 'shift', 'torque converter', 'clutch', 'tcm'],
        'Engine': ['engine', 'cylinder', 'crankshaft', 'camshaft', 'vvt', 'timing', 'knock', 'compression'],
        'Cooling': ['coolant', 'thermostat', 'radiator', 'temperature', 'cooling'],
        'Intake/Exhaust': ['intake', 'exhaust', 'manifold', 'throttle', 'maf', 'map', 'turbo', 'boost'],
        'SRS': ['airbag', 'restraint', 'srs', 'occupant'],
        'ABS': ['abs', 'brake', 'wheel speed', 'traction', 'stability', 'esp', 'dsc'],
        'Steering': ['steering', 'power steering', 'eps'],
        'HVAC': ['hvac', 'climate', 'air condition', 'a/c', 'heater', 'blower'],
        'Lighting': ['lamp', 'light', 'headlight', 'bulb'],
        'Network': ['can', 'bus', 'communication', 'network', 'module'],
        'Hybrid System': ['hybrid', 'hv battery', 'inverter', 'regenerat'],
        'EV Battery': ['battery', 'cell', 'soc', 'charging', 'high voltage'],
        'EV Motor': ['motor', 'drive unit', 'traction motor'],
    }
    
    for system, keywords in system_keywords.items():
        if any(kw in desc_lower for kw in keywords):
            return system
    
    # Fall back to code prefix
    if code.startswith('P0') or code.startswith('P1') or code.startswith('P2') or code.startswith('P3'):
        return 'Engine'
    elif code.startswith('B'):
        return 'Body'
    elif code.startswith('C'):
        return 'Chassis'
    elif code.startswith('U'):
        return 'Network Communication'
    
    return 'Engine'


def detect_severity_from_code(code: str, description: str) -> str:
    """Detect severity from code and description."""
    desc_lower = description.lower()
    
    # Critical keywords
    if any(kw in desc_lower for kw in ['airbag', 'restraint', 'brake failure', 'steering', 'fuel leak']):
        return 'Critical'
    
    # High severity
    if any(kw in desc_lower for kw in ['misfire', 'catalyst damage', 'overheat', 'transmission', 'abs', 'fuel system']):
        return 'High'
    
    # Low severity
    if any(kw in desc_lower for kw in ['intermittent', 'lamp', 'light', 'sensor range', 'hvac']):
        return 'Low'
    
    return 'Medium'


def detect_powertrain_from_code(code: str, description: str) -> str:
    """Detect powertrain type from code and description."""
    desc_lower = description.lower()
    
    # Diesel-specific
    if any(kw in desc_lower for kw in ['glow plug', 'dpf', 'particulate', 'egr', 'adblue', 'def', 'urea', 'nox', 'turbo']):
        return 'Diesel'
    
    # EV-specific  
    if any(kw in desc_lower for kw in ['high voltage', 'hv battery', 'charging', 'inverter', 'traction motor', 'dc/dc']):
        return 'Electric'
    
    # Hybrid-specific
    if any(kw in desc_lower for kw in ['hybrid', 'regenerat', 'motor generator', 'mg1', 'mg2']):
        return 'Petrol Hybrid'
    
    # Petrol-specific
    if any(kw in desc_lower for kw in ['spark', 'ignition coil', 'knock sensor', 'catalytic converter']):
        return 'Petrol'
    
    return 'All'


def enrich_codes_with_ai(codes_to_import: List[Tuple[str, str]], make_id: str) -> List[Dict]:
    """Use AI to enrich codes with detailed information."""
    new_rows = []
    
    # Process in batches of 20 to avoid token limits
    batch_size = 20
    for i in range(0, len(codes_to_import), batch_size):
        batch = codes_to_import[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        total_batches = (len(codes_to_import) + batch_size - 1) // batch_size
        
        print(f"\n   🔧 Enriching batch {batch_num}/{total_batches} ({len(batch)} codes)...")
        
        # Build prompt
        codes_list = "\n".join([f"- {code}: {desc}" for code, desc in batch])
        
        system_prompt = """You are an expert automotive diagnostician. Enrich these OBD-II codes with detailed technical information.

Return ONLY a valid JSON array with no other text. Use UK English terminology (petrol not gasoline).

Powertrain types: Petrol, Diesel, Petrol Hybrid, Diesel Hybrid, Plug-in Hybrid, Electric, All"""

        prompt = f"""Enrich these standard OBD-II codes with detailed information for {make_id.upper() if make_id != 'generic' else 'all vehicles'}:

{codes_list}

Return a JSON array where each object has:
{{
  "code": "P0xxx",
  "description": "Original short description",
  "detailed_description": "Detailed technical explanation (2-3 sentences)",
  "system": "Engine|Transmission|Fuel System|Emissions|ABS|SRS|Body|Network|HVAC|Hybrid System|EV Battery|etc",
  "severity": "Low|Medium|High|Critical",
  "common_causes": ["Cause 1", "Cause 2", "Cause 3"],
  "symptoms": ["Symptom 1", "Symptom 2"],
  "applicable_models": "All or specific models",
  "applicable_years": "1996+ or specific range",
  "powertrain_type": "Petrol|Diesel|Petrol Hybrid|Diesel Hybrid|Plug-in Hybrid|Electric|All"
}}

Return ONLY the JSON array."""

        response = call_openrouter(prompt, system_prompt, temperature=0.3, manufacturer=make_id)
        
        if not response:
            # Fall back to quick import for this batch
            print(f"   ⚠️  AI failed, using quick import for batch")
            new_rows.extend(quick_import_codes(batch, make_id))
            continue
        
        # Parse JSON
        try:
            json_match = re.search(r'\[[\s\S]*\]', response)
            if json_match:
                enriched = json.loads(json_match.group())
                for item in enriched:
                    item['make_id'] = make_id
                    # Ensure lists are JSON strings
                    if isinstance(item.get('common_causes'), list):
                        item['common_causes'] = json.dumps(item['common_causes'])
                    if isinstance(item.get('symptoms'), list):
                        item['symptoms'] = json.dumps(item['symptoms'])
                new_rows.extend(enriched)
                print(f"   ✅ Enriched {len(enriched)} codes")
            else:
                print(f"   ⚠️  Could not parse response, using quick import")
                new_rows.extend(quick_import_codes(batch, make_id))
        except json.JSONDecodeError:
            print(f"   ⚠️  JSON parse error, using quick import")
            new_rows.extend(quick_import_codes(batch, make_id))
    
    return new_rows


def import_scraped_dtc_codes(df: pd.DataFrame, input_path: Path, enrich: bool = True, update_existing: bool = False) -> pd.DataFrame:
    """
    Import DTC codes from a scraped CSV file (produced by scrape_dtc.py).
    
    The scraped CSV should have columns: code, description, source_url, manufacturer
    OR the prepared format: code, make_id, description, ...
    
    Args:
        df: Existing DTC codes DataFrame
        input_path: Path to the scraped CSV file
        enrich: Whether to use AI to enrich the codes with detailed info
        update_existing: Whether to update existing codes if scraped description differs
    
    Returns:
        Updated DataFrame with merged codes
    """
    print(f"\n" + "="*70)
    print("📥 IMPORTING SCRAPED DTC CODES")
    print("="*70)
    
    # Read the scraped CSV
    scraped_df = pd.read_csv(input_path)
    print(f"   📂 Loaded {len(scraped_df)} codes from {input_path.name}")
    
    # Detect format and normalize column names
    if 'manufacturer' in scraped_df.columns and 'make_id' not in scraped_df.columns:
        scraped_df = scraped_df.rename(columns={'manufacturer': 'make_id'})
    
    if 'make_id' not in scraped_df.columns:
        print("   ❌ Error: CSV must have 'make_id' or 'manufacturer' column")
        return df
    
    if 'code' not in scraped_df.columns or 'description' not in scraped_df.columns:
        print("   ❌ Error: CSV must have 'code' and 'description' columns")
        return df
    
    # Get manufacturer from the scraped data
    make_id = scraped_df['make_id'].iloc[0].lower()
    print(f"   🏭 Manufacturer: {make_id}")
    
    # Build lookup for existing codes
    existing_keys = {}
    for idx, row in df.iterrows():
        key = (row['code'].upper(), row['make_id'].lower())
        existing_keys[key] = idx
    
    new_codes = []
    codes_to_update = []
    skipped_codes = 0
    
    for _, row in scraped_df.iterrows():
        key = (row['code'].upper(), row['make_id'].lower())
        scraped_desc = row['description']
        
        if key not in existing_keys:
            # New code - add it
            new_codes.append((row['code'].upper(), scraped_desc))
        else:
            # Existing code - check if we should update
            if update_existing:
                existing_idx = existing_keys[key]
                existing_desc = df.loc[existing_idx, 'description']
                
                # Update if scraped description is longer or significantly different
                if len(scraped_desc) > len(existing_desc) * 1.2:  # 20% longer
                    codes_to_update.append((existing_idx, row['code'].upper(), scraped_desc))
                else:
                    skipped_codes += 1
            else:
                skipped_codes += 1
    
    print(f"\n   📊 Summary:")
    print(f"      New codes to add:    {len(new_codes)}")
    print(f"      Codes to update:     {len(codes_to_update)}")
    print(f"      Skipped (unchanged): {skipped_codes}")
    
    if not new_codes and not codes_to_update:
        print("   ✅ No changes to make")
        return df
    
    # Category breakdown for new codes
    if new_codes:
        categories = {}
        for code, _ in new_codes:
            if len(code) >= 2:
                prefix = code[:2].upper()
                categories[prefix] = categories.get(prefix, 0) + 1
        
        print(f"\n   New codes by category:")
        for prefix, count in sorted(categories.items()):
            category_name = DTC_CATEGORIES.get(prefix, "Unknown")
            print(f"      {prefix}xxx: {count} codes ({category_name})")
    
    # Update existing codes (just update description, keep other fields)
    if codes_to_update:
        print(f"\n   📝 Updating {len(codes_to_update)} existing codes with better descriptions...")
        for existing_idx, code, new_desc in codes_to_update:
            old_desc = df.loc[existing_idx, 'description']
            df.loc[existing_idx, 'description'] = new_desc
            print(f"      {code}: '{old_desc[:40]}...' → '{new_desc[:40]}...'")
        stats.codes_updated += len(codes_to_update)
    
    # Import new codes
    if new_codes:
        if enrich:
            print(f"\n   🧠 Using AI to enrich {len(new_codes)} new codes...")
            new_rows = enrich_codes_with_ai(new_codes, make_id)
        else:
            print(f"\n   📋 Quick import without AI enrichment...")
            new_rows = quick_import_codes(new_codes, make_id)
        
        # Add to DataFrame
        if new_rows:
            new_df = pd.DataFrame(new_rows)
            df = pd.concat([df, new_df], ignore_index=True)
            
            # Track stats
            stats.codes_added += len(new_rows)
            stats.add_codes(make_id, len(new_rows))
            
            print(f"\n   ✅ Added {len(new_rows)} new codes for {make_id}")
    
    # Sort by code
    df = df.sort_values(['make_id', 'code']).reset_index(drop=True)
    
    return df


def print_analysis(df: pd.DataFrame):
    """Print detailed coverage analysis."""
    analysis = analyze_dtc_coverage(df)
    gaps = identify_gaps(df)
    
    print("\n" + "="*70)
    print("📊 DTC CODE COVERAGE ANALYSIS")
    print("="*70)
    
    print(f"\n📈 Total Codes in Database: {analysis['total_codes']}")
    print(f"📚 Standard OBD-II Reference: {analysis['total_reference_codes']:,} codes available")
    
    # Category breakdown with reference comparison
    print("\n📁 By Category (yours vs reference):")
    all_categories = set(analysis['categories'].keys()) | set(analysis['reference_coverage'].keys())
    for prefix in sorted(all_categories):
        yours = analysis['categories'].get(prefix, 0)
        ref = analysis['reference_coverage'].get(prefix, 0)
        category_name = DTC_CATEGORIES.get(prefix, "Unknown")
        if ref > 0:
            coverage_pct = (yours / ref * 100) if ref > 0 else 0
            print(f"   {prefix}xxx: {yours:4} / {ref:4} ({coverage_pct:5.1f}%) - {category_name}")
        else:
            print(f"   {prefix}xxx: {yours:4} codes - {category_name}")
    
    # Manufacturer breakdown
    print("\n🏭 By Manufacturer:")
    print(f"   {'Make':<15} {'Codes':>6} {'Ref':>5} {'Categories':<30} {'Powertrains'}")
    print(f"   {'-'*15} {'-'*6} {'-'*5} {'-'*30} {'-'*20}")
    for make_id, data in sorted(analysis['manufacturers'].items(), key=lambda x: -x[1]['count']):
        categories_str = ", ".join([f"{k}:{v}" for k, v in sorted(data['categories'].items())])[:30]
        powertrains_str = ", ".join(data.get('powertrain_types', []))[:20]
        ref_covered = data.get('reference_codes_covered', 0)
        print(f"   {make_id:<15} {data['count']:>6} {ref_covered:>5} {categories_str:<30} {powertrains_str}")
    
    # Gaps
    if gaps['low_coverage_manufacturers']:
        print("\n⚠️  Low Coverage (need more codes):")
        for gap in gaps['low_coverage_manufacturers']:
            deficit = gap.get('deficit', gap.get('count', 0))
            print(f"   {gap['make_id']:15} has {gap['count']:3} codes, needs ~{deficit} more")
    
    if gaps['missing_categories']:
        print("\n⚠️  Missing Categories:")
        for gap in gaps['missing_categories']:
            print(f"   {gap['make_id']:15} missing: {', '.join(gap['missing'])}")
    
    if gaps['missing_powertrain_types']:
        print("\n⚠️  Missing Powertrain Types:")
        for gap in gaps['missing_powertrain_types']:
            missing_str = ', '.join(gap['missing'])
            has_str = ', '.join(gap.get('has', [])) or 'None'
            print(f"   {gap['make_id']:15} missing: {missing_str}")
            print(f"   {'':15} has: {has_str}")
    
    # Reference code suggestions
    if REFERENCE_CODES:
        print("\n💡 REFERENCE CODE SUGGESTIONS:")
        # Find most common standard codes not yet assigned to any manufacturer
        all_assigned = set(df['code'].str.upper())
        unassigned_standard = set(REFERENCE_CODES.keys()) - all_assigned
        
        # Group by category
        unassigned_by_category = {}
        for code in unassigned_standard:
            if len(code) >= 2:
                prefix = code[:2].upper()
                unassigned_by_category[prefix] = unassigned_by_category.get(prefix, 0) + 1
        
        print(f"   {len(unassigned_standard):,} standard codes not yet in database:")
        for prefix, count in sorted(unassigned_by_category.items(), key=lambda x: -x[1])[:8]:
            category_name = DTC_CATEGORIES.get(prefix, "Unknown")
            print(f"      {prefix}xxx: {count:4} codes available ({category_name})")


def smart_analyze_with_ai(df: pd.DataFrame, manufacturer: str = None):
    """Use AI to provide intelligent gap analysis and recommendations."""
    print("\n" + "="*70)
    print("🧠 AI-POWERED GAP ANALYSIS")
    print("="*70)
    
    # Gather context
    analysis = analyze_dtc_coverage(df)
    gaps = identify_gaps(df, manufacturer)
    
    # Load reference codes
    load_reference_codes()
    
    # Get the codes currently in database for this manufacturer
    if manufacturer:
        existing_codes = set(df[df['make_id'] == manufacturer]['code'].str.upper())
    else:
        existing_codes = set(df['code'].str.upper())
    
    # Find MISSING reference codes (standard codes not yet in database)
    missing_reference_codes = set(REFERENCE_CODES.keys()) - existing_codes
    
    # Organize missing reference codes by category
    missing_by_category = {}
    for code in missing_reference_codes:
        if len(code) >= 2:
            prefix = code[:2].upper()
            if prefix not in missing_by_category:
                missing_by_category[prefix] = []
            missing_by_category[prefix].append(f"{code}: {REFERENCE_CODES[code][:80]}")
    
    # Build a sample of key missing codes (prioritize safety-critical)
    priority_prefixes = ['B0', 'C0', 'U0', 'P0']  # Generic codes are standard
    sample_missing = []
    for prefix in priority_prefixes:
        if prefix in missing_by_category:
            sample_missing.extend(missing_by_category[prefix][:10])  # Top 10 per category
    
    # Add some manufacturer-specific if we have room
    for prefix in ['B1', 'C1', 'P1', 'U1']:
        if prefix in missing_by_category and len(sample_missing) < 60:
            sample_missing.extend(missing_by_category[prefix][:5])
    
    # Build context for AI
    if manufacturer:
        make_data = analysis['manufacturers'].get(manufacturer, {})
        
        # Get actual existing codes for this manufacturer (sample)
        existing_sample = sorted(list(existing_codes))[:30]
        
        context = f"""
Manufacturer: {manufacturer.upper()}
Current codes in database: {make_data.get('count', 0)}
Categories covered: {make_data.get('categories', {})}
Powertrain types present: {make_data.get('powertrain_types', [])}
Expected powertrains for this make: {MANUFACTURER_POWERTRAINS.get(manufacturer, MANUFACTURER_POWERTRAINS['default'])}

EXISTING CODES SAMPLE (already in database):
{', '.join(existing_sample)}

STANDARD OBD-II REFERENCE DATABASE:
Total available: {len(REFERENCE_CODES):,} standard codes
Already covered: {len(existing_codes)} codes
MISSING standard codes: {len(missing_reference_codes):,}

MISSING BY CATEGORY:
{chr(10).join([f"  {cat}: {len(codes)} missing" for cat, codes in sorted(missing_by_category.items())])}

KEY MISSING STANDARD CODES (sample):
{chr(10).join(sample_missing[:40])}
"""
    else:
        context = f"""
Total manufacturers: {len(analysis['manufacturers'])}
Total codes in database: {analysis['total_codes']}

STANDARD OBD-II REFERENCE DATABASE:
Total available: {len(REFERENCE_CODES):,} standard codes
Total missing: {len(missing_reference_codes):,}

Missing by category:
{chr(10).join([f"  {cat}: {len(codes)} missing" for cat, codes in sorted(missing_by_category.items())])}

Categories in database: {analysis['categories']}
Low coverage manufacturers: {[g['make_id'] for g in gaps['low_coverage_manufacturers']]}
Missing powertrains: {[(g['make_id'], g['missing']) for g in gaps['missing_powertrain_types']]}

KEY MISSING STANDARD CODES (prioritized sample):
{chr(10).join(sample_missing[:50])}
"""
    
    system_prompt = """You are an expert automotive diagnostician helping prioritize DTC code database improvements.

You have access to the standard OBD-II reference database. Use this knowledge to:
1. Recommend which standard codes to import (generic codes work across all vehicles)
2. Identify manufacturer-specific gaps that need AI generation
3. Prioritize safety-critical systems (airbags, brakes, steering, fuel)

Provide actionable, specific recommendations based on:
- Safety-critical codes (brakes, steering, airbags, fuel systems)
- Common failure patterns by manufacturer
- UK-market relevance (diesels important, hybrids/EVs growing)
- Diagnostic workflow efficiency

Be concise and practical. Format as a prioritized action list."""

    prompt = f"""Analyze this DTC code coverage and recommend improvements:

{context}

Provide:
1. IMMEDIATE IMPORTS - Which standard reference codes should be imported now (list specific codes)
2. GENERATION NEEDED - What manufacturer-specific codes need AI generation (P1xxx, B1xxx etc)
3. SAFETY PRIORITIES - Any critical safety codes missing
4. POWERTRAIN GAPS - Missing diesel/hybrid/EV codes for UK market
5. QUICK WINS - Low effort, high value additions

Be specific about actual code numbers from the reference database where applicable."""

    print("\n   🔍 Analyzing with AI (including reference database)...")
    response = call_openrouter(prompt, system_prompt, temperature=0.4, manufacturer=manufacturer or 'analysis')
    
    if response:
        print("\n" + "="*70)
        print("📋 AI RECOMMENDATIONS")
        print("="*70)
        print(response)
    else:
        print("   ❌ AI analysis failed")


def main():
    parser = argparse.ArgumentParser(
        description="Fill gaps in DTC code database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # FREE (no API cost):
    python fill_dtc_gaps.py --analyze                     # Show coverage analysis
    python fill_dtc_gaps.py --cleanup                     # Normalize powertrain data
    python fill_dtc_gaps.py --import-standard             # Quick import to 'generic'
    python fill_dtc_gaps.py --import-standard -m toyota   # Quick import for Toyota
    python fill_dtc_gaps.py --import-generic-all          # Import ALL safe generic codes (P0/B0/C0/U0)
    
    # IMPORT FROM SCRAPED FILES:
    python fill_dtc_gaps.py --input output/scraped/scraped_honda_dtc.csv              # Import + AI enrich
    python fill_dtc_gaps.py --input output/scraped/scraped_honda_dtc.csv --merge-only # Import without AI
    
    # USES AI (costs API):
    python fill_dtc_gaps.py --smart-analyze               # AI recommendations
    python fill_dtc_gaps.py --smart-analyze -m bmw        # AI analysis for BMW
    python fill_dtc_gaps.py --import-standard --enrich    # Import + AI enrichment
    python fill_dtc_gaps.py --manufacturer toyota         # Generate new codes
    python fill_dtc_gaps.py --all                         # Generate for all (fixed targets)
    python fill_dtc_gaps.py --smart-fill                  # AI sets optimal targets per manufacturer
    python fill_dtc_gaps.py -m bmw --powertrain Diesel    # Diesel-specific codes
    python fill_dtc_gaps.py --smart-import --all          # Smart import ALL codes to ALL manufacturers
    python fill_dtc_gaps.py --smart-import -m honda       # Smart import for Honda only
    python fill_dtc_gaps.py --enrich-existing --all       # Enrich existing basic codes
    python fill_dtc_gaps.py --enrich-existing -m ford     # Enrich Ford's basic codes

Workflow with scraper:
    1. python scrape_dtc.py --url <url> --manufacturer <name>    # Scrape codes
    2. python fill_dtc_gaps.py --input output/scraped/<file>.csv # Import & enrich
    3. python merge_to_json.py                                   # Update app data

Environment Variables:
    OPENROUTER_API_KEY      Required for AI features
    DTC_FILLER_MODEL        Model (default: google/gemini-2.0-flash-001)
        """
    )
    
    parser.add_argument('--analyze', action='store_true',
                       help='Analyze coverage without filling gaps (free)')
    parser.add_argument('--smart-analyze', action='store_true',
                       help='AI-powered gap analysis with recommendations (costs API)')
    parser.add_argument('--manufacturer', '-m', type=str,
                       help='Fill gaps for specific manufacturer')
    parser.add_argument('--country', '-c', type=str,
                       help='Fill gaps for all manufacturers from a country')
    parser.add_argument('--all', '-a', action='store_true',
                       help='Fill gaps for all manufacturers (uses fixed target counts)')
    parser.add_argument('--smart-fill', action='store_true',
                       help='AI determines optimal target counts per manufacturer')
    parser.add_argument('--code-range', type=str,
                       help='Fill specific code range (e.g., P0xxx, P1xxx, B1xxx)')
    parser.add_argument('--powertrain', '-p', type=str,
                       choices=['Petrol', 'Diesel', 'Petrol Hybrid', 'Diesel Hybrid', 'Plug-in Hybrid', 'Electric'],
                       help='Focus on specific powertrain type')
    parser.add_argument('--count', '-n', type=int, default=None,
                       help='Target number of new codes per manufacturer')
    parser.add_argument('--model', type=str,
                       help='Override model (or set DTC_FILLER_MODEL env var)')
    parser.add_argument('--import-standard', action='store_true',
                       help='Import standard OBD-II codes from reference database')
    parser.add_argument('--import-generic-all', action='store_true',
                       help='Import ALL safe generic codes (P0/B0/C0/U0) - FREE')
    parser.add_argument('--enrich', action='store_true',
                       help='Use AI to enrich imported codes with detailed info (costs API)')
    parser.add_argument('--import-max', type=int, default=100,
                       help='Maximum standard codes to import (default: 100)')
    parser.add_argument('--smart-import', action='store_true',
                       help='Smart import: AI identifies which manufacturer-specific codes (P1xxx etc.) belong to which manufacturer')
    parser.add_argument('--enrich-existing', action='store_true',
                       help='Enrich existing codes that have basic/minimal descriptions with AI')
    parser.add_argument('--cleanup', action='store_true',
                       help='Cleanup/normalize powertrain data (Gasoline→Petrol, fix combined types)')
    parser.add_argument('--batch', type=str,
                       help='Comma-separated list of manufacturers for batch processing')
    parser.add_argument('--input', '-i', type=str,
                       help='Import and enrich DTC codes from a scraped CSV file (from scrape_dtc.py)')
    parser.add_argument('--merge-only', action='store_true',
                       help='With --input: just merge scraped codes without AI enrichment')
    parser.add_argument('--update-existing', action='store_true',
                       help='With --input: update existing codes if scraped description is longer/different')
    
    args = parser.parse_args()
    
    # Override model if specified
    global DTC_FILLER_MODEL
    if args.model:
        DTC_FILLER_MODEL = args.model
    
    print("="*60)
    print("🔧 DTC CODE GAP FILLER")
    print("="*60)
    print(f"📡 Model: {DTC_FILLER_MODEL}")
    
    # Load existing codes
    df = load_existing_dtc_codes()
    
    # Analyze only?
    if args.analyze:
        print_analysis(df)
        return
    
    # Smart analyze with AI?
    if args.smart_analyze:
        print_analysis(df)
        smart_analyze_with_ai(df, args.manufacturer)
        stats.print_summary()
        return
    
    # No action specified?
    if not any([args.manufacturer, args.country, args.all, args.smart_fill, args.code_range, args.import_standard, args.import_generic_all, args.smart_import, args.batch, args.enrich_existing, args.cleanup, args.input]):
        print("\n⚠️  No action specified. Use --analyze to see coverage, or specify:")
        print("   --manufacturer <name>    Fill gaps for one manufacturer")
        print("   --country <name>         Fill gaps for country's manufacturers")
        print("   --all                    Fill all gaps (fixed targets)")
        print("   --smart-fill             AI determines optimal targets per manufacturer")
        print("   --smart-import           AI classifies manufacturer-specific codes")
        print("   --enrich-existing        Enrich codes with basic descriptions")
        print("   --code-range <range>     Fill specific code range")
        print("   --import-standard        Import standard OBD-II codes (limited)")
        print("   --import-generic-all     Import ALL generic codes P0/B0/C0/U0 (FREE)")
        print("   --input <file>           Import from scraped CSV file")
        print("\nRun with --help for more options.")
        return
    
    # Import from scraped CSV file
    if args.input:
        input_path = Path(args.input)
        if not input_path.exists():
            print(f"\n❌ Input file not found: {input_path}")
            return
        
        print(f"\n📂 Importing from scraped file: {input_path}")
        df = import_scraped_dtc_codes(df, input_path, enrich=not args.merge_only, update_existing=args.update_existing)
        save_dtc_codes(df)
        stats.print_summary()
        print("\n✅ Done! Run 'python merge_to_json.py' to update the main database.")
        return
    
    # Cleanup powertrain data
    if args.cleanup:
        df = cleanup_powertrain_data(df, remove_invalid_codes=True)
        save_dtc_codes(df, also_to_assets=True)  # Save to both output AND assets
        stats.print_summary()
        print("\n✅ Cleanup complete! Both output and assets files updated.")
        return
    
    # Show initial analysis
    print_analysis(df)
    
    # Enrich existing codes with basic descriptions
    if args.enrich_existing:
        # Determine which manufacturers to process
        if args.batch:
            manufacturers = [m.strip().lower() for m in args.batch.split(',')]
        elif args.manufacturer:
            manufacturers = [args.manufacturer.lower()]
        elif args.all:
            manufacturers = None  # All manufacturers
        else:
            print("\n⚠️  --enrich-existing requires: -m <manufacturer>, --batch '<list>', or --all")
            print("   Examples:")
            print("     --enrich-existing -m ford")
            print("     --enrich-existing --batch 'ford,volvo,mazda'")
            print("     --enrich-existing --all")
            return
        
        df = enrich_existing_codes(df, manufacturers)
        save_dtc_codes(df)
        stats.print_summary()
        print("\n✅ Done! Run 'python merge_to_json.py' to update the main database.")
        return
    
    # Import ALL generic codes (FREE option)
    if args.import_generic_all:
        df = import_all_generic_codes(df)
        save_dtc_codes(df)
        stats.print_summary()
        print("\n✅ Done! Run 'python merge_to_json.py' to update the main database.")
        return
    
    # Smart import: AI classifies manufacturer-specific codes (ONE PASS)
    if args.smart_import:
        # Determine which manufacturers to process
        if args.batch:
            manufacturers = [m.strip().lower() for m in args.batch.split(',')]
        elif args.manufacturer:
            manufacturers = [args.manufacturer.lower()]
        elif args.all:
            manufacturers = list(MANUFACTURER_KEYWORDS.keys())
        else:
            print("\n⚠️  --smart-import requires: -m <manufacturer>, --batch '<list>', or --all")
            print("   Examples:")
            print("     --smart-import -m honda")
            print("     --smart-import --batch 'bmw,audi,mercedes-benz'")
            print("     --smart-import --all")
            return
        
        print(f"\n🧠 Smart Import Mode: ONE PASS for {len(manufacturers)} manufacturer(s)")
        
        # ONE call that processes ALL manufacturers at once
        df = smart_import_manufacturer_codes(df, manufacturers, enrich=args.enrich)
        save_dtc_codes(df)
        
        stats.print_summary()
        print("\n✅ Done! Run 'python merge_to_json.py' to update the main database.")
        return
    
    # Import standard codes (limited)
    if args.import_standard:
        df = import_standard_codes(
            df,
            manufacturer=args.manufacturer,  # None = 'generic'
            code_prefix=args.code_range.replace('xxx', '').replace('XXX', '') if args.code_range else None,
            max_codes=args.import_max,
            enrich=args.enrich  # Use AI to enrich if flag set
        )
    
    # Fill gaps based on arguments (uses AI)
    elif args.manufacturer:
        df = fill_gaps_for_manufacturer(
            df, 
            args.manufacturer.lower(),
            target_count=args.count,
            focus_powertrain=args.powertrain
        )
    elif args.country:
        df = fill_gaps_for_country(df, args.country)
    elif args.code_range:
        df = fill_code_range(df, args.code_range, args.manufacturer)
    elif args.smart_fill:
        # AI determines targets
        df = fill_all_gaps(df, use_smart_targets=True)
    elif args.all:
        df = fill_all_gaps(df, use_smart_targets=False)
    
    # Save results
    save_dtc_codes(df)
    
    # Print usage summary
    stats.print_summary()
    
    print("\n✅ Done! Run 'python merge_to_json.py' to update the main database.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted! Saving progress...")
        stats.print_summary()
        sys.exit(1)
