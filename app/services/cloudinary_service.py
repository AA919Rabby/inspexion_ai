import io
import cloudinary
import cloudinary.uploader
from app.core.config import settings

cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET,
    secure=True
)

class CloudinaryService:
    @staticmethod
    def upload_image_bytes(image_bytes: bytes, folder: str = "inspexion/avatars") -> str:
        """
        Takes raw image bytes, converts to an in-memory BytesIO stream,
        and uploads directly to Cloudinary.
        """
        try:
            stream = io.BytesIO(image_bytes)
            response = cloudinary.uploader.upload(
                stream,
                folder=folder,
                resource_type="image"
            )
            url = response.get("secure_url", "")
            print(f"✅ Cloudinary avatar upload SUCCESS: {url}")
            return url
        except Exception as e:
            print(f"❌ Cloudinary avatar upload ERROR: {e}")
            return ""

    @staticmethod
    def upload_file(file_path: str, folder: str) -> str:
        try:
            r_type = "raw" if file_path.endswith(".pdf") else "auto"
            response = cloudinary.uploader.upload(
                file_path,
                folder=folder,
                resource_type=r_type
            )
            return response.get("secure_url", "")
        except Exception as e:
            print(f"🔥 Cloudinary file upload error: {e}")
            return ""

cloudinary_service = CloudinaryService()