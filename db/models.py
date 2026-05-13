from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class MaterialMaster(BaseModel):
    """자재 마스터 정보 (스펙 중심)"""
    model_config = ConfigDict(populate_by_name=True)

    material_id: str = Field(..., alias="MATERIAL_ID")
    material_name: str = Field(..., alias="MATERIAL_NAME")
    category: str = Field(..., alias="CATEGORY")
    brand: Optional[str] = Field(None, alias="BRAND")  # 제조사 브랜드
    mpn: Optional[str] = Field(None, alias="MPN")      # 제조사 형번
    technical_specification: str = Field(..., alias="TECHNICAL_SPECIFICATION")
    spec_attributes: Dict[str, Any] = Field(default_factory=dict)  # 정규화된 속성 데이터 (JSON)
    
class Inventory(BaseModel):
    """재고 스냅샷 정보"""
    model_config = ConfigDict(populate_by_name=True)

    material_id: str = Field(..., alias="MATERIAL_ID")
    current_stock: int = Field(..., alias="CURRENT_STOCK")
    safety_stock: int = Field(..., alias="SAFETY_STOCK")
    plant: str = Field(..., alias="PLANT")
    last_updated: datetime = Field(default_factory=datetime.now)

class ShortageEvent(BaseModel):
    """결품 감지 시 발생되는 이벤트 포맷"""
    event_id: str
    status: str = "SHORTAGE_DETECTED"
    material_id: str
    material_name: str
    category: str
    brand: Optional[str] = None
    mpn: Optional[str] = None
    plant: str
    current_stock: int
    safety_stock: int
    shortage_qty: int
    technical_specification: str
    spec_attributes: Dict[str, Any] = Field(default_factory=dict)  # 정규화된 속성 데이터 전달
    search_keywords: List[str]
    detected_at: datetime = Field(default_factory=datetime.now)
