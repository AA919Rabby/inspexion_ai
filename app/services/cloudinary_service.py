import cloudinary
import cloudinary.uploader
from app.core.config import settings



cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET,
    secure=True,
)


class CloudinaryService:
    @staticmethod
    def upload_file(file_path:str,folder:str)->str:
        try:
            response=cloudinary.uploader.upload(
                file_path,
                folder=folder,
                resource_type="auto",
            )
            return response.get("secure_url")
        except Exception as e:
            print(f"Cloudinary upload error: {e}")
            return ""

cloudinary_service=CloudinaryService()
