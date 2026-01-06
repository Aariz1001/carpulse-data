"""
Vehicle Data Generator using OpenRouter AI with Web Search

This script uses OpenRouter's API with web search plugin to gather accurate
vehicle information (makes, models, generations, variants) and export to CSV.
"""

import os
import sys
import json
import time
import argparse
import requests
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv
from tqdm import tqdm
from dataclasses import dataclass, field

# Load environment variables
load_dotenv()

# Configuration
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "anthropic/claude-3.5-sonnet")
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Web search cost per search (approximately $4 per 1000 searches = $0.004 per search)
WEB_SEARCH_COST_PER_SEARCH = 0.004

# Output directory
OUTPUT_DIR = Path(__file__).parent / "output"

# Manufacturer batches by country
MANUFACTURERS_BY_COUNTRY = {
    "Germany": ["Mercedes-Benz", "BMW", "Audi", "Volkswagen", "Porsche"],
    "Japan": ["Toyota", "Honda", "Nissan", "Mazda", "Subaru", "Mitsubishi", "Lexus", "Infiniti", "Acura"],
    "USA": ["Ford", "Chevrolet", "GMC", "Dodge", "Jeep", "Cadillac", "Tesla", "Lincoln", "Buick"],
    "South Korea": ["Hyundai", "Kia", "Genesis"],
    "UK": ["Jaguar", "Land Rover", "Mini", "Bentley", "Aston Martin"],
    "Italy": ["Ferrari", "Lamborghini", "Alfa Romeo", "Fiat", "Maserati"],
    "France": ["Peugeot", "Renault", "Citroën"],
    "Sweden": ["Volvo", "Polestar"],
    "Czech Republic": ["Škoda"],
    "India": ["Tata Motors", "Mahindra"],
    "Spain": ["SEAT", "Cupra"],
    "China": ["Geely", "BYD", "NIO", "XPeng"],

}

# All manufacturers list
ALL_MANUFACTURERS = [m for country in MANUFACTURERS_BY_COUNTRY.values() for m in country]

# Supported markets
SUPPORTED_MARKETS = ["Global", "US", "EU", "Asia", "UK", "Australia"]

# Current market setting (set via args)
CURRENT_MARKET = "Global"

# Manufacturer powertrain profiles - what each make commonly offers
# Used for comprehensive DTC code generation
MANUFACTURER_POWERTRAINS = {
    # German premium - all types
    "BMW": ["Petrol", "Diesel", "Hybrid", "PHEV", "EV"],
    "Mercedes-Benz": ["Petrol", "Diesel", "Hybrid", "PHEV", "EV"],
    "Audi": ["Petrol", "Diesel", "Hybrid", "PHEV", "EV"],
    "Volkswagen": ["Petrol", "Diesel", "Hybrid", "PHEV", "EV"],
    "Porsche": ["Petrol", "Hybrid", "PHEV", "EV"],
    
    # Japanese - strong hybrid focus
    "Toyota": ["Petrol", "Diesel", "Hybrid", "PHEV", "EV"],
    "Lexus": ["Petrol", "Hybrid", "PHEV", "EV"],
    "Honda": ["Petrol", "Diesel", "Hybrid", "PHEV", "EV"],
    "Acura": ["Petrol", "Hybrid"],
    "Nissan": ["Petrol", "Diesel", "Hybrid", "EV"],
    "Infiniti": ["Petrol", "Hybrid"],
    "Mazda": ["Petrol", "Diesel", "Hybrid"],
    "Subaru": ["Petrol", "Hybrid"],
    "Mitsubishi": ["Petrol", "Diesel", "PHEV"],
    
    # Korean - EV leaders
    "Hyundai": ["Petrol", "Diesel", "Hybrid", "PHEV", "EV"],
    "Kia": ["Petrol", "Diesel", "Hybrid", "PHEV", "EV"],
    "Genesis": ["Petrol", "Hybrid", "EV"],
    
    # American
    "Ford": ["Petrol", "Diesel", "Hybrid", "PHEV", "EV"],
    "Chevrolet": ["Petrol", "Diesel", "Hybrid", "EV"],
    "GMC": ["Petrol", "Diesel", "EV"],
    "Dodge": ["Petrol"],
    "Jeep": ["Petrol", "Diesel", "PHEV"],
    "Cadillac": ["Petrol", "Hybrid", "EV"],
    "Tesla": ["EV"],
    "Lincoln": ["Petrol", "Hybrid", "PHEV"],
    "Buick": ["Petrol", "Hybrid"],
    
    # UK brands
    "Jaguar": ["Petrol", "Diesel", "Hybrid", "PHEV", "EV"],
    "Land Rover": ["Petrol", "Diesel", "Hybrid", "PHEV"],
    "Mini": ["Petrol", "Diesel", "EV"],
    "Bentley": ["Petrol", "Hybrid", "PHEV"],
    "Aston Martin": ["Petrol", "Hybrid", "PHEV"],
    
    # French
    "Peugeot": ["Petrol", "Diesel", "Hybrid", "PHEV", "EV"],
    "Renault": ["Petrol", "Diesel", "Hybrid", "EV"],
    "Citroën": ["Petrol", "Diesel", "Hybrid", "PHEV", "EV"],
    
    # Swedish
    "Volvo": ["Petrol", "Diesel", "Hybrid", "PHEV", "EV"],
    "Polestar": ["PHEV", "EV"],
    
    # Italian
    "Ferrari": ["Petrol", "Hybrid", "PHEV"],
    "Lamborghini": ["Petrol", "Hybrid", "PHEV"],
    "Alfa Romeo": ["Petrol", "Diesel"],
    "Fiat": ["Petrol", "Diesel", "Hybrid", "EV"],
    "Maserati": ["Petrol", "Hybrid"],
    
    # Other
    "Škoda": ["Petrol", "Diesel", "Hybrid", "PHEV", "EV"],
    "SEAT": ["Petrol", "Diesel", "Hybrid"],
    "Cupra": ["Petrol", "Hybrid", "PHEV", "EV"],
    "Tata Motors": ["Petrol", "Diesel", "EV"],
    "Mahindra": ["Petrol", "Diesel", "EV"],
    "Geely": ["Petrol", "Hybrid", "PHEV", "EV"],
    "BYD": ["Hybrid", "PHEV", "EV"],
    "NIO": ["EV"],
    "XPeng": ["EV"],
}

# DTC code categories to fetch for comprehensive coverage
DTC_CATEGORIES = [
    ("General", "manufacturer-specific P1xxx, B1xxx, C1xxx, U1xxx"),
    ("Engine", "engine management, fuel system, ignition, timing"),
    ("Transmission", "automatic transmission, CVT, DCT, gearbox"),
    ("Emissions", "catalytic converter, oxygen sensors, EGR, EVAP"),
    ("ABS/Stability", "ABS, traction control, stability control, wheel speed"),
    ("Airbag/SRS", "airbag, seatbelt, occupant detection, restraint"),
    ("Body/Comfort", "HVAC, lighting, windows, locks, comfort systems"),
    ("Network", "CAN bus, communication, module communication"),
]


@dataclass
class UsageStats:
    """Track API usage and costs across all calls using OpenRouter's generation API."""
    # Native token counts (actual billing)
    native_prompt_tokens: int = 0
    native_completion_tokens: int = 0
    native_cached_tokens: int = 0
    native_reasoning_tokens: int = 0
    
    # Actual cost in USD from generation API
    total_cost_usd: float = 0.0
    
    # Search tracking
    total_searches: int = 0
    
    # Call tracking
    api_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    estimated_calls: int = 0  # Calls where we used fallback estimation
    
    # Generation IDs for tracking
    generation_ids: list = field(default_factory=list)
    
    # Per-category tracking
    calls_by_type: dict = field(default_factory=lambda: {
        'make': 0, 'models': 0, 'generations': 0, 'variants': 0, 'dtc': 0
    })
    cost_by_type: dict = field(default_factory=lambda: {
        'make': 0.0, 'models': 0.0, 'generations': 0.0, 'variants': 0.0, 'dtc': 0.0
    })
    
    def add_generation_stats(self, gen_stats: dict, call_type: str = None):
        """Add stats from the generation API response (accurate cost tracking)."""
        if not gen_stats:
            return
        
        self.api_calls += 1
        self.successful_calls += 1
        
        # Native token counts (what you're actually billed for)
        # Use 'or 0' to handle None values
        self.native_prompt_tokens += gen_stats.get('native_tokens_prompt') or 0
        self.native_completion_tokens += gen_stats.get('native_tokens_completion') or 0
        self.native_cached_tokens += gen_stats.get('native_tokens_cached') or 0
        self.native_reasoning_tokens += gen_stats.get('native_tokens_reasoning') or 0
        
        # Actual cost in USD (handle None)
        cost = gen_stats.get('total_cost') or 0
        self.total_cost_usd += cost
        
        # Search count (handle None)
        search_count = gen_stats.get('num_search_results') or 0
        if search_count > 0:
            self.total_searches += 1
        
        # Track by type
        if call_type and call_type in self.calls_by_type:
            self.calls_by_type[call_type] += 1
            self.cost_by_type[call_type] += cost
    
    def add_usage_fallback(self, usage_data: dict, call_type: str = None):
        """
        Fallback: Add usage from response when generation API is unavailable.
        Note: This uses normalized token counts, not native - cost is estimated.
        """
        if not usage_data:
            return
        
        self.api_calls += 1
        self.successful_calls += 1
        self.estimated_calls += 1  # Track that this is an estimate
        
        # These are normalized tokens (GPT-4o tokenizer), not native
        # But better than nothing for tracking
        prompt_tokens = usage_data.get('prompt_tokens') or 0
        completion_tokens = usage_data.get('completion_tokens') or 0
        
        self.native_prompt_tokens += prompt_tokens
        self.native_completion_tokens += completion_tokens
        
        # Estimate cost based on model pricing (rough estimate)
        # Claude 3.5 Sonnet: ~$3/1M input, ~$15/1M output
        # This is just an estimate when generation API fails
        estimated_cost = (prompt_tokens * 3 / 1_000_000) + (completion_tokens * 15 / 1_000_000)
        self.total_cost_usd += estimated_cost
        
        # Track by type
        if call_type and call_type in self.calls_by_type:
            self.calls_by_type[call_type] += 1
            self.cost_by_type[call_type] += estimated_cost
    
    def add_failed_call(self):
        """Track a failed API call."""
        self.api_calls += 1
        self.failed_calls += 1
    
    def print_summary(self):
        """Print a detailed cost summary."""
        print("\n" + "="*70)
        print("💰 COST & USAGE SUMMARY (from OpenRouter Generation API)")
        print("="*70)
        
        # API Calls
        print("\n📊 API CALLS")
        print(f"   Total Calls:      {self.api_calls}")
        print(f"   Successful:       {self.successful_calls}")
        print(f"   Failed:           {self.failed_calls}")
        if self.estimated_calls > 0:
            print(f"   Estimated Cost:   {self.estimated_calls} (generation API unavailable)")
        print(f"   Calls with Search: {self.total_searches}")
        
        # Calls by type
        if any(c > 0 for c in self.calls_by_type.values()):
            print("\n   By Category:")
            for call_type, count in self.calls_by_type.items():
                if count > 0:
                    print(f"      {call_type.capitalize():12} {count:5} calls")
        
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
        
        # Cost Breakdown (actual from generation API)
        print("\n💵 ACTUAL COST (from OpenRouter)")
        print(f"   ─────────────────────────────")
        print(f"   TOTAL COST:        ${self.total_cost_usd:.6f}")
        
        # Cost by category
        if any(c > 0 for c in self.cost_by_type.values()):
            print("\n   By Category:")
            for call_type, cost in self.cost_by_type.items():
                if cost > 0:
                    print(f"      {call_type.capitalize():12} ${cost:.6f}")
        
        # Cost estimates
        print("\n📈 PROJECTIONS")
        if self.successful_calls > 0:
            avg_cost_per_call = self.total_cost_usd / self.successful_calls
            print(f"   Avg Cost/Call:     ${avg_cost_per_call:.6f}")
            print(f"   Est. 100 Calls:    ${avg_cost_per_call * 100:.4f}")
            print(f"   Est. 1000 Calls:   ${avg_cost_per_call * 1000:.2f}")
        
        print("\n" + "="*70)
        if self.estimated_calls > 0:
            print(f"⚠️  Note: {self.estimated_calls} calls used estimated costs (generation API unavailable)")
            print(f"   Actual billing may differ. Check your OpenRouter dashboard for exact costs.")
        else:
            print(f"💡 Note: Costs are actual USD from OpenRouter's generation API")
            print(f"   This reflects your real billing, including web search costs")
        print("="*70 + "\n")


# Global usage tracker
usage_tracker = UsageStats()


def check_api_key():
    """Verify API key is configured."""
    if not OPENROUTER_API_KEY or OPENROUTER_API_KEY.startswith("sk-or-v1-your"):
        print("❌ Error: OPENROUTER_API_KEY not configured!")
        print("   1. Copy .env.example to .env")
        print("   2. Add your API key from https://openrouter.ai/keys")
        sys.exit(1)


def fetch_generation_stats(generation_id: str, max_retries: int = 3) -> Optional[dict]:
    """
    Fetch actual cost and usage stats from OpenRouter's generation API.
    This gives accurate billing information including web search costs.
    Retries a few times since stats may not be immediately available.
    """
    for attempt in range(max_retries):
        try:
            response = requests.get(
                f"https://openrouter.ai/api/v1/generation?id={generation_id}",
                headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
                timeout=30
            )
            if response.status_code == 404:
                # Stats not yet available, wait and retry
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
                return None
            response.raise_for_status()
            data = response.json()
            return data.get("data", {})
        except requests.exceptions.HTTPError as e:
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            return None
        except Exception as e:
            return None
    return None


def call_openrouter(prompt: str, use_search: bool = True, call_type: str = None) -> Optional[str]:
    """
    Call OpenRouter API with optional web search.
    
    Args:
        prompt: The prompt to send
        use_search: Whether to enable web search plugin
        call_type: Type of call for tracking ('make', 'models', 'generations', 'variants')
        
    Returns:
        The assistant's response text, or None on error
    """
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/carpulse",  # Optional, for rankings
        "X-Title": "CarPulse Vehicle Database Generator",  # Optional
    }
    
    # Build the request body
    body = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You are a vehicle database expert. Return valid JSON only, no markdown or explanation."
            },
            {
                "role": "user", 
                "content": prompt
            }
        ],
        "temperature": 0.3,  # Low for consistent factual responses
    }
    
    # Web search is DISABLED by default - the model already knows vehicle data!
    # Web search was injecting 50-150K tokens of web content per request.
    # Only enable for very recent data (2025+) if needed.
    # if use_search:
    #     body["plugins"] = [{"id": "web", "max_results": 2}]
    
    try:
        response = requests.post(
            OPENROUTER_API_URL,
            headers=headers,
            json=body,
            timeout=60  # Reduced timeout since no web search
        )
        response.raise_for_status()
        
        data = response.json()
        
        # Get the generation ID for accurate cost tracking
        generation_id = data.get("id")
        cost_tracked = False
        
        if generation_id:
            # Small delay to ensure generation data is available
            time.sleep(1)
            
            # Fetch actual cost from generation API (with retries)
            gen_stats = fetch_generation_stats(generation_id)
            if gen_stats:
                usage_tracker.add_generation_stats(gen_stats, call_type=call_type)
                cost = gen_stats.get('total_cost') or 0
                if cost and cost > 0:
                    print(f"   💵 Cost: ${cost:.6f}")
                cost_tracked = True
        
        # Fallback: use response usage data if generation API failed
        if not cost_tracked and "usage" in data:
            usage_tracker.add_usage_fallback(data["usage"], call_type=call_type)
            print(f"   💵 Cost: ~estimated from tokens")
        
        if "choices" in data and len(data["choices"]) > 0:
            return data["choices"][0]["message"]["content"]
        else:
            print(f"⚠️ Unexpected response format: {data}")
            usage_tracker.add_failed_call()
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"❌ API Error: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"   Response: {e.response.text}")
        usage_tracker.add_failed_call()
        return None


def repair_truncated_json(json_str: str) -> str:
    """
    Attempt to repair truncated JSON by closing open brackets and strings.
    """
    # Remove any trailing incomplete content after the last complete object
    json_str = json_str.strip()
    
    # Track brackets and quotes
    in_string = False
    escape_next = False
    bracket_stack = []
    last_valid_pos = 0
    
    for i, char in enumerate(json_str):
        if escape_next:
            escape_next = False
            continue
            
        if char == '\\':
            escape_next = True
            continue
            
        if char == '"' and not escape_next:
            in_string = not in_string
            continue
            
        if in_string:
            continue
            
        if char in '[{':
            bracket_stack.append(char)
        elif char == ']':
            if bracket_stack and bracket_stack[-1] == '[':
                bracket_stack.pop()
                last_valid_pos = i + 1
        elif char == '}':
            if bracket_stack and bracket_stack[-1] == '{':
                bracket_stack.pop()
                if not bracket_stack or bracket_stack[-1] == '[':
                    last_valid_pos = i + 1
    
    # If we're in the middle of a string or have unclosed brackets, try to repair
    if in_string or bracket_stack:
        # Find the last complete object in an array
        # Look for the last },\n or }\n pattern before truncation
        last_complete = json_str.rfind('},\n')
        if last_complete == -1:
            last_complete = json_str.rfind('}\n')
        if last_complete == -1:
            last_complete = json_str.rfind('},')
        
        if last_complete > 0:
            # Truncate to last complete object and close the array
            json_str = json_str[:last_complete + 1]
            # Close any remaining brackets
            for bracket in reversed(bracket_stack):
                if bracket == '[':
                    json_str += ']'
                elif bracket == '{':
                    json_str += '}'
        else:
            # Can't find a good truncation point, try simple closure
            if in_string:
                json_str += '"'
            for bracket in reversed(bracket_stack):
                if bracket == '[':
                    json_str += ']'
                elif bracket == '{':
                    json_str += '}'
    
    return json_str


def parse_json_response(response: str) -> Optional[dict]:
    """Parse JSON from the AI response, handling potential markdown wrapping and truncation."""
    if not response:
        return None
    
    # Try to extract JSON if wrapped in markdown code blocks
    if "```json" in response:
        start = response.find("```json") + 7
        end = response.find("```", start)
        if end != -1:
            response = response[start:end].strip()
        else:
            # No closing ``` - extract from start to end
            response = response[start:].strip()
    elif "```" in response:
        start = response.find("```") + 3
        end = response.find("```", start)
        if end != -1:
            response = response[start:end].strip()
        else:
            response = response[start:].strip()
    
    # First attempt: try parsing as-is
    try:
        return json.loads(response)
    except json.JSONDecodeError as e:
        print(f"⚠️ JSON truncated, attempting repair...")
        
        # Second attempt: try to repair truncated JSON
        try:
            repaired = repair_truncated_json(response)
            result = json.loads(repaired)
            print(f"   ✅ Successfully repaired JSON (recovered {len(result) if isinstance(result, list) else 1} items)")
            return result
        except json.JSONDecodeError:
            pass
        
        # Third attempt: try to extract complete objects from array
        if response.strip().startswith('['):
            try:
                # Find all complete objects in the array
                objects = []
                depth = 0
                obj_start = None
                in_str = False
                escape = False
                
                for i, c in enumerate(response):
                    if escape:
                        escape = False
                        continue
                    if c == '\\':
                        escape = True
                        continue
                    if c == '"' and not escape:
                        in_str = not in_str
                        continue
                    if in_str:
                        continue
                    if c == '{':
                        if depth == 0:
                            obj_start = i
                        depth += 1
                    elif c == '}':
                        depth -= 1
                        if depth == 0 and obj_start is not None:
                            try:
                                obj = json.loads(response[obj_start:i+1])
                                objects.append(obj)
                            except:
                                pass
                            obj_start = None
                
                if objects:
                    print(f"   ✅ Extracted {len(objects)} complete objects from truncated response")
                    return objects
            except:
                pass
        
        print(f"   ❌ JSON Parse Error: {e}")
        print(f"   Response preview: {response[:300]}...")
        return None


def generate_make_data(manufacturer: str) -> Optional[dict]:
    """Generate data for a single manufacturer."""
    prompt = f'{manufacturer} car manufacturer. Return JSON: {{"id":"lowercase_id","name":"{manufacturer}","country":"","founded":0,"parent_company":null}}'
    response = call_openrouter(prompt, use_search=False, call_type='make')
    return parse_json_response(response)


def generate_dtc_codes_for_make(make_id: str, make_name: str, batch_num: int = 1) -> Optional[list]:
    """Generate manufacturer-specific DTC codes in batches."""
    # Different focus areas for different batches to maximize unique codes
    batch_focus = [
        "P1xxx manufacturer-specific powertrain codes",
        "P0xxx generic powertrain codes commonly seen",
        "B1xxx and B2xxx body control codes",
        "C1xxx chassis and ABS codes",
        "U1xxx and U0xxx network communication codes",
    ]
    focus = batch_focus[(batch_num - 1) % len(batch_focus)]
    
    prompt = f'''List as many {make_name}-specific OBD2 DTC codes as you know, focusing on {focus}.
Include at least 30-50 codes if possible. Be comprehensive.

Return JSON array:
[{{"code":"P1xxx","make_id":"{make_id}","description":"short description","detailed_description":"detailed technical explanation","system":"Engine|Transmission|ABS|SRS|Body|Network|HVAC","severity":"Critical|High|Medium|Low","common_causes":["cause1","cause2"],"symptoms":["symptom1","symptom2"],"applicable_models":"All or specific","applicable_years":"1996+","powertrain_type":"All|Petrol|Diesel|Hybrid|PHEV|EV"}}]'''
    response = call_openrouter(prompt, use_search=False, call_type='dtc')
    return parse_json_response(response)


def generate_dtc_codes_for_system(make_id: str, make_name: str, system: str, system_desc: str = "") -> Optional[list]:
    """Generate DTC codes for a specific vehicle system."""
    desc_hint = f" ({system_desc})" if system_desc else ""
    prompt = f'''List ALL known {make_name} DTC codes related to {system}{desc_hint}.
Include both manufacturer-specific (P1xxx, B1xxx, C1xxx, U1xxx) and commonly seen generic codes.
Be comprehensive - list 30-50 codes if possible.

Return JSON array:
[{{"code":"P1xxx","make_id":"{make_id}","description":"short description","detailed_description":"detailed technical explanation","system":"{system}","severity":"Critical|High|Medium|Low","common_causes":["cause1","cause2"],"symptoms":["symptom1","symptom2"],"applicable_models":"All or specific","applicable_years":"1996+","powertrain_type":"All"}}]'''
    response = call_openrouter(prompt, use_search=False, call_type='dtc')
    return parse_json_response(response)


def generate_dtc_for_powertrain_type(make_id: str, make_name: str, powertrain: str) -> Optional[list]:
    """Generate DTC codes specific to a powertrain type (Petrol, Diesel, Hybrid, PHEV, EV)."""
    # Powertrain-specific hints for better code generation
    powertrain_hints = {
        "Petrol": "ignition coils, spark plugs, fuel injection, knock sensors, catalytic converters, oxygen sensors",
        "Diesel": "glow plugs, DPF, EGR, turbo, injectors, fuel rail pressure, AdBlue/DEF, NOx sensors",
        "Hybrid": "hybrid battery, inverter, motor generator, regenerative braking, HV system, e-CVT",
        "PHEV": "plug-in charging, onboard charger, HV battery, electric motor, charge port, battery management",
        "EV": "high voltage battery, BMS, electric motor, inverter, DC charging, thermal management, range",
    }
    hint = powertrain_hints.get(powertrain, "")
    
    prompt = f'''List ALL known {make_name} {powertrain}-specific DTC codes.
Focus on: {hint}
Include P0Axx (hybrid/EV), P1xxx (manufacturer), and any relevant codes.
Be comprehensive - list 30-50 codes if possible.

Return JSON array:
[{{"code":"P0Axx","make_id":"{make_id}","description":"short description","detailed_description":"detailed technical explanation","system":"Engine|Hybrid System|EV Battery|Charging|etc","severity":"Critical|High|Medium|Low","common_causes":["cause1","cause2"],"symptoms":["symptom1","symptom2"],"applicable_models":"All or specific {powertrain} models","applicable_years":"year range","powertrain_type":"{powertrain}"}}]'''
    response = call_openrouter(prompt, use_search=False, call_type='dtc')
    return parse_json_response(response)


def generate_models_for_make(make_id: str, make_name: str, market: str = "Global") -> Optional[list]:
    """Generate model lineup for a manufacturer."""
    prompt = f'''List all {make_name} car models (2000-2025){" in " + market if market != "Global" else ""}. JSON array:
[{{"id":"{make_id}_modelname","make_id":"{make_id}","name":"Model","body_type":"Sedan|SUV|Hatch","segment":"Compact|Mid|Full|Luxury","market":"{market}"}}]'''
    response = call_openrouter(prompt, use_search=False, call_type='models')
    return parse_json_response(response)


def generate_generations_for_model(make_name: str, model_name: str, model_id: str) -> Optional[list]:
    """Generate generation data for a specific model."""
    prompt = f'''List {make_name} {model_name} generations (2000-2025) with chassis codes. JSON array:
[{{"id":"{model_id}_code","model_id":"{model_id}","name":"W205/G20/etc","start_year":2014,"end_year":2021,"facelift_year":null,"platform":""}}]'''
    response = call_openrouter(prompt, use_search=False, call_type='generations')
    return parse_json_response(response)


def generate_variants_for_generation(
    make_name: str, 
    model_name: str, 
    generation_name: str,
    generation_id: str,
    market: str = "Global"
) -> Optional[list]:
    """Generate variant/engine data for a specific generation."""
    prompt = f'''List {make_name} {model_name} {generation_name} engine variants{" in " + market if market != "Global" else ""}. JSON array:
[{{"id":"{generation_id}_variant","generation_id":"{generation_id}","name":"320i/2.5L/etc","engine_type":"gasoline|diesel|hybrid|ev","engine_code":"","displacement_cc":2000,"horsepower":200,"torque_nm":300,"transmission":"auto|manual","drive_type":"FWD|RWD|AWD","market":"{market}"}}]'''
    response = call_openrouter(prompt, use_search=False, call_type='variants')
    return parse_json_response(response)


def load_existing_data():
    """Load existing CSV data if available."""
    data = {
        "makes": pd.DataFrame(columns=["id", "name", "country", "founded", "parent_company"]),
        "models": pd.DataFrame(columns=["id", "make_id", "name", "body_type", "segment", "market"]),
        "generations": pd.DataFrame(columns=["id", "model_id", "name", "start_year", "end_year", "facelift_year", "platform"]),
        "variants": pd.DataFrame(columns=["id", "generation_id", "name", "engine_type", "engine_code", "displacement_cc", "horsepower", "torque_nm", "transmission", "drive_type", "market"]),
        "dtc_codes": pd.DataFrame(columns=["code", "make_id", "description", "detailed_description", "system", "severity", "common_causes", "symptoms", "applicable_models", "applicable_years", "powertrain_type"])
    }
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    for key in data.keys():
        filepath = OUTPUT_DIR / f"{key}.csv"
        if filepath.exists():
            data[key] = pd.read_csv(filepath)
            print(f"📂 Loaded {len(data[key])} existing {key}")
    
    return data


def save_data(data: dict):
    """Save all data to CSV files."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    for key, df in data.items():
        filepath = OUTPUT_DIR / f"{key}.csv"
        df.to_csv(filepath, index=False)
        print(f"💾 Saved {len(df)} {key} to {filepath}")


def process_manufacturer(make_name: str, data: dict, skip_existing: bool = True, market: str = "Global", fetch_dtc: bool = False, expand_dtc: bool = False):
    """Process a single manufacturer - get all models, generations, variants, and optionally DTC codes."""
    
    # Check if make already exists
    existing_make = data["makes"][data["makes"]["name"] == make_name]
    
    if not existing_make.empty and skip_existing:
        print(f"⏭️  Skipping {make_name} (already exists)")
        make_id = existing_make.iloc[0]["id"]
    else:
        # Generate make data
        print(f"\n🔍 Fetching {make_name}...")
        make_data = generate_make_data(make_name)
        
        if not make_data:
            print(f"❌ Failed to get data for {make_name}")
            return
        
        make_id = make_data["id"]
        
        # Add to dataframe (or update)
        if existing_make.empty:
            data["makes"] = pd.concat([data["makes"], pd.DataFrame([make_data])], ignore_index=True)
        
        time.sleep(1)  # Rate limiting
    
    # Generate models for this make
    existing_models = data["models"][data["models"]["make_id"] == make_id]
    
    if existing_models.empty or not skip_existing:
        print(f"   📋 Getting models for {make_name} ({market} market)...")
        models = generate_models_for_make(make_id, make_name, market)
        
        if models:
            for model in models:
                # Ensure market field is set
                if "market" not in model:
                    model["market"] = market
                # Check if model already exists
                if model["id"] not in data["models"]["id"].values:
                    data["models"] = pd.concat([data["models"], pd.DataFrame([model])], ignore_index=True)
            print(f"   ✅ Added {len(models)} models")
        
        time.sleep(1)
    
    # Get the models for this make
    make_models = data["models"][data["models"]["make_id"] == make_id]
    
    # Process each model
    for _, model in make_models.iterrows():
        model_id = model["id"]
        model_name = model["name"]
        
        # Check for existing generations
        existing_gens = data["generations"][data["generations"]["model_id"] == model_id]
        
        if existing_gens.empty or not skip_existing:
            print(f"   🔄 Getting generations for {model_name}...")
            generations = generate_generations_for_model(make_name, model_name, model_id)
            
            if generations:
                for gen in generations:
                    if gen["id"] not in data["generations"]["id"].values:
                        data["generations"] = pd.concat([data["generations"], pd.DataFrame([gen])], ignore_index=True)
                print(f"      ✅ Added {len(generations)} generations")
            
            time.sleep(1)
        
        # Get generations for this model
        model_gens = data["generations"][data["generations"]["model_id"] == model_id]
        
        # Process each generation for variants
        for _, gen in model_gens.iterrows():
            gen_id = gen["id"]
            gen_name = gen["name"]
            
            # Check for existing variants
            existing_vars = data["variants"][data["variants"]["generation_id"] == gen_id]
            
            if existing_vars.empty or not skip_existing:
                print(f"      🔧 Getting variants for {model_name} {gen_name}...")
                variants = generate_variants_for_generation(make_name, model_name, gen_name, gen_id, market)
                
                if variants:
                    for var in variants:
                        # Ensure market field is set
                        if "market" not in var:
                            var["market"] = market
                        if var["id"] not in data["variants"]["id"].values:
                            data["variants"] = pd.concat([data["variants"], pd.DataFrame([var])], ignore_index=True)
                    print(f"         ✅ Added {len(variants)} variants")
                
                time.sleep(1)
    
    # Fetch DTC codes if requested
    if fetch_dtc:
        skip_dtc = skip_existing and not expand_dtc
        fetch_comprehensive_dtc_codes(make_id, make_name, data, skip_dtc)


def add_dtc_codes_to_data(codes: list, make_id: str, data: dict) -> int:
    """Helper to add DTC codes to data, handling duplicates and JSON conversion."""
    added = 0
    if not codes:
        return 0
    
    for code in codes:
        # Convert lists to JSON strings for CSV storage
        if isinstance(code.get("common_causes"), list):
            code["common_causes"] = json.dumps(code["common_causes"])
        if isinstance(code.get("symptoms"), list):
            code["symptoms"] = json.dumps(code["symptoms"])
        
        # Check if code already exists for this make
        existing = data["dtc_codes"][
            (data["dtc_codes"]["code"] == code["code"]) & 
            (data["dtc_codes"]["make_id"] == make_id)
        ]
        if existing.empty:
            data["dtc_codes"] = pd.concat([data["dtc_codes"], pd.DataFrame([code])], ignore_index=True)
            added += 1
    
    return added


def fetch_comprehensive_dtc_codes(make_id: str, make_name: str, data: dict, skip_existing: bool = True):
    """Fetch comprehensive DTC codes for a manufacturer - all categories and powertrains."""
    print(f"\n   🔍 Fetching comprehensive DTC codes for {make_name}...")
    
    # Check for existing DTC codes for this make
    existing_dtc = data["dtc_codes"][data["dtc_codes"]["make_id"] == make_id]
    initial_count = len(existing_dtc)
    
    if not existing_dtc.empty and skip_existing:
        print(f"      ⏭️  {make_name} already has {initial_count} DTC codes, skipping...")
        print(f"      💡 Use --expand to add more codes, or --force to regenerate all")
        return
    
    total_added = 0
    
    # PHASE 1: General manufacturer codes (multiple batches)
    print(f"\n      📋 Phase 1: General manufacturer codes...")
    for batch in range(1, 4):  # 3 batches for different code ranges
        print(f"         Batch {batch}/3...")
        codes = generate_dtc_codes_for_make(make_id, make_name, batch_num=batch)
        added = add_dtc_codes_to_data(codes, make_id, data)
        total_added += added
        print(f"         ✅ Added {added} codes")
        time.sleep(1)
    
    # PHASE 2: System-specific codes
    print(f"\n      🔧 Phase 2: System-specific codes...")
    for system_name, system_desc in DTC_CATEGORIES:
        print(f"         {system_name}...")
        codes = generate_dtc_codes_for_system(make_id, make_name, system_name, system_desc)
        added = add_dtc_codes_to_data(codes, make_id, data)
        total_added += added
        print(f"         ✅ Added {added} codes")
        time.sleep(1)
    
    # PHASE 3: Powertrain-specific codes (based on what this manufacturer actually makes)
    powertrains = MANUFACTURER_POWERTRAINS.get(make_name, ["Petrol"])  # Default to Petrol
    print(f"\n      ⚡ Phase 3: Powertrain-specific codes ({', '.join(powertrains)})...")
    
    powertrain_icons = {
        "Petrol": "⛽",
        "Diesel": "🛢️",
        "Hybrid": "🔋",
        "PHEV": "🔌",
        "EV": "⚡",
    }
    
    for powertrain in powertrains:
        icon = powertrain_icons.get(powertrain, "🔧")
        print(f"         {icon} {powertrain}...")
        codes = generate_dtc_for_powertrain_type(make_id, make_name, powertrain)
        added = add_dtc_codes_to_data(codes, make_id, data)
        total_added += added
        print(f"         ✅ Added {added} codes")
        time.sleep(1)
    
    # Summary
    final_count = len(data["dtc_codes"][data["dtc_codes"]["make_id"] == make_id])
    print(f"\n      ✅ DTC Summary for {make_name}:")
    print(f"         Started with: {initial_count} codes")
    print(f"         Added: {total_added} new codes")
    print(f"         Total: {final_count} codes")


def main():
    global CURRENT_MARKET
    
    parser = argparse.ArgumentParser(description="Generate vehicle database using AI with web search")
    parser.add_argument("--mode", choices=["manufacturers", "country", "all"], default="manufacturers",
                        help="Generation mode: by manufacturer batch, by country, or all")
    parser.add_argument("--batch", type=str, 
                        help="Comma-separated list of manufacturers (for 'manufacturers' mode)")
    parser.add_argument("--country", type=str,
                        help="Country name (for 'country' mode)")
    parser.add_argument("--market", type=str, choices=SUPPORTED_MARKETS, default="Global",
                        help="Target market for vehicle specs (Global, US, EU, Asia, UK, Australia)")
    parser.add_argument("--fetch-dtc", action="store_true",
                        help="Also fetch manufacturer-specific DTC codes")
    parser.add_argument("--dtc-only", action="store_true",
                        help="Only fetch DTC codes (skip vehicle data)")
    parser.add_argument("--expand", action="store_true",
                        help="Add MORE DTC codes to existing manufacturers (keeps existing, adds new)")
    parser.add_argument("--skip-existing", action="store_true", default=True,
                        help="Skip manufacturers that already have data")
    parser.add_argument("--force", action="store_true",
                        help="Force regeneration of all data (don't skip existing)")
    
    args = parser.parse_args()
    CURRENT_MARKET = args.market
    
    # Check API key
    check_api_key()
    
    print("🚗 CarPulse Vehicle Data Generator")
    print(f"   Model: {OPENROUTER_MODEL}")
    print(f"   Mode: {args.mode}")
    print(f"   Market: {args.market}")
    if args.fetch_dtc or args.dtc_only:
        print(f"   DTC Codes: {'Only' if args.dtc_only else 'Enabled'}")
    if args.expand:
        print(f"   Mode: EXPAND (adding more codes to existing manufacturers)")
    print()
    
    # Load existing data
    data = load_existing_data()
    skip_existing = not args.force
    expand_mode = args.expand  # Add more codes without skipping existing makes
    
    # Determine which manufacturers to process
    manufacturers = []
    
    if args.mode == "manufacturers":
        if args.batch:
            manufacturers = [m.strip() for m in args.batch.split(",")]
        else:
            # Default batch - first 5 popular manufacturers
            manufacturers = ["Toyota", "Honda", "Ford", "BMW", "Mercedes-Benz"]
            
    elif args.mode == "country":
        country = args.country or "Germany"
        if country in MANUFACTURERS_BY_COUNTRY:
            manufacturers = MANUFACTURERS_BY_COUNTRY[country]
            print(f"🌍 Processing manufacturers from {country}")
        else:
            print(f"❌ Unknown country: {country}")
            print(f"   Available: {', '.join(MANUFACTURERS_BY_COUNTRY.keys())}")
            sys.exit(1)
            
    elif args.mode == "all":
        manufacturers = ALL_MANUFACTURERS
        print(f"🌐 Processing ALL {len(manufacturers)} manufacturers")
    
    print(f"📝 Will process: {', '.join(manufacturers)}")
    print()
    
    # Process each manufacturer
    for i, make in enumerate(manufacturers):
        print(f"\n{'='*60}")
        print(f"[{i+1}/{len(manufacturers)}] Processing {make}")
        print('='*60)
        
        try:
            if args.dtc_only:
                # Only fetch DTC codes - need to get make_id first
                existing_make = data["makes"][data["makes"]["name"] == make]
                if existing_make.empty:
                    print(f"   🔍 Fetching {make} info first...")
                    make_data = generate_make_data(make)
                    if make_data:
                        data["makes"] = pd.concat([data["makes"], pd.DataFrame([make_data])], ignore_index=True)
                        make_id = make_data["id"]
                    else:
                        print(f"   ❌ Failed to get make data")
                        continue
                else:
                    make_id = existing_make.iloc[0]["id"]
                
                # Fetch comprehensive DTC codes using the new function
                # If expand_mode, don't skip even if codes exist
                skip_dtc = skip_existing and not expand_mode
                fetch_comprehensive_dtc_codes(make_id, make, data, skip_existing=skip_dtc)
            else:
                # Full processing
                process_manufacturer(make, data, skip_existing=skip_existing, market=args.market, fetch_dtc=args.fetch_dtc, expand_dtc=expand_mode)
            
            # Save after each manufacturer (incremental)
            save_data(data)
            
        except KeyboardInterrupt:
            print("\n\n⚠️ Interrupted! Saving current progress...")
            save_data(data)
            # Still show cost summary on interrupt
            usage_tracker.print_summary()
            sys.exit(0)
        except Exception as e:
            print(f"❌ Error processing {make}: {e}")
            continue
    
    # Final save
    save_data(data)
    
    print("\n" + "="*60)
    print("✅ Generation Complete!")
    print("="*60)
    print(f"   Makes: {len(data['makes'])}")
    print(f"   Models: {len(data['models'])}")
    print(f"   Generations: {len(data['generations'])}")
    print(f"   Variants: {len(data['variants'])}")
    print(f"   DTC Codes: {len(data['dtc_codes'])}")
    print(f"   Market: {args.market}")
    print(f"\n📁 Output saved to: {OUTPUT_DIR}")
    
    # Print detailed cost summary
    usage_tracker.print_summary()


if __name__ == "__main__":
    main()
