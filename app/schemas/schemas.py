from typing import List,Optional,Any,Dict
from pydantic import BaseModel,HttpUrl,EmailStr
from datetime import datetime



class GoogleAuthRequest(BaseModel):
    id_token:str

class TokenResponse(BaseModel):
    access_token:str
    token_type:str="bearer"
    user:"UserOut"

class UserOut(BaseModel):
    id:int
    email:EmailStr
    full_name:Optional[str]
    avatar_url:Optional[str]
    created_at:datetime
    class Config:
        from_attributes:True

class UserUpdate(BaseModel):
    full_name:Optional[str]=None
    avatar_url:Optional[str]=None

class ImageOut(BaseModel):
    id:int
    file_path:str
    detected_category:str
    confidence_score:float
    yolo_detections:List[Dict[str,Any]]
    class Config:
        from_attributes:True

class InspectionSessionCreate(BaseModel):
    title:str="Asset Physical Inspection"
    asset_type:str="Machinery/Automotive/Warehouse"

class InspectionSessionOut(BaseModel):
    id:int
    user_id:int
    title:str
    asset_type:str
    status:str
    summary:Optional[str]
    critical_defects_count:int
    minor_defects_count:int
    total_images:int
    created_at:datetime
    class Config:
        from_attributes:True

class PDFReportOut(BaseModel):
    id:int
    session_id:int
    report_title:str
    file_path:str
    created_at:datetime
    class Config:
        from_attributes=True

class AnalyticsRatioResponse(BaseModel):
    total_inspections:int
    total_images_analyzed:int
    critical_defects:int
    minor_defects:int
    defect_ratio:float
    categories_breakdown:Dict[str,int]
    timeline_trend:List[Dict[str,Any]]

class RAGQueryRequest(BaseModel):
    session_id:int
    question:str

class RAGQueryResponse(BaseModel):
    session_id:int
    question:str
    answer:str
    context_sources:List[str]







