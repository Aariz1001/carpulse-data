"""
CarPulse Data Manager - Streamlit GUI
A web-based interface for managing vehicle and DTC code data.

Run with: streamlit run gui.py
"""

import streamlit as st
import pandas as pd
import json
import subprocess
import sys
import os
from pathlib import Path
from datetime import datetime
import re

# Set page config
st.set_page_config(
    page_title="CarPulse Data Manager",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Paths
SCRIPT_DIR = Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR / "output"
ASSETS_DIR = SCRIPT_DIR.parent.parent / "assets" / "data"

# DTC code pattern
DTC_PATTERN = re.compile(r'^[PBCU][0-3][0-9A-Fa-f]{3}$')


# ============================================================================
# Data Loading Functions
# ============================================================================

@st.cache_data(ttl=60)
def load_dtc_codes():
    """Load DTC codes from CSV."""
    filepath = OUTPUT_DIR / "dtc_codes.csv"
    if filepath.exists():
        df = pd.read_csv(filepath)
        return df
    return pd.DataFrame()


@st.cache_data(ttl=60)
def load_makes():
    """Load makes from CSV."""
    filepath = OUTPUT_DIR / "makes.csv"
    if filepath.exists():
        return pd.read_csv(filepath)
    return pd.DataFrame()


@st.cache_data(ttl=60)
def load_models():
    """Load models from CSV."""
    filepath = OUTPUT_DIR / "models.csv"
    if filepath.exists():
        return pd.read_csv(filepath)
    return pd.DataFrame()


def save_dtc_codes(df):
    """Save DTC codes to CSV."""
    filepath = OUTPUT_DIR / "dtc_codes.csv"
    df.to_csv(filepath, index=False)
    st.cache_data.clear()


def get_make_name(make_id, makes_df):
    """Get make name from ID."""
    if makes_df.empty:
        return make_id
    match = makes_df[makes_df['id'] == make_id]
    if not match.empty:
        return match.iloc[0]['name']
    return make_id


# ============================================================================
# Sidebar Navigation
# ============================================================================

st.sidebar.title("🚗 CarPulse Data Manager")
st.sidebar.markdown("---")

page = st.sidebar.radio(
    "Navigation",
    ["🔍 Search & Browse", "✏️ Edit Codes", "📤 Upload Data", "🔧 Generate", "🌐 Scrape", "📊 Statistics", "⚙️ Settings"],
    label_visibility="collapsed"
)

st.sidebar.markdown("---")

# Quick stats in sidebar
dtc_df = load_dtc_codes()
makes_df = load_makes()

st.sidebar.metric("Total DTC Codes", len(dtc_df))
st.sidebar.metric("Manufacturers", len(makes_df))

if not dtc_df.empty:
    st.sidebar.markdown("**Top Manufacturers:**")
    top_makes = dtc_df['make_id'].value_counts().head(5)
    for make_id, count in top_makes.items():
        name = get_make_name(make_id, makes_df)
        st.sidebar.text(f"  {name}: {count}")


# ============================================================================
# Page: Search & Browse
# ============================================================================

if page == "🔍 Search & Browse":
    st.title("🔍 Search & Browse DTC Codes")
    
    if dtc_df.empty:
        st.warning("No DTC codes loaded. Generate or upload data first.")
    else:
        # Search filters
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            search_query = st.text_input("🔎 Search codes or descriptions", placeholder="e.g., P0420, catalyst, misfire")
        
        with col2:
            # Get unique makes
            make_options = ["All Manufacturers"]
            if not makes_df.empty:
                for make_id in dtc_df['make_id'].unique():
                    name = get_make_name(make_id, makes_df)
                    make_options.append(name)
            selected_make = st.selectbox("Manufacturer", sorted(set(make_options)))
        
        with col3:
            severity_options = ["All Severities"] + list(dtc_df['severity'].dropna().unique())
            selected_severity = st.selectbox("Severity", severity_options)
        
        # Filter data
        filtered_df = dtc_df.copy()
        
        if search_query:
            mask = (
                filtered_df['code'].str.contains(search_query, case=False, na=False) |
                filtered_df['description'].str.contains(search_query, case=False, na=False) |
                filtered_df['detailed_description'].str.contains(search_query, case=False, na=False)
            )
            filtered_df = filtered_df[mask]
        
        if selected_make != "All Manufacturers":
            # Find make_id from name
            make_match = makes_df[makes_df['name'] == selected_make]
            if not make_match.empty:
                make_id = make_match.iloc[0]['id']
                filtered_df = filtered_df[filtered_df['make_id'] == make_id]
        
        if selected_severity != "All Severities":
            filtered_df = filtered_df[filtered_df['severity'] == selected_severity]
        
        st.markdown(f"**Found {len(filtered_df)} codes**")
        
        # Display results
        if not filtered_df.empty:
            # Pagination
            codes_per_page = 20
            total_pages = max(1, len(filtered_df) // codes_per_page + (1 if len(filtered_df) % codes_per_page else 0))
            
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                current_page = st.number_input("Page", min_value=1, max_value=total_pages, value=1)
            
            start_idx = (current_page - 1) * codes_per_page
            end_idx = start_idx + codes_per_page
            page_df = filtered_df.iloc[start_idx:end_idx]
            
            for _, row in page_df.iterrows():
                with st.expander(f"**{row['code']}** - {row.get('description', 'No description')[:80]}"):
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        st.markdown(f"**Description:** {row.get('description', 'N/A')}")
                        st.markdown(f"**Detailed:** {row.get('detailed_description', 'N/A')}")
                        
                        # Parse JSON fields
                        causes = row.get('common_causes', '[]')
                        if isinstance(causes, str) and causes.startswith('['):
                            try:
                                causes_list = json.loads(causes)
                                if causes_list:
                                    st.markdown("**Common Causes:**")
                                    for cause in causes_list[:5]:
                                        st.markdown(f"  • {cause}")
                            except:
                                pass
                        
                        symptoms = row.get('symptoms', '[]')
                        if isinstance(symptoms, str) and symptoms.startswith('['):
                            try:
                                symptoms_list = json.loads(symptoms)
                                if symptoms_list:
                                    st.markdown("**Symptoms:**")
                                    for symptom in symptoms_list[:5]:
                                        st.markdown(f"  • {symptom}")
                            except:
                                pass
                    
                    with col2:
                        make_name = get_make_name(row['make_id'], makes_df)
                        st.markdown(f"**Manufacturer:** {make_name}")
                        st.markdown(f"**System:** {row.get('system', 'N/A')}")
                        
                        severity = row.get('severity', 'Unknown')
                        severity_colors = {
                            'Critical': '🔴',
                            'High': '🟠',
                            'Medium': '🟡',
                            'Low': '🟢',
                            'Info': '🔵'
                        }
                        st.markdown(f"**Severity:** {severity_colors.get(severity, '⚪')} {severity}")
                        st.markdown(f"**Powertrain:** {row.get('powertrain_type', 'All')}")
                        st.markdown(f"**Models:** {row.get('applicable_models', 'All')}")
                        st.markdown(f"**Years:** {row.get('applicable_years', 'N/A')}")


# ============================================================================
# Page: Edit Codes
# ============================================================================

elif page == "✏️ Edit Codes":
    st.title("✏️ Edit DTC Codes")
    
    tab1, tab2, tab3 = st.tabs(["Edit Existing", "Add New Code", "Bulk Edit"])
    
    with tab1:
        st.subheader("Edit Existing Code")
        
        if dtc_df.empty:
            st.warning("No codes to edit.")
        else:
            # Select code to edit
            code_to_edit = st.selectbox(
                "Select code to edit",
                dtc_df['code'].unique(),
                format_func=lambda x: f"{x} - {dtc_df[dtc_df['code'] == x].iloc[0].get('description', '')[:50]}"
            )
            
            if code_to_edit:
                code_row = dtc_df[dtc_df['code'] == code_to_edit].iloc[0]
                idx = dtc_df[dtc_df['code'] == code_to_edit].index[0]
                
                with st.form("edit_form"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        new_description = st.text_input("Description", value=code_row.get('description', ''))
                        new_detailed = st.text_area("Detailed Description", value=code_row.get('detailed_description', ''), height=150)
                        new_system = st.selectbox(
                            "System",
                            ["Engine", "Transmission", "ABS", "SRS", "Body", "Network", "HVAC", "Emissions", "Hybrid System", "EV Battery", "Charging"],
                            index=0 if pd.isna(code_row.get('system')) else ["Engine", "Transmission", "ABS", "SRS", "Body", "Network", "HVAC", "Emissions", "Hybrid System", "EV Battery", "Charging"].index(code_row.get('system')) if code_row.get('system') in ["Engine", "Transmission", "ABS", "SRS", "Body", "Network", "HVAC", "Emissions", "Hybrid System", "EV Battery", "Charging"] else 0
                        )
                    
                    with col2:
                        new_severity = st.selectbox(
                            "Severity",
                            ["Critical", "High", "Medium", "Low", "Info"],
                            index=["Critical", "High", "Medium", "Low", "Info"].index(code_row.get('severity')) if code_row.get('severity') in ["Critical", "High", "Medium", "Low", "Info"] else 2
                        )
                        new_powertrain = st.selectbox(
                            "Powertrain Type",
                            ["All", "Petrol", "Diesel", "Hybrid", "PHEV", "EV"],
                            index=["All", "Petrol", "Diesel", "Hybrid", "PHEV", "EV"].index(code_row.get('powertrain_type')) if code_row.get('powertrain_type') in ["All", "Petrol", "Diesel", "Hybrid", "PHEV", "EV"] else 0
                        )
                        new_models = st.text_input("Applicable Models", value=code_row.get('applicable_models', 'All'))
                        new_years = st.text_input("Applicable Years", value=code_row.get('applicable_years', ''))
                    
                    # Common causes and symptoms as text areas
                    causes_str = code_row.get('common_causes', '[]')
                    if isinstance(causes_str, str) and causes_str.startswith('['):
                        try:
                            causes_list = json.loads(causes_str)
                            causes_text = '\n'.join(causes_list)
                        except:
                            causes_text = causes_str
                    else:
                        causes_text = str(causes_str) if pd.notna(causes_str) else ''
                    
                    new_causes = st.text_area("Common Causes (one per line)", value=causes_text, height=100)
                    
                    symptoms_str = code_row.get('symptoms', '[]')
                    if isinstance(symptoms_str, str) and symptoms_str.startswith('['):
                        try:
                            symptoms_list = json.loads(symptoms_str)
                            symptoms_text = '\n'.join(symptoms_list)
                        except:
                            symptoms_text = symptoms_str
                    else:
                        symptoms_text = str(symptoms_str) if pd.notna(symptoms_str) else ''
                    
                    new_symptoms = st.text_area("Symptoms (one per line)", value=symptoms_text, height=100)
                    
                    submitted = st.form_submit_button("💾 Save Changes", type="primary")
                    
                    if submitted:
                        # Update dataframe
                        dtc_df.at[idx, 'description'] = new_description
                        dtc_df.at[idx, 'detailed_description'] = new_detailed
                        dtc_df.at[idx, 'system'] = new_system
                        dtc_df.at[idx, 'severity'] = new_severity
                        dtc_df.at[idx, 'powertrain_type'] = new_powertrain
                        dtc_df.at[idx, 'applicable_models'] = new_models
                        dtc_df.at[idx, 'applicable_years'] = new_years
                        
                        # Convert causes/symptoms back to JSON
                        causes_list = [c.strip() for c in new_causes.split('\n') if c.strip()]
                        symptoms_list = [s.strip() for s in new_symptoms.split('\n') if s.strip()]
                        dtc_df.at[idx, 'common_causes'] = json.dumps(causes_list)
                        dtc_df.at[idx, 'symptoms'] = json.dumps(symptoms_list)
                        
                        save_dtc_codes(dtc_df)
                        st.success(f"✅ Code {code_to_edit} updated successfully!")
                        st.rerun()
    
    with tab2:
        st.subheader("Add New DTC Code")
        
        with st.form("add_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                new_code = st.text_input("DTC Code", placeholder="P0420")
                
                # Make selection
                make_options = list(makes_df['name'].unique()) if not makes_df.empty else []
                selected_make_name = st.selectbox("Manufacturer", make_options) if make_options else st.text_input("Manufacturer ID")
                
                new_description = st.text_input("Description", placeholder="Catalyst System Efficiency Below Threshold")
                new_detailed = st.text_area("Detailed Description", height=100)
            
            with col2:
                new_system = st.selectbox("System", ["Engine", "Transmission", "ABS", "SRS", "Body", "Network", "HVAC", "Emissions", "Hybrid System", "EV Battery", "Charging"])
                new_severity = st.selectbox("Severity", ["Critical", "High", "Medium", "Low", "Info"], index=2)
                new_powertrain = st.selectbox("Powertrain Type", ["All", "Petrol", "Diesel", "Hybrid", "PHEV", "EV"])
                new_models = st.text_input("Applicable Models", value="All")
                new_years = st.text_input("Applicable Years", placeholder="1996+")
            
            new_causes = st.text_area("Common Causes (one per line)", height=80)
            new_symptoms = st.text_area("Symptoms (one per line)", height=80)
            
            submitted = st.form_submit_button("➕ Add Code", type="primary")
            
            if submitted:
                # Validate code format
                if not DTC_PATTERN.match(new_code.upper()):
                    st.error("❌ Invalid DTC code format. Must be like P0420, B1234, C0100, U0001")
                elif new_code.upper() in dtc_df['code'].values:
                    st.error(f"❌ Code {new_code.upper()} already exists")
                else:
                    # Get make_id
                    if not makes_df.empty and selected_make_name in makes_df['name'].values:
                        make_id = makes_df[makes_df['name'] == selected_make_name].iloc[0]['id']
                    else:
                        make_id = selected_make_name.lower().replace(' ', '_')
                    
                    # Create new row
                    new_row = {
                        'code': new_code.upper(),
                        'make_id': make_id,
                        'description': new_description,
                        'detailed_description': new_detailed,
                        'system': new_system,
                        'severity': new_severity,
                        'common_causes': json.dumps([c.strip() for c in new_causes.split('\n') if c.strip()]),
                        'symptoms': json.dumps([s.strip() for s in new_symptoms.split('\n') if s.strip()]),
                        'applicable_models': new_models,
                        'applicable_years': new_years,
                        'powertrain_type': new_powertrain
                    }
                    
                    dtc_df = pd.concat([dtc_df, pd.DataFrame([new_row])], ignore_index=True)
                    save_dtc_codes(dtc_df)
                    st.success(f"✅ Code {new_code.upper()} added successfully!")
                    st.rerun()
    
    with tab3:
        st.subheader("Bulk Edit (Table View)")
        st.warning("⚠️ Be careful with bulk edits - changes are saved immediately!")
        
        if not dtc_df.empty:
            # Filter for bulk edit
            make_filter = st.selectbox("Filter by Manufacturer", ["All"] + list(makes_df['name'].unique()) if not makes_df.empty else ["All"])
            
            edit_df = dtc_df.copy()
            if make_filter != "All" and not makes_df.empty:
                make_id = makes_df[makes_df['name'] == make_filter].iloc[0]['id']
                edit_df = edit_df[edit_df['make_id'] == make_id]
            
            # Show editable table (limited columns for clarity)
            edited_df = st.data_editor(
                edit_df[['code', 'description', 'system', 'severity', 'powertrain_type']].head(50),
                use_container_width=True,
                num_rows="dynamic"
            )
            
            if st.button("💾 Save Bulk Changes"):
                st.info("Bulk save not implemented yet - use individual edit for now")


# ============================================================================
# Page: Upload Data
# ============================================================================

elif page == "📤 Upload Data":
    st.title("📤 Upload Data")
    
    tab1, tab2 = st.tabs(["Upload CSV", "Import from JSON"])
    
    with tab1:
        st.subheader("Upload DTC Codes CSV")
        
        st.markdown("""
        Upload a CSV file with DTC codes. Required columns:
        - `code` - The DTC code (e.g., P0420)
        - `description` - Short description
        
        Optional columns: `detailed_description`, `system`, `severity`, `common_causes`, `symptoms`, `applicable_models`, `applicable_years`, `powertrain_type`
        """)
        
        uploaded_file = st.file_uploader("Choose a CSV file", type="csv")
        
        if uploaded_file:
            try:
                upload_df = pd.read_csv(uploaded_file)
                st.success(f"✅ Loaded {len(upload_df)} rows")
                
                # Preview
                st.subheader("Preview")
                st.dataframe(upload_df.head(20))
                
                # Validate
                if 'code' not in upload_df.columns:
                    st.error("❌ Missing required column: 'code'")
                else:
                    # Check for valid codes
                    invalid_codes = upload_df[~upload_df['code'].str.upper().str.match(r'^[PBCU][0-3][0-9A-Fa-f]{3}$', na=False)]
                    if not invalid_codes.empty:
                        st.warning(f"⚠️ Found {len(invalid_codes)} invalid codes (will be skipped)")
                        st.dataframe(invalid_codes[['code']].head(10))
                    
                    # Manufacturer selection
                    st.subheader("Import Settings")
                    
                    if 'make_id' in upload_df.columns or 'manufacturer' in upload_df.columns:
                        use_file_make = st.checkbox("Use manufacturer from file", value=True)
                    else:
                        use_file_make = False
                    
                    if not use_file_make:
                        make_options = list(makes_df['name'].unique()) if not makes_df.empty else []
                        if make_options:
                            target_make = st.selectbox("Assign to Manufacturer", make_options)
                            target_make_id = makes_df[makes_df['name'] == target_make].iloc[0]['id']
                        else:
                            target_make_id = st.text_input("Manufacturer ID", placeholder="manufacturer_name")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        enrich_with_ai = st.checkbox("🤖 Enrich with AI (fills gaps)", value=False)
                    with col2:
                        skip_duplicates = st.checkbox("Skip existing codes", value=True)
                    
                    if st.button("📥 Import Codes", type="primary"):
                        # Process import
                        valid_df = upload_df[upload_df['code'].str.upper().str.match(r'^[PBCU][0-3][0-9A-Fa-f]{3}$', na=False)].copy()
                        valid_df['code'] = valid_df['code'].str.upper()
                        
                        # Assign make_id
                        if not use_file_make:
                            valid_df['make_id'] = target_make_id
                        elif 'manufacturer' in valid_df.columns and 'make_id' not in valid_df.columns:
                            valid_df['make_id'] = valid_df['manufacturer'].str.lower().str.replace(' ', '_')
                        
                        # Remove duplicates
                        added = 0
                        skipped = 0
                        
                        for _, row in valid_df.iterrows():
                            if skip_duplicates:
                                exists = dtc_df[
                                    (dtc_df['code'] == row['code']) & 
                                    (dtc_df['make_id'] == row.get('make_id', ''))
                                ]
                                if not exists.empty:
                                    skipped += 1
                                    continue
                            
                            # Add missing columns
                            new_row = {
                                'code': row['code'],
                                'make_id': row.get('make_id', target_make_id if not use_file_make else ''),
                                'description': row.get('description', ''),
                                'detailed_description': row.get('detailed_description', ''),
                                'system': row.get('system', ''),
                                'severity': row.get('severity', 'Medium'),
                                'common_causes': row.get('common_causes', '[]'),
                                'symptoms': row.get('symptoms', '[]'),
                                'applicable_models': row.get('applicable_models', 'All'),
                                'applicable_years': row.get('applicable_years', ''),
                                'powertrain_type': row.get('powertrain_type', 'All')
                            }
                            
                            dtc_df = pd.concat([dtc_df, pd.DataFrame([new_row])], ignore_index=True)
                            added += 1
                        
                        save_dtc_codes(dtc_df)
                        st.success(f"✅ Imported {added} codes ({skipped} duplicates skipped)")
                        
                        if enrich_with_ai:
                            st.info("🤖 AI enrichment would run here (run fill_dtc_gaps.py manually for now)")
                        
                        st.rerun()
                        
            except Exception as e:
                st.error(f"❌ Error loading file: {e}")
    
    with tab2:
        st.subheader("Import from JSON")
        st.info("Import from vehicles.json - coming soon")


# ============================================================================
# Page: Generate
# ============================================================================

elif page == "🔧 Generate":
    st.title("🔧 Generate Vehicle Data")
    
    st.warning("⚠️ **Cost Warning:** Generation uses AI APIs that cost money. Monitor your usage!")
    
    tab1, tab2, tab3 = st.tabs(["Generate Manufacturer", "DTC Only", "Fill Gaps"])
    
    with tab1:
        st.subheader("Generate Full Manufacturer Data")
        
        with st.form("generate_form"):
            manufacturers = st.text_input(
                "Manufacturers (comma-separated)",
                placeholder="Toyota, Honda, BMW"
            )
            
            col1, col2 = st.columns(2)
            with col1:
                market = st.selectbox("Market", ["Global", "US", "EU", "UK", "Asia", "Australia"])
            with col2:
                fetch_dtc = st.checkbox("Also fetch DTC codes", value=True)
            
            force_regen = st.checkbox("Force regenerate (ignore existing)", value=False)
            
            submitted = st.form_submit_button("🚀 Start Generation", type="primary")
            
            if submitted and manufacturers:
                cmd = [
                    sys.executable, str(SCRIPT_DIR / "generate_vehicles.py"),
                    "--mode", "manufacturers",
                    "--batch", manufacturers,
                    "--market", market
                ]
                if fetch_dtc:
                    cmd.append("--fetch-dtc")
                if force_regen:
                    cmd.append("--force")
                
                st.code(" ".join(cmd))
                st.info("Run this command in your terminal. GUI execution coming soon!")
    
    with tab2:
        st.subheader("Generate DTC Codes Only")
        
        with st.form("dtc_only_form"):
            manufacturers = st.text_input(
                "Manufacturers (comma-separated)",
                placeholder="Mercedes-Benz, Audi, Volkswagen"
            )
            
            force_regen = st.checkbox("Force regenerate (ignore existing)", value=False)
            
            submitted = st.form_submit_button("🔧 Generate DTCs", type="primary")
            
            if submitted and manufacturers:
                cmd = [
                    sys.executable, str(SCRIPT_DIR / "generate_vehicles.py"),
                    "--mode", "manufacturers",
                    "--batch", manufacturers,
                    "--dtc-only"
                ]
                if force_regen:
                    cmd.append("--force")
                
                st.code(" ".join(cmd))
                st.info("Run this command in your terminal. GUI execution coming soon!")
    
    with tab3:
        st.subheader("Fill Gaps with AI")
        
        st.markdown("Enrich existing codes that are missing detailed descriptions, causes, or symptoms.")
        
        # Show codes with gaps
        if not dtc_df.empty:
            gaps = dtc_df[
                (dtc_df['detailed_description'].isna() | (dtc_df['detailed_description'] == '')) |
                (dtc_df['common_causes'].isna() | (dtc_df['common_causes'] == '[]'))
            ]
            st.metric("Codes with gaps", len(gaps))
            
            if st.button("🤖 Fill Gaps"):
                cmd = [sys.executable, str(SCRIPT_DIR / "fill_dtc_gaps.py")]
                st.code(" ".join(cmd))
                st.info("Run this command in your terminal. GUI execution coming soon!")


# ============================================================================
# Page: Scrape
# ============================================================================

elif page == "🌐 Scrape":
    st.title("🌐 Web Scraper")
    
    st.info("Extract DTC codes from manufacturer websites (FREE - no AI used)")
    
    with st.form("scrape_form"):
        url = st.text_input("URL to scrape", placeholder="https://example.com/dtc-codes")
        manufacturer = st.text_input("Manufacturer name", placeholder="Honda")
        
        col1, col2 = st.columns(2)
        with col1:
            follow_links = st.checkbox("Follow links on page", value=False)
        with col2:
            prepare = st.checkbox("Prepare for import", value=True)
        
        submitted = st.form_submit_button("🕷️ Start Scraping", type="primary")
        
        if submitted and url and manufacturer:
            cmd = [
                sys.executable, str(SCRIPT_DIR / "scrape_dtc.py"),
                "--url", url,
                "--manufacturer", manufacturer
            ]
            if follow_links:
                cmd.append("--follow-links")
            if prepare:
                cmd.append("--prepare")
            
            st.code(" ".join(cmd))
            st.info("Run this command in your terminal. GUI execution coming soon!")
    
    st.markdown("---")
    st.subheader("Known Sources")
    
    known_sources = {
        "Honda": "https://hondacodes.wordpress.com/honda-fault-codes/",
        "Toyota": "(Add URL)",
        "BMW": "(Add URL)",
        "Mercedes-Benz": "(Add URL)",
    }
    
    for make, url in known_sources.items():
        st.markdown(f"**{make}:** `{url}`")


# ============================================================================
# Page: Statistics
# ============================================================================

elif page == "📊 Statistics":
    st.title("📊 Database Statistics")
    
    if dtc_df.empty:
        st.warning("No data loaded.")
    else:
        # Overview metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total DTC Codes", len(dtc_df))
        with col2:
            st.metric("Manufacturers", dtc_df['make_id'].nunique())
        with col3:
            unique_systems = dtc_df['system'].dropna().nunique()
            st.metric("Systems", unique_systems)
        with col4:
            models_df = load_models()
            st.metric("Vehicle Models", len(models_df))
        
        st.markdown("---")
        
        # Charts
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Codes by Manufacturer")
            make_counts = dtc_df['make_id'].value_counts().head(15)
            # Map IDs to names
            make_counts.index = [get_make_name(m, makes_df) for m in make_counts.index]
            st.bar_chart(make_counts)
        
        with col2:
            st.subheader("Codes by Severity")
            severity_counts = dtc_df['severity'].value_counts()
            st.bar_chart(severity_counts)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Codes by System")
            system_counts = dtc_df['system'].value_counts().head(10)
            st.bar_chart(system_counts)
        
        with col2:
            st.subheader("Codes by Powertrain")
            pt_counts = dtc_df['powertrain_type'].value_counts()
            st.bar_chart(pt_counts)
        
        st.markdown("---")
        
        # Code prefix distribution
        st.subheader("Code Type Distribution")
        dtc_df['prefix'] = dtc_df['code'].str[0]
        prefix_counts = dtc_df['prefix'].value_counts()
        
        prefix_names = {
            'P': 'Powertrain',
            'B': 'Body',
            'C': 'Chassis',
            'U': 'Network'
        }
        
        cols = st.columns(4)
        for i, (prefix, count) in enumerate(prefix_counts.items()):
            with cols[i % 4]:
                st.metric(f"{prefix} - {prefix_names.get(prefix, 'Unknown')}", count)
        
        # Data quality
        st.markdown("---")
        st.subheader("Data Quality")
        
        missing_detailed = len(dtc_df[dtc_df['detailed_description'].isna() | (dtc_df['detailed_description'] == '')])
        missing_causes = len(dtc_df[dtc_df['common_causes'].isna() | (dtc_df['common_causes'] == '[]') | (dtc_df['common_causes'] == '')])
        missing_symptoms = len(dtc_df[dtc_df['symptoms'].isna() | (dtc_df['symptoms'] == '[]') | (dtc_df['symptoms'] == '')])
        
        col1, col2, col3 = st.columns(3)
        with col1:
            pct = (1 - missing_detailed / len(dtc_df)) * 100
            st.metric("Has Detailed Desc", f"{pct:.1f}%")
        with col2:
            pct = (1 - missing_causes / len(dtc_df)) * 100
            st.metric("Has Common Causes", f"{pct:.1f}%")
        with col3:
            pct = (1 - missing_symptoms / len(dtc_df)) * 100
            st.metric("Has Symptoms", f"{pct:.1f}%")


# ============================================================================
# Page: Settings
# ============================================================================

elif page == "⚙️ Settings":
    st.title("⚙️ Settings")
    
    tab1, tab2, tab3, tab4 = st.tabs(["Paths", "API", "Export", "🔐 Encryption"])
    
    with tab1:
        st.subheader("Data Paths")
        st.text_input("Output Directory", value=str(OUTPUT_DIR), disabled=True)
        st.text_input("Assets Directory", value=str(ASSETS_DIR), disabled=True)
        
        if st.button("📂 Open Output Folder"):
            os.startfile(OUTPUT_DIR) if os.name == 'nt' else subprocess.run(['open', OUTPUT_DIR])
    
    with tab2:
        st.subheader("API Configuration")
        
        env_file = SCRIPT_DIR / ".env"
        if env_file.exists():
            st.success("✅ .env file found")
        else:
            st.warning("⚠️ .env file not found - create one from .env.example")
        
        st.markdown("""
        Edit your `.env` file to configure:
        - `OPENROUTER_API_KEY` - Your API key
        - `OPENROUTER_MODEL` - AI model to use
        """)
    
    with tab3:
        st.subheader("Export Data")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📥 Merge to JSON"):
                cmd = [sys.executable, str(SCRIPT_DIR / "merge_to_json.py")]
                st.code(" ".join(cmd))
                st.info("Run this command to merge CSVs to vehicles.json")
        
        with col2:
            if st.button("📦 Export DTC CSV"):
                if not dtc_df.empty:
                    csv = dtc_df.to_csv(index=False)
                    st.download_button(
                        "Download dtc_codes.csv",
                        csv,
                        "dtc_codes.csv",
                        "text/csv"
                    )
        
        st.markdown("---")
        
        st.subheader("GitHub Contribution")
        st.markdown("""
        To contribute your data to the community:
        1. Fork the repository
        2. Add your CSV changes
        3. Submit a Pull Request
        
        [View Contributing Guidelines](https://github.com/YOUR_USERNAME/carpulse-data/blob/main/CONTRIBUTING.md)
        """)
    
    with tab4:
        st.subheader("🔐 Data Encryption")
        
        st.info("""
        **Protect your data for distribution!**
        
        Encrypted data can only be used by the CarPulse app and this tool.
        This prevents competitors from simply copying your data files.
        """)
        
        encrypted_dir = OUTPUT_DIR / "encrypted"
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Source Files:**")
            json_files = list(OUTPUT_DIR.glob("*.json"))
            csv_files = list(OUTPUT_DIR.glob("*.csv"))
            st.write(f"  • {len(json_files)} JSON files")
            st.write(f"  • {len(csv_files)} CSV files")
        
        with col2:
            st.markdown("**Encrypted Files:**")
            if encrypted_dir.exists():
                enc_files = list(encrypted_dir.glob("*.enc.*"))
                st.write(f"  • {len(enc_files)} encrypted files")
            else:
                st.write("  • No encrypted files yet")
        
        st.markdown("---")
        
        if st.button("🔐 Encrypt All Data Files", type="primary"):
            try:
                from crypto_utils import encrypt_json_file, encrypt_csv
                
                encrypted_dir.mkdir(parents=True, exist_ok=True)
                
                progress = st.progress(0)
                status = st.empty()
                
                all_files = json_files + csv_files
                total = len(all_files)
                
                for i, file in enumerate(all_files):
                    status.text(f"Encrypting {file.name}...")
                    
                    if file.suffix == '.json':
                        out_file = encrypted_dir / (file.stem + '.enc.json')
                        encrypt_json_file(str(file), str(out_file))
                    else:
                        out_file = encrypted_dir / (file.stem + '.enc.csv')
                        encrypt_csv(str(file), str(out_file))
                    
                    progress.progress((i + 1) / total)
                
                status.empty()
                progress.empty()
                
                st.success(f"✅ Encrypted {total} files to `{encrypted_dir}`")
                
            except ImportError:
                st.error("❌ cryptography package not installed. Run: `pip install cryptography`")
            except Exception as e:
                st.error(f"❌ Encryption failed: {e}")
        
        st.markdown("---")
        
        st.subheader("Copy to Flutter Assets")
        
        copy_to_assets = st.checkbox("Also copy encrypted files to Flutter assets")
        
        if copy_to_assets and encrypted_dir.exists():
            encrypted_assets_dir = ASSETS_DIR / "encrypted"
            
            if st.button("📋 Copy Encrypted Files to Assets"):
                import shutil
                
                encrypted_assets_dir.mkdir(parents=True, exist_ok=True)
                
                for enc_file in encrypted_dir.glob("*.enc.*"):
                    dest = encrypted_assets_dir / enc_file.name
                    shutil.copy(enc_file, dest)
                
                st.success(f"✅ Copied files to `{encrypted_assets_dir}`")
        
        st.markdown("---")
        
        with st.expander("ℹ️ How Encryption Works"):
            st.markdown("""
            **Security Features:**
            - **AES-256 encryption** - Military-grade encryption
            - **Obfuscated keys** - Keys are not stored in plain text
            - **App-specific** - Only CarPulse can decrypt the data
            
            **Files Generated:**
            - `vehicles.enc.json` - Encrypted vehicle database
            - `dtc_codes.enc.csv` - Encrypted DTC codes
            
            **Usage in Flutter:**
            ```dart
            import 'package:carpulse/utils/data_decryptor.dart';
            
            // Load encrypted asset
            final data = await rootBundle.load('assets/data/encrypted/vehicles.enc.json');
            final vehicles = DataDecryptor.instance.decryptJson(data.buffer.asUint8List());
            ```
            """)


# ============================================================================
# Footer
# ============================================================================

st.sidebar.markdown("---")
st.sidebar.markdown("Made with ❤️ for CarPulse")
st.sidebar.markdown("[Documentation](https://github.com/YOUR_USERNAME/carpulse-data)")
