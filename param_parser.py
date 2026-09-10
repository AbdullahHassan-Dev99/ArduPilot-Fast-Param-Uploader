"""
Parameter Parser Module
Supports loading and saving parameters from/to .param and .json formats.
"""

import json
import os
from typing import Dict, Union, Tuple, Any

def parse_param_file(filepath: str) -> Dict[str, float]:
    """
    Parses ArduPilot standard .param or .params file.
    Supports comma, space, tab, or '=' delimited formats.
    Ignores comment lines starting with '#' or ';'.
    """
    params = {}
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            # Skip empty lines or comments
            if not line or line.startswith('#') or line.startswith(';'):
                continue
            
            # Remove inline comments if present
            if '#' in line:
                line = line.split('#')[0].strip()
            if ';' in line:
                line = line.split(';')[0].strip()
            
            if not line:
                continue

            # Determine delimiter: comma, '=', or whitespace
            parts = []
            if ',' in line:
                parts = line.split(',')
            elif '=' in line:
                parts = line.split('=')
            else:
                parts = line.split()

            if len(parts) >= 2:
                param_name = parts[0].strip().upper()
                raw_val = parts[1].strip()
                try:
                    # Convert to float or int
                    if '.' in raw_val or 'e' in raw_val.lower():
                        val = float(raw_val)
                    else:
                        val = float(int(raw_val))
                    params[param_name] = val
                except ValueError:
                    print(f"[Warning] Line {line_num}: Could not parse value '{raw_val}' for param '{param_name}'")
    return params

def parse_json_file(filepath: str) -> Dict[str, float]:
    """
    Parses JSON parameter file.
    Supports:
    1. Key-Value Dict: {"PARAM1": 1.0, "PARAM2": 2.0}
    2. Array of objects: [{"name": "PARAM1", "value": 1.0}, ...]
    3. Nested dict: {"parameters": [{"name": "PARAM1", "value": 1.0}]}
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    params = {}

    if isinstance(data, dict):
        if "parameters" in data and isinstance(data["parameters"], list):
            data_list = data["parameters"]
            for item in data_list:
                if isinstance(item, dict):
                    name = item.get("name") or item.get("param") or item.get("key")
                    val = item.get("value") or item.get("val")
                    if name is not None and val is not None:
                        params[str(name).upper()] = float(val)
        elif "parameters" in data and isinstance(data["parameters"], dict):
            for name, val in data["parameters"].items():
                params[str(name).upper()] = float(val)
        else:
            # Simple Key-Value Dict
            for name, val in data.items():
                try:
                    params[str(name).upper()] = float(val)
                except (ValueError, TypeError):
                    print(f"[Warning] Skipping invalid parameter pair: {name} = {val}")

    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                name = item.get("name") or item.get("param") or item.get("key")
                val = item.get("value") or item.get("val")
                if name is not None and val is not None:
                    try:
                        params[str(name).upper()] = float(val)
                    except (ValueError, TypeError):
                        pass

    return params

def load_parameters(filepath: str) -> Dict[str, float]:
    """
    Loads parameter file automatically based on extension or format inspection.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Parameter file not found: {filepath}")

    ext = os.path.splitext(filepath)[1].lower()

    if ext == '.json':
        return parse_json_file(filepath)
    elif ext in ['.param', '.params', '.txt']:
        return parse_param_file(filepath)
    else:
        # Attempt JSON first, fallback to PARAM
        try:
            return parse_json_file(filepath)
        except Exception:
            return parse_param_file(filepath)

def save_to_param_file(params: Dict[str, float], output_filepath: str):
    """Saves parameter dictionary to standard .param format (NAME,VALUE)."""
    with open(output_filepath, 'w', encoding='utf-8') as f:
        for name, val in sorted(params.items()):
            if val == int(val):
                val_str = str(int(val))
            else:
                val_str = f"{val:.7g}"
            f.write(f"{name},{val_str}\n")

def save_to_json_file(params: Dict[str, float], output_filepath: str, format_type: str = 'dict'):
    """
    Saves parameter dictionary to JSON format.
    format_type: 'dict' ({"NAME": val}) or 'list' ([{"name": "NAME", "value": val}])
    """
    with open(output_filepath, 'w', encoding='utf-8') as f:
        if format_type == 'list':
            data = [{"name": name, "value": val} for name, val in sorted(params.items())]
        else:
            data = {name: val for name, val in sorted(params.items())}
        json.dump(data, f, indent=4)
