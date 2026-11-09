"""Image preprocessing, validation, orientation normalization, and safe compression."""
import base64
import io
from pathlib import Path
from typing import Tuple, Optional, Dict, Any, Union
import numpy as np
from PIL import Image, ImageOps

class ImageValidationError(Exception):
    """Raised when an image fails integrity, dimension, or security checks."""
    pass

class LowImageQualityError(ImageValidationError):
    """Raised when an image is blurry, corrupt, or below legible threshold."""
    pass

class ImageProcessor:
    """Preprocesses medical images for Groq Vision OCR."""

    MIN_DIMENSION: int = 32
    MAX_DIMENSION: int = 4096
    TARGET_MAX_DIMENSION: int = 2048
    SUPPORTED_FORMATS: Tuple[str, ...] = ("PNG", "JPEG", "JPG", "WEBP")

    @classmethod
    def load_and_validate_image(
        cls,
        image_input: Union[bytes, str, Path],
        blur_check: bool = True
    ) -> Image.Image:
        """Validate and load image from raw bytes or filesystem path."""
        if isinstance(image_input, (str, Path)):
            path = Path(image_input)
            if not path.exists():
                raise ImageValidationError(f"Image file does not exist: {path}")
            with open(path, "rb") as fp:
                raw_bytes = fp.read()
        elif isinstance(image_input, bytes):
            raw_bytes = image_input
        else:
            raise ImageValidationError("Invalid image input type; expected bytes, str, or Path.")

        if len(raw_bytes) == 0:
            raise ImageValidationError("Empty image payload provided.")

        try:
            temp_buf = io.BytesIO(raw_bytes)
            with Image.open(temp_buf) as probe:
                probe.verify()
        except Exception as exc:
            raise ImageValidationError(f"Image integrity verification failed: {str(exc)}") from exc

        buf = io.BytesIO(raw_bytes)
        img = Image.open(buf)
        img_format = (img.format or "").upper()
        if img_format not in cls.SUPPORTED_FORMATS and img_format != "MPO":
            raise ImageValidationError(f"Unsupported image format '{img_format}'. Supported: {cls.SUPPORTED_FORMATS}")

        try:
            img = ImageOps.exif_transpose(img)
        except Exception:
            pass

        width, height = img.size
        if width < cls.MIN_DIMENSION or height < cls.MIN_DIMENSION:
            raise LowImageQualityError(
                f"Image dimensions ({width}x{height}) below minimum required {cls.MIN_DIMENSION}x{cls.MIN_DIMENSION} pixels."
            )

        if width > cls.MAX_DIMENSION or height > cls.MAX_DIMENSION:
            raise ImageValidationError(
                f"Image dimensions ({width}x{height}) exceed maximum allowed {cls.MAX_DIMENSION}x{cls.MAX_DIMENSION} pixels."
            )

        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")

        if blur_check and cls.is_low_quality_or_blurry(img):
            raise LowImageQualityError("Image sharpness is insufficient for reliable character recognition.")

        return img

    @classmethod
    def is_low_quality_or_blurry(cls, img: Image.Image, threshold: float = 12.0) -> bool:
        """Evaluate image sharpness using discrete Laplacian variance."""
        try:
            gray = img.convert("L")
            arr = np.array(gray, dtype=np.float32)
            if arr.shape[0] < 8 or arr.shape[1] < 8:
                return True
            laplacian = (
                -4 * arr[1:-1, 1:-1]
                + arr[:-2, 1:-1]
                + arr[2:, 1:-1]
                + arr[1:-1, :-2]
                + arr[1:-1, 2:]
            )
            variance = float(laplacian.var())
            return variance < threshold
        except Exception:
            return False

    @classmethod
    def resize_if_needed(cls, img: Image.Image) -> Image.Image:
        """Proportionally downscale image if dimensions exceed target maximum."""
        width, height = img.size
        max_dim = max(width, height)
        if max_dim <= cls.TARGET_MAX_DIMENSION:
            return img

        scale = cls.TARGET_MAX_DIMENSION / float(max_dim)
        new_width = max(cls.MIN_DIMENSION, int(width * scale))
        new_height = max(cls.MIN_DIMENSION, int(height * scale))
        return img.resize((new_width, new_height), Image.Resampling.LANCZOS)

    @classmethod
    def to_base64_data_url(cls, img: Image.Image, format_name: str = "PNG") -> str:
        """Convert Pillow Image to a base64 Data URL string."""
        processed = cls.resize_if_needed(img)
        buf = io.BytesIO()
        target_fmt = "JPEG" if format_name.upper() in ("JPEG", "JPG") else "PNG"
        if target_fmt == "JPEG" and processed.mode != "RGB":
            processed = processed.convert("RGB")
        processed.save(buf, format=target_fmt, quality=88 if target_fmt == "JPEG" else None)
        b64_str = base64.b64encode(buf.getvalue()).decode("utf-8")
        mime = "image/jpeg" if target_fmt == "JPEG" else "image/png"
        return f"data:{mime};base64,{b64_str}"

    @classmethod
    def bytes_to_base64_data_url(cls, raw_bytes: bytes, format_hint: str = "PNG") -> str:
        """Load, validate, and convert raw image bytes to a base64 Data URL."""
        img = cls.load_and_validate_image(raw_bytes, blur_check=False)
        return cls.to_base64_data_url(img, format_name=format_hint)
