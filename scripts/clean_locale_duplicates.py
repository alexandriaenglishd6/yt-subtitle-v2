"""Clean duplicate keys from JSON locale files"""
import json
from collections import OrderedDict
from pathlib import Path

def find_and_remove_duplicates(json_path):
    """Find duplicate keys and keep only the last occurrence"""
    with open(json_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Parse with duplicate detection
    seen = {}
    duplicates = []
    
    def object_pairs_hook(pairs):
        result = OrderedDict()
        for key, value in pairs:
            if key in result:
                duplicates.append(key)
            result[key] = value
        return result
    
    data = json.loads(content, object_pairs_hook=object_pairs_hook)
    
    print(f"File: {json_path}")
    print(f"Total keys: {len(data)}")
    print(f"Duplicate keys found: {len(duplicates)}")
    
    if duplicates:
        unique_dups = list(set(duplicates))
        print(f"Unique duplicates: {unique_dups[:20]}...")
        
        # Save cleaned file
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Cleaned file saved (kept last occurrence of each duplicate)")
    
    return len(duplicates)

if __name__ == "__main__":
    locales_dir = Path("core/i18n/locales")
    
    for json_file in locales_dir.glob("*.json"):
        find_and_remove_duplicates(json_file)
        print("---")
