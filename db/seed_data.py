from datetime import datetime
from .models import MaterialMaster, Inventory
from .database import init_db, save_material, save_inventory

def seed():
    init_db()
    
    # 1. 자재 마스터 데이터 확장 (10종)
    materials = [
        # [Case 1] 범용 베어링 (Standard)
        MaterialMaster(
            MATERIAL_ID="MAT-BRG-001", MATERIAL_NAME="Ball Bearing 6204-ZZ", CATEGORY="Bearing",
            BRAND="NSK", MPN="6204ZZ",
            TECHNICAL_SPECIFICATION="Deep groove ball bearing. ID: 20mm, OD: 47mm, Width: 14mm. Steel material. Double metal shield. ISO Class 6.",
            spec_attributes={"inner_diameter": 20, "outer_diameter": 47, "width": 14, "unit": "mm", "precision": "Class 6", "material": "Steel"}
        ),
        # [Case 2] 고정밀 베어링 (High-Precision)
        MaterialMaster(
            MATERIAL_ID="MAT-BRG-002", MATERIAL_NAME="Angular Contact Bearing 7005-CTY", CATEGORY="Bearing",
            BRAND="FAG", MPN="7005-C-TYP4S",
            TECHNICAL_SPECIFICATION="High precision angular contact. ID: 25mm, OD: 47mm, Width: 12mm. P4S precision class.",
            spec_attributes={"inner_diameter": 25, "outer_diameter": 47, "width": 12, "unit": "mm", "precision": "P4S", "material": "Steel"}
        ),
        # [Case 3] 표준 평기어 (Standard Gear)
        MaterialMaster(
            MATERIAL_ID="MAT-GER-002", MATERIAL_NAME="Spur Gear Mod 2.0", CATEGORY="Gear",
            BRAND="KHK", MPN="SS2-30",
            TECHNICAL_SPECIFICATION="Module: 2.0. Teeth: 30. Pitch Diameter: 60mm. Material: S45C. Bore: 15mm.",
            spec_attributes={"module": 2.0, "teeth": 30, "bore": 15, "unit": "mm", "material": "S45c"}
        ),
        # [Case 4] 특수 재질 가이드 (Stainless Material)
        MaterialMaster(
            MATERIAL_ID="MAT-LNR-003", MATERIAL_NAME="Linear Block HSR20", CATEGORY="Guide",
            BRAND="THK", MPN="HSR20CA",
            TECHNICAL_SPECIFICATION="Size 20. Width: 63mm, Length: 74mm. Static Load: 27.4kN. Material: Stainless Steel (SUS).",
            spec_attributes={"size": 20, "width": 63, "length": 74, "unit": "mm", "material": "Stainless"}
        ),
        # [Case 5] 정밀 볼나사 (High-Precision Screw)
        MaterialMaster(
            MATERIAL_ID="MAT-SCW-004", MATERIAL_NAME="Ball Screw 1505", CATEGORY="Screw",
            BRAND="NSK", MPN="W1502FA",
            TECHNICAL_SPECIFICATION="Diameter: 15mm, Lead: 5mm. Precision grade C5. Overall length 500mm.",
            spec_attributes={"diameter": 15, "lead": 5, "precision": "C5", "unit": "mm", "material": "Steel"}
        ),
        # [Case 6] 축 커플링 (Coupling)
        MaterialMaster(
            MATERIAL_ID="MAT-CPL-005", MATERIAL_NAME="Flexible Coupling CP-25", CATEGORY="Coupling",
            BRAND="SUNGIL", MPN="SOH-25C",
            TECHNICAL_SPECIFICATION="Outer Diameter: 25mm, Length: 30mm. Bore 1: 8mm, Bore 2: 10mm. Aluminum alloy.",
            spec_attributes={"outer_diameter": 25, "width": 30, "bore1": 8, "bore2": 10, "unit": "mm", "material": "Aluminum"}
        )
    ]
    
    # 2. 재고 데이터 시나리오 설정
    inventories = [
        Inventory(MATERIAL_ID="MAT-BRG-001", CURRENT_STOCK=8, SAFETY_STOCK=20, PLANT="P100"),  # 부족 (정상)
        Inventory(MATERIAL_ID="MAT-BRG-002", CURRENT_STOCK=0, SAFETY_STOCK=5, PLANT="P100"),   # 긴급 (재고 0)
        Inventory(MATERIAL_ID="MAT-GER-002", CURRENT_STOCK=15, SAFETY_STOCK=10, PLANT="P100"), # 정상 (감지 안됨)
        Inventory(MATERIAL_ID="MAT-LNR-003", CURRENT_STOCK=2, SAFETY_STOCK=10, PLANT="P200"),  # 부족 (특수 재질)
        Inventory(MATERIAL_ID="MAT-SCW-004", CURRENT_STOCK=1, SAFETY_STOCK=3, PLANT="P100"),   # 부족 (고정밀)
        Inventory(MATERIAL_ID="MAT-CPL-005", CURRENT_STOCK=20, SAFETY_STOCK=20, PLANT="P100")  # 경계 (감지 안됨)
    ]
    
    # 3. 저장
    for m in materials: save_material(m)
    for i in inventories: save_inventory(i)

    print(f"Successfully seeded {len(materials)} materials with various shortage scenarios.")

if __name__ == "__main__":
    seed()
