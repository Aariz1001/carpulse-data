"""
CarPulse Data Encryption Utilities

This module provides encryption/decryption for vehicle and DTC data.
The encryption ensures the data only works with authorized applications.
"""

import os
import json
import csv
import base64
import hashlib
from io import StringIO
from pathlib import Path
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding

# =============================================================================
# KEY OBFUSCATION
# =============================================================================
# The key is NOT stored in plain text. It's derived from multiple components
# that are combined and hashed. This makes it harder to extract.

def _get_key_components():
    """
    Returns key components that are combined to form the encryption key.
    These are intentionally obscure and split across multiple values.
    
    ⚠️  IMPORTANT: For your own deployment, create a file called
        'crypto_keys_private.py' with your own secret values.
        The file should contain a function: get_private_keys() -> tuple
        
        Example crypto_keys_private.py:
        
        def get_private_keys():
            return (
                "your-secret-value-1",
                "your-secret-value-2", 
                "your-secret-value-3",
                "your-secret-value-4",
                "your-secret-salt"
            )
    """
    # Try to load private keys first
    try:
        from crypto_keys_private import get_private_keys
        return get_private_keys()
    except ImportError:
        pass
    
    # Fallback to default keys (for development/testing only)
    # ⚠️ DO NOT use these in production!
    
    # Component 1: Looks like a version string
    c1 = "v2.4.1-carpulse"
    
    # Component 2: Looks like a build ID  
    c2 = "build_7f3a9c2e"
    
    # Component 3: Looks like a config value
    c3 = "obd2_protocol_iso15765"
    
    # Component 4: App identifier
    c4 = "com.carpulse.diagnostics"
    
    # Salt that looks like a timestamp
    salt = "20240115_release"
    
    return c1, c2, c3, c4, salt


def _derive_key():
    """
    Derives the encryption key from obfuscated components.
    Uses SHA-256 to create a consistent 32-byte key.
    """
    c1, c2, c3, c4, salt = _get_key_components()
    
    # Combine in a specific way
    combined = f"{c3}::{c1}||{salt}<<{c4}>>{c2}"
    
    # Hash to get 32-byte key for AES-256
    key = hashlib.sha256(combined.encode('utf-8')).digest()
    return key


def _derive_iv():
    """
    Derives a consistent IV from key components.
    Uses MD5 to create a 16-byte IV.
    """
    c1, c2, c3, c4, salt = _get_key_components()
    
    # Different combination for IV
    combined = f"{c2}@@{salt}!!{c1}"
    
    # MD5 gives us exactly 16 bytes for IV
    iv = hashlib.md5(combined.encode('utf-8')).digest()
    return iv


# =============================================================================
# ENCRYPTION / DECRYPTION
# =============================================================================

def encrypt_data(data: bytes) -> bytes:
    """
    Encrypts data using AES-256-CBC.
    
    Args:
        data: Raw bytes to encrypt
        
    Returns:
        Encrypted bytes (base64 encoded for safe storage)
    """
    key = _derive_key()
    iv = _derive_iv()
    
    # Pad data to block size
    padder = padding.PKCS7(128).padder()
    padded_data = padder.update(data) + padder.finalize()
    
    # Encrypt
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    encrypted = encryptor.update(padded_data) + encryptor.finalize()
    
    # Base64 encode for safe storage
    return base64.b64encode(encrypted)


def decrypt_data(encrypted_data: bytes) -> bytes:
    """
    Decrypts data that was encrypted with encrypt_data().
    
    Args:
        encrypted_data: Base64 encoded encrypted bytes
        
    Returns:
        Decrypted bytes
    """
    key = _derive_key()
    iv = _derive_iv()
    
    # Base64 decode
    encrypted = base64.b64decode(encrypted_data)
    
    # Decrypt
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    padded_data = decryptor.update(encrypted) + decryptor.finalize()
    
    # Unpad
    unpadder = padding.PKCS7(128).unpadder()
    data = unpadder.update(padded_data) + unpadder.finalize()
    
    return data


# =============================================================================
# FILE ENCRYPTION / DECRYPTION
# =============================================================================

def encrypt_file(input_path: str, output_path: str = None) -> str:
    """
    Encrypts a file.
    
    Args:
        input_path: Path to the file to encrypt
        output_path: Path for encrypted output (default: input_path + '.enc')
        
    Returns:
        Path to the encrypted file
    """
    if output_path is None:
        output_path = input_path + '.enc'
    
    with open(input_path, 'rb') as f:
        data = f.read()
    
    encrypted = encrypt_data(data)
    
    with open(output_path, 'wb') as f:
        f.write(encrypted)
    
    return output_path


def decrypt_file(input_path: str, output_path: str = None) -> str:
    """
    Decrypts a file.
    
    Args:
        input_path: Path to the encrypted file
        output_path: Path for decrypted output (default: removes .enc extension)
        
    Returns:
        Path to the decrypted file
    """
    if output_path is None:
        if input_path.endswith('.enc'):
            output_path = input_path[:-4]
        else:
            output_path = input_path + '.dec'
    
    with open(input_path, 'rb') as f:
        encrypted_data = f.read()
    
    decrypted = decrypt_data(encrypted_data)
    
    with open(output_path, 'wb') as f:
        f.write(decrypted)
    
    return output_path


# =============================================================================
# JSON HELPERS
# =============================================================================

def encrypt_json(data: dict | list) -> bytes:
    """Encrypts a JSON-serializable object."""
    json_bytes = json.dumps(data, separators=(',', ':')).encode('utf-8')
    return encrypt_data(json_bytes)


def decrypt_json(encrypted_data: bytes) -> dict | list:
    """Decrypts to a JSON object."""
    decrypted = decrypt_data(encrypted_data)
    return json.loads(decrypted.decode('utf-8'))


def encrypt_json_file(input_path: str, output_path: str = None) -> str:
    """Encrypts a JSON file."""
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    if output_path is None:
        output_path = input_path.replace('.json', '.enc.json')
    
    encrypted = encrypt_json(data)
    
    with open(output_path, 'wb') as f:
        f.write(encrypted)
    
    return output_path


def decrypt_json_file(input_path: str) -> dict | list:
    """Decrypts a JSON file and returns the data."""
    with open(input_path, 'rb') as f:
        encrypted_data = f.read()
    return decrypt_json(encrypted_data)


# =============================================================================
# CSV HELPERS
# =============================================================================

def encrypt_csv(input_path: str, output_path: str = None) -> str:
    """Encrypts a CSV file."""
    with open(input_path, 'r', encoding='utf-8') as f:
        data = f.read()
    
    if output_path is None:
        output_path = input_path.replace('.csv', '.enc.csv')
    
    encrypted = encrypt_data(data.encode('utf-8'))
    
    with open(output_path, 'wb') as f:
        f.write(encrypted)
    
    return output_path


def decrypt_csv(input_path: str) -> list[dict]:
    """Decrypts a CSV file and returns list of dicts."""
    with open(input_path, 'rb') as f:
        encrypted_data = f.read()
    
    decrypted = decrypt_data(encrypted_data).decode('utf-8')
    reader = csv.DictReader(StringIO(decrypted))
    return list(reader)


def decrypt_csv_to_string(input_path: str) -> str:
    """Decrypts a CSV file and returns raw string."""
    with open(input_path, 'rb') as f:
        encrypted_data = f.read()
    return decrypt_data(encrypted_data).decode('utf-8')


# =============================================================================
# BATCH OPERATIONS
# =============================================================================

def encrypt_all_data_files(data_dir: str, output_dir: str = None):
    """
    Encrypts all JSON and CSV files in a directory.
    
    Args:
        data_dir: Directory containing data files
        output_dir: Output directory (default: same as data_dir)
    """
    if output_dir is None:
        output_dir = data_dir
    
    data_path = Path(data_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    encrypted_files = []
    
    # Encrypt JSON files
    for json_file in data_path.glob('*.json'):
        out_file = output_path / (json_file.stem + '.enc.json')
        encrypt_json_file(str(json_file), str(out_file))
        encrypted_files.append(str(out_file))
        print(f"✓ Encrypted: {json_file.name} → {out_file.name}")
    
    # Encrypt CSV files
    for csv_file in data_path.glob('*.csv'):
        out_file = output_path / (csv_file.stem + '.enc.csv')
        encrypt_csv(str(csv_file), str(out_file))
        encrypted_files.append(str(out_file))
        print(f"✓ Encrypted: {csv_file.name} → {out_file.name}")
    
    return encrypted_files


# =============================================================================
# VERIFICATION
# =============================================================================

def verify_encryption(original_path: str, encrypted_path: str) -> bool:
    """
    Verifies that an encrypted file decrypts to match the original.
    
    Returns:
        True if verification passes
    """
    with open(original_path, 'rb') as f:
        original_data = f.read()
    
    with open(encrypted_path, 'rb') as f:
        encrypted_data = f.read()
    
    try:
        decrypted_data = decrypt_data(encrypted_data)
        return original_data == decrypted_data
    except Exception as e:
        print(f"Verification failed: {e}")
        return False


# =============================================================================
# CLI
# =============================================================================

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='CarPulse Data Encryption Utility')
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Encrypt command
    encrypt_parser = subparsers.add_parser('encrypt', help='Encrypt a file')
    encrypt_parser.add_argument('input', help='Input file path')
    encrypt_parser.add_argument('-o', '--output', help='Output file path')
    
    # Decrypt command  
    decrypt_parser = subparsers.add_parser('decrypt', help='Decrypt a file')
    decrypt_parser.add_argument('input', help='Input file path')
    decrypt_parser.add_argument('-o', '--output', help='Output file path')
    
    # Batch encrypt command
    batch_parser = subparsers.add_parser('batch', help='Encrypt all data files in directory')
    batch_parser.add_argument('directory', help='Directory containing data files')
    batch_parser.add_argument('-o', '--output', help='Output directory')
    
    # Verify command
    verify_parser = subparsers.add_parser('verify', help='Verify encryption')
    verify_parser.add_argument('original', help='Original file')
    verify_parser.add_argument('encrypted', help='Encrypted file')
    
    args = parser.parse_args()
    
    if args.command == 'encrypt':
        result = encrypt_file(args.input, args.output)
        print(f"✓ Encrypted: {result}")
        
    elif args.command == 'decrypt':
        result = decrypt_file(args.input, args.output)
        print(f"✓ Decrypted: {result}")
        
    elif args.command == 'batch':
        results = encrypt_all_data_files(args.directory, args.output)
        print(f"\n✓ Encrypted {len(results)} files")
        
    elif args.command == 'verify':
        if verify_encryption(args.original, args.encrypted):
            print("✓ Verification passed!")
        else:
            print("✗ Verification failed!")
            exit(1)
    else:
        parser.print_help()
