import sqlite3
import json
import os
from pathlib import Path
from .models import MaterialMaster, Inventory

DEFAULT_DB_PATH = Path(__file__).parent.parent / "buybee.db"


def get_db_path() -> Path:
    return Path(os.environ.get("BUYBEE_DB_PATH", DEFAULT_DB_PATH))

def get_connection():
    return sqlite3.connect(get_db_path())

def init_db():
    """데이터베이스 테이블 초기화"""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # 자재 마스터 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS material_master (
                material_id TEXT PRIMARY KEY,
                material_name TEXT NOT NULL,
                category TEXT,
                brand TEXT,
                mpn TEXT,
                technical_specification TEXT,
                spec_attributes TEXT
            )
        """)
        
        # 재고 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                material_id TEXT PRIMARY KEY,
                current_stock INTEGER NOT NULL,
                safety_stock INTEGER NOT NULL,
                plant TEXT,
                last_updated TEXT,
                FOREIGN KEY (material_id) REFERENCES material_master (material_id)
            )
        """)
        conn.commit()

def save_material(material: MaterialMaster):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO material_master 
            (material_id, material_name, category, brand, mpn, technical_specification, spec_attributes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (material.material_id, material.material_name, material.category, 
              material.brand, material.mpn, material.technical_specification, json.dumps(material.spec_attributes)))
        conn.commit()

def save_inventory(inv: Inventory):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO inventory 
            (material_id, current_stock, safety_stock, plant, last_updated)
            VALUES (?, ?, ?, ?, ?)
        """, (inv.material_id, inv.current_stock, inv.safety_stock, 
              inv.plant, inv.last_updated.isoformat()))
        conn.commit()

if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {get_db_path()}")
