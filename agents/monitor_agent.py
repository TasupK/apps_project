import uuid
import json
from datetime import datetime
from db.database import get_connection
from db.models import ShortageEvent
from tools.dimension_extractor import get_search_keywords

def scan_inventory():
    """재고를 스캔하여 부족(Current < Safety)한 품목을 찾아 이벤트를 생성합니다."""
    events = []
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # 재고와 마스터 정보를 조인하여 부족분 조회
        query = """
            SELECT 
                m.material_id, m.material_name, m.category, m.brand, m.mpn, m.technical_specification, m.spec_attributes,
                i.current_stock, i.safety_stock, i.plant
            FROM inventory i
            JOIN material_master m ON i.material_id = m.material_id
            WHERE i.current_stock < i.safety_stock
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        
        for row in rows:
            mid, name, cat, brand, mpn, spec, spec_attr_json, current, safety, plant = row
            shortage_qty = safety - current
            
            # JSON 복원
            spec_attributes = json.loads(spec_attr_json) if spec_attr_json else {}
            
            # 검색 키워드 추출 (보완된 버전: 브랜드, 형번, 동의어 포함)
            keywords = get_search_keywords(name, spec, category=cat, brand=brand, mpn=mpn)
            
            event = ShortageEvent(
                event_id=f"SE-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}",
                material_id=mid,
                material_name=name,
                category=cat,
                brand=brand,
                mpn=mpn,
                plant=plant,
                current_stock=current,
                safety_stock=safety,
                shortage_qty=shortage_qty,
                technical_specification=spec,
                spec_attributes=spec_attributes,
                search_keywords=keywords
            )
            events.append(event)
            
    return events

def run_monitor():
    print(f"[{datetime.now().isoformat()}] Monitoring started...")
    shortages = scan_inventory()
    
    if not shortages:
        print("No shortages detected.")
        return
    
    print(f"Detected {len(shortages)} shortages!")
    for ev in shortages:
        # JSON 파일로 저장 (Phase 2에서 읽어갈 수 있도록)
        output_path = f"shortage_event_{ev.material_id}.json"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(ev.model_dump_json(indent=2))
        
        print(f" - [{ev.material_id}] {ev.material_name}: {ev.shortage_qty} items needed. Event saved to {output_path}")

if __name__ == "__main__":
    run_monitor()
