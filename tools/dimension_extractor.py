import re
from typing import List

from typing import List, Dict, Any

def extract_attributes(text: str) -> Dict[str, Any]:
    """
    텍스트에서 정형화된 속성 데이터(치수, 정밀도, 재질 등)를 추출합니다.
    """
    attributes = {}
    
    # 1. 내경/외경/폭 패턴
    id_match = re.search(r'ID\s?[:]?\s?(\d+(?:\.\d+)?)', text, re.IGNORECASE)
    od_match = re.search(r'OD\s?[:]?\s?(\d+(?:\.\d+)?)', text, re.IGNORECASE)
    width_match = re.search(r'(?:Width|W)\s?[:]?\s?(\d+(?:\.\d+)?)', text, re.IGNORECASE)
    
    if id_match: attributes["inner_diameter"] = float(id_match.group(1))
    if od_match: attributes["outer_diameter"] = float(od_match.group(1))
    if width_match: attributes["width"] = float(width_match.group(1))
    
    # 2. 정밀도 등급 (P5, P6, Class 6 등)
    precision_match = re.search(r'([P][0-9]|Class\s?[0-9]|ABEC\s?-[0-9])', text, re.IGNORECASE)
    if precision_match: attributes["precision"] = precision_match.group(1).upper()

    # 3. 재질 (SUS304, S45C, Steel 등)
    material_match = re.search(r'(SUS\d+|S45C|Steel|Stainless|Chrome)', text, re.IGNORECASE)
    if material_match: attributes["material"] = material_match.group(1).capitalize()

    # 4. 모듈/잇수 패턴 (Gear용)
    mod_match = re.search(r'(?:Mod|Module)\s?[:]?\s?(\d+(?:\.\d+)?)', text, re.IGNORECASE)
    teeth_match = re.search(r'(?:Teeth|z)\s?[:]?\s?(\d+)', text, re.IGNORECASE)
    
    if mod_match: attributes["module"] = float(mod_match.group(1))
    if teeth_match: attributes["teeth"] = int(teeth_match.group(1))
    
    if attributes:
        attributes["unit"] = "mm"
        
    return attributes

import json
from pathlib import Path
from typing import List, Dict, Any

ALIAS_PATH = Path(__file__).parent.parent / "db" / "aliases.json"

def load_aliases() -> Dict[str, List[str]]:
    if ALIAS_PATH.exists():
        with open(ALIAS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def get_search_keywords(name: str, spec: str, category: str = None, brand: str = None, mpn: str = None) -> List[str]:
    """[동의어] [치수] [제조사] 순서로 최적화된 검색 키워드 생성"""
    attrs = extract_attributes(spec)
    aliases = load_aliases()
    
    # 1. 동의어 (가장 먼저 배치하여 검색 범위 확장)
    expanded = []
    if category and category in aliases:
        expanded.extend(aliases[category])
    else:
        expanded.append(name)

    # 2. 치수 정보 (규격화된 문자열로 조합: 20x47x14)
    dim_str = ""
    if "inner_diameter" in attrs and "outer_diameter" in attrs:
        dim_str = f"{attrs['inner_diameter']}x{attrs['outer_diameter']}"
        if "width" in attrs:
            dim_str += f"x{attrs['width']}"
    elif "module" in attrs:
        dim_str = f"Mod{attrs['module']}"

    # 3. 키워드 조립
    final_keywords = [name]
    if "inner_diameter" in attrs:
        final_keywords.append(f"{attrs['inner_diameter']}mm")
    if "outer_diameter" in attrs:
        final_keywords.append(f"{attrs['outer_diameter']}mm")
    if "width" in attrs:
        final_keywords.append(f"{attrs['width']}mm")
    final_keywords.extend(expanded)

    for syn in expanded[:2]: # 너무 많아지지 않게 주요 동의어 2개만 조합
        query = f"{syn} {dim_str}"
        if brand: query += f" {brand}"
        final_keywords.append(query.strip())
    
    # 개별 핵심 정보들도 추가
    if mpn: final_keywords.append(mpn)
    
    return sorted(list(set(final_keywords)))

if __name__ == "__main__":
    test_spec = "Deep groove ball bearing. ID: 20mm, OD: 47mm, Width: 14.5 mm. ISO Class 6."
    print(f"Extracted: {extract_dimensions(test_spec)}")
