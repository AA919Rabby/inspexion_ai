import os
from typing import List,Dict,Any
from ultralytics import YOLO
import cv2
import numpy as np



class YOLOService:
    def __init__(self,model_name:str="yolov8n.pt"):
        self.model=YOLO(model_name)
    def process_image(self,file_path:str)->Dict[str,Any]:
        results=self.model(file_path,conf=0.25)
        detections:List[Dict[str,Any]]=[]
        highest_conf=0.0
        primary_category="Physical Asset (Clean)"
        for r in results:
            boxes=r.boxes
            for box in boxes:
                cls_id=int(box.cls[0].item())
                label=self.model.names[cls_id]
                conf=float(box.conf[0].item())
                xyxy=[round(float(c),2) for c in box.xyxy[0].tolist()]
                detections.append({
                    "label":label,
                    "confidence":round(conf,4),
                    "box":xyxy
                })
                if conf > highest_conf:
                    highest_conf=conf
                    primary_category=label
        return {
            "primary_category":primary_category,
            "confidence_score":round(highest_conf,4),
            "detections":detections
        }

yolo_service=YOLOService()





