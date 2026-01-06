#!/usr/bin/env python3
"""
Encrypt CarPulse Data Files

This script encrypts all vehicle and DTC data files for distribution.
The encrypted files can only be decrypted by the CarPulse app and authorized tools.

Usage:
    python encrypt_data.py                    # Encrypt all data files
    python encrypt_data.py --verify           # Encrypt and verify
    python encrypt_data.py --output ./dist    # Encrypt to specific directory
"""

import argparse
import shutil
from pathlib import Path
from crypto_utils import (
    encrypt_json_file,
    encrypt_csv,
    verify_encryption,
    encrypt_all_data_files
)


def main():
    parser = argparse.ArgumentParser(
        description='Encrypt CarPulse data files for distribution'
    )
    parser.add_argument(
        '--output', '-o',
        default='./output/encrypted',
        help='Output directory for encrypted files'
    )
    parser.add_argument(
        '--verify', '-v',
        action='store_true',
        help='Verify encryption after completing'
    )
    parser.add_argument(
        '--input', '-i',
        default='./output',
        help='Input directory containing data files'
    )
    parser.add_argument(
        '--assets',
        help='Also copy encrypted files to Flutter assets directory'
    )
    
    args = parser.parse_args()
    
    input_dir = Path(args.input)
    output_dir = Path(args.output)
    
    if not input_dir.exists():
        print(f"❌ Input directory not found: {input_dir}")
        return 1
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("=" * 60)
    print("CarPulse Data Encryption")
    print("=" * 60)
    print(f"Input:  {input_dir.absolute()}")
    print(f"Output: {output_dir.absolute()}")
    print("-" * 60)
    
    encrypted_files = []
    verification_pairs = []
    
    # Encrypt JSON files
    for json_file in input_dir.glob('*.json'):
        out_file = output_dir / (json_file.stem + '.enc.json')
        encrypt_json_file(str(json_file), str(out_file))
        encrypted_files.append(out_file)
        verification_pairs.append((json_file, out_file))
        print(f"✓ {json_file.name} → {out_file.name}")
    
    # Encrypt CSV files
    for csv_file in input_dir.glob('*.csv'):
        out_file = output_dir / (csv_file.stem + '.enc.csv')
        encrypt_csv(str(csv_file), str(out_file))
        encrypted_files.append(out_file)
        verification_pairs.append((csv_file, out_file))
        print(f"✓ {csv_file.name} → {out_file.name}")
    
    print("-" * 60)
    print(f"Encrypted {len(encrypted_files)} files")
    
    # Verify if requested
    if args.verify:
        print("\nVerifying encryption...")
        all_passed = True
        for original, encrypted in verification_pairs:
            from crypto_utils import decrypt_data
            try:
                # Read original as text (normalized)
                with open(original, 'r', encoding='utf-8') as f:
                    original_text = f.read()
                
                # Read encrypted and decrypt
                with open(encrypted, 'rb') as f:
                    encrypted_data = f.read()
                
                decrypted_data = decrypt_data(encrypted_data)
                decrypted_text = decrypted_data.decode('utf-8')
                
                # Compare normalized text (ignore line ending differences)
                original_normalized = original_text.replace('\r\n', '\n').strip()
                decrypted_normalized = decrypted_text.replace('\r\n', '\n').strip()
                
                if original_normalized == decrypted_normalized:
                    print(f"  ✓ {original.name}")
                else:
                    print(f"  ✗ {original.name} - Data mismatch!")
                    # Debug: show first difference
                    for i, (a, b) in enumerate(zip(original_normalized, decrypted_normalized)):
                        if a != b:
                            print(f"    First diff at position {i}: '{repr(a)}' vs '{repr(b)}'")
                            break
                    all_passed = False
            except Exception as e:
                print(f"  ✗ {original.name} - Decryption failed: {e}")
                all_passed = False
        
        if all_passed:
            print("\n✓ All files verified successfully!")
        else:
            print("\n✗ Some files failed verification!")
            return 1
    
    # Copy to Flutter assets if specified
    if args.assets:
        assets_dir = Path(args.assets)
        assets_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"\nCopying to Flutter assets: {assets_dir}")
        for enc_file in encrypted_files:
            dest = assets_dir / enc_file.name
            shutil.copy(enc_file, dest)
            print(f"  → {dest.name}")
    
    print("\n" + "=" * 60)
    print("Encryption complete!")
    print("=" * 60)
    
    return 0


if __name__ == '__main__':
    exit(main())
