import unittest
import os
import json
from db.database import init_db, get_connection, save_material, save_inventory
from db.models import MaterialMaster, Inventory
from tools.dimension_extractor import extract_attributes, get_search_keywords
from agents.monitor_agent import scan_inventory

class TestPhase1(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 테스트용 임시 DB 초기화
        init_db()
        
    def test_dimension_extraction(self):
        """치수 추출 로직 검증"""
        spec = "ID: 25mm, OD: 52mm, W: 15mm. ISO P6."
        attrs = extract_attributes(spec)
        self.assertEqual(attrs["inner_diameter"], 25.0)
        self.assertEqual(attrs["outer_diameter"], 52.0)
        self.assertEqual(attrs["width"], 15.0)
        self.assertEqual(attrs["unit"], "mm")

    def test_query_expansion(self):
        """검색어 확장 로직 검증 (동의어 포함)"""
        name = "Ball Bearing 6205"
        spec = "ID: 25mm, OD: 52mm"
        category = "Bearing"
        keywords = get_search_keywords(name, spec, category=category)
        
        # 필수 요소 포함 확인
        self.assertIn("Ball Bearing 6205", keywords)
        self.assertIn("25.0mm", keywords)
        self.assertIn("Roller Bearing", keywords) # 동의어 사전의 값
        self.assertIn("회전 베어링", keywords)      # 국문 동의어

    def test_shortage_detection(self):
        """결품 감지 로직 검증"""
        # 테스트 데이터 삽입
        m = MaterialMaster(
            MATERIAL_ID="TEST-MAT-01",
            MATERIAL_NAME="Test Component",
            CATEGORY="Gear",
            TECHNICAL_SPECIFICATION="Mod 1.5, z20",
            spec_attributes={"module": 1.5, "teeth": 20}
        )
        save_material(m)
        
        # 부족 상태 시나리오
        inv = Inventory(
            MATERIAL_ID="TEST-MAT-01",
            CURRENT_STOCK=5,
            SAFETY_STOCK=10,
            PLANT="TEST-PLANT"
        )
        save_inventory(inv)
        
        # 감지 실행
        shortages = scan_inventory()
        self.assertTrue(any(s.material_id == "TEST-MAT-01" for s in shortages))
        
        # 수량 계산 검증 (10 - 5 = 5)
        event = next(s for s in shortages if s.material_id == "TEST-MAT-01")
        self.assertEqual(event.shortage_qty, 5)

if __name__ == "__main__":
    unittest.main()
