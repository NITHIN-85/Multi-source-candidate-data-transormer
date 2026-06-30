import re
import jsonschema
from src.normalizer import normalize_phone, normalize_skill

def get_by_path(candidate: dict, path_str: str) -> any:
    """Extract a value from a candidate dictionary using a JSON-like path."""
    if not path_str:
        return None
        
    # 1. Match list index like "emails[0]" or "phones[0]"
    match_idx = re.match(r"^(\w+)\[(\d+)\]$", path_str)
    if match_idx:
        key, idx = match_idx.groups()
        lst = candidate.get(key)
        if lst and isinstance(lst, list) and len(lst) > int(idx):
            return lst[int(idx)]
        return None
        
    # 2. Match subkey map like "skills[].name"
    match_map = re.match(r"^(\w+)\[\]\.(\w+)$", path_str)
    if match_map:
        key, subkey = match_map.groups()
        lst = candidate.get(key)
        if lst and isinstance(lst, list):
            return [item.get(subkey) for item in lst if isinstance(item, dict) and subkey in item]
        return None
        
    # 3. Direct key access
    return candidate.get(path_str)

def apply_normalization(val: any, norm_type: str) -> any:
    """Apply inline dynamic normalizations during projection."""
    if val is None:
        return None
    if norm_type == "E164":
        if isinstance(val, list):
            normalized = [normalize_phone(v) for v in val]
            return [n for n in normalized if n]
        return normalize_phone(str(val))
    elif norm_type == "canonical":
        if isinstance(val, list):
            return [normalize_skill(str(v)) for v in val]
        return normalize_skill(str(val))
    return val

def generate_json_schema(config: dict) -> dict:
    """Build a dynamic JSON Schema from the custom configuration file."""
    properties = {}
    required = []
    
    # Map configuration types to JSON schema types
    type_mapping = {
        "string": {"type": "string"},
        "number": {"type": "number"},
        "boolean": {"type": "boolean"},
        "string[]": {
            "type": "array",
            "items": {"type": "string"}
        },
        "number[]": {
            "type": "array",
            "items": {"type": "number"}
        }
    }
    
    for f in config.get("fields", []):
        path = f.get("path")
        t = f.get("type", "string")
        req = f.get("required", False)
        
        if path:
            properties[path] = type_mapping.get(t, {"type": "string"})
            # If the value is nullable in our projection, allow null in schema
            if not req:
                if isinstance(properties[path], dict):
                    # For draft-07 compatible null type union
                    if "type" in properties[path]:
                        orig_type = properties[path]["type"]
                        if orig_type == "array":
                            properties[path] = {
                                "anyOf": [
                                    properties[path],
                                    {"type": "null"}
                                ]
                            }
                        else:
                            properties[path]["type"] = [orig_type, "null"]
            else:
                required.append(path)
                
    # Add metadata if toggled on
    if config.get("include_confidence", False):
        properties["overall_confidence"] = {"type": "number"}
    if config.get("include_provenance", False):
        properties["provenance"] = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "field": {"type": "string"},
                    "source": {"type": "string"},
                    "method": {"type": "string"}
                },
                "required": ["field", "source", "method"]
            }
        }
        
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False
    }

def project_candidate(candidate: dict, config: dict) -> dict:
    """Reshape a canonical candidate profile based on the custom configuration."""
    projected = {}
    on_missing = config.get("on_missing", "null")
    
    for f in config.get("fields", []):
        path = f.get("path")
        source_path = f.get("from", path)
        norm_type = f.get("normalize")
        is_required = f.get("required", False)
        
        val = get_by_path(candidate, source_path)
        
        # Apply normalization override if specified
        if norm_type:
            val = apply_normalization(val, norm_type)
            
        if val is None or val == [] or val == "":
            # Missing value handling
            if is_required and on_missing == "error":
                raise ValueError(f"Required field '{path}' is missing for candidate.")
            elif on_missing == "omit":
                continue
            else:
                projected[path] = None
        else:
            projected[path] = val
            
    # Include metadata if configured
    if config.get("include_confidence", False):
        projected["overall_confidence"] = candidate.get("overall_confidence", 0.0)
    if config.get("include_provenance", False):
        # We only project provenance entries for fields that are in the output
        field_paths = {f.get("path") for f in config.get("fields", [])}
        prov = [p for p in candidate.get("provenance", []) if p.get("field") in field_paths]
        projected["provenance"] = prov
        
    # Validate result against dynamic generated schema
    schema = generate_json_schema(config)
    jsonschema.validate(instance=projected, schema=schema)
    
    return projected
