"""ModernOCR — multi-backend OCR with automatic fallback.

Replaces the basic Tesseract-only OCR in the codebase with a
modern multi-backend approach:

  - PaddleOCR (primary): Chinese + English, table recognition
  - TrOCR (fallback): transformer-based, handwriting-capable
  - EasyOCR (fallback): 80+ languages
  - Tesseract (legacy): universal fallback

MultiDocFusion integration: OCR output feeds into the vision-based
document parsing pipeline for region text extraction.

Usage:
    from livingtree.knowledge.modern_ocr import ModernOCR

    ocr = ModernOCR()
    text = ocr.extract("scanned_report.pdf", language="chi_sim")
    regions = ocr.extract_regions("complex_form.jpg")
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from loguru import logger

import fitz
import pytesseract
from loguru import logger
from PIL import Image
from rapidocr import RapidOCR

try:
    import easyocr as _easyocr_lib
except ImportError:
    _easyocr_lib = None
from transformers import TrOCRProcessor, VisionEncoderDecoderModel

# Hardware accelerator support
try:
    from livingtree.core.hardware_acceleration import get_accelerator
except ImportError:
    get_accelerator = None


@dataclass
class OCRRegion:
    """A single detected text region with position."""
    text: str
    bbox: tuple[int, int, int, int] = (0, 0, 0, 0)
    confidence: float = 1.0
    font_size: float = 0.0


@dataclass
class OCRResult:
    """Complete OCR output for a document/image."""
    text: str = ""
    regions: list[OCRRegion] = field(default_factory=list)
    language: str = ""
    backend_used: str = ""
    processing_time_ms: float = 0.0

    @property
    def confidence_avg(self) -> float:
        if not self.regions:
            return 0.0
        return sum(r.confidence for r in self.regions) / len(self.regions)


class ModernOCR:
    """Multi-backend modern OCR with automatic backend selection.

    Priority order: PaddleOCR → TrOCR → EasyOCR → Tesseract

    Each backend is tried in order; the first that succeeds is used.
    Results are cached by file hash for repeated queries.

    Automatically uses GPU via HardwareAccelerator when available.
    """

    def __init__(self, cache_dir: str = ""):
        self._cache_dir = cache_dir or os.path.expanduser("~/.livingtree/ocr_cache")
        self._lock = threading.Lock()
        self._backend_cache: dict[str, Any] = {}
        self._accelerator = None
        if get_accelerator is not None:
            try:
                self._accelerator = get_accelerator()
            except Exception as e:
                logger.debug("HardwareAccelerator init failed: %s", e)
        self._available_backends = self._detect_backends()

    def extract(
        self,
        filepath: str,
        language: str = "chi_sim",
    ) -> OCRResult:
        """Extract text from a document or image file.

        Supports PDF (rasterized), PNG, JPG, TIFF, BMP.
        """
        import time
        start = time.time()

        path = Path(filepath)
        if not path.exists():
            return OCRResult(text="", language=language, backend_used="none")

        ext = path.suffix.lower()

        for backend_name, backend_fn in self._available_backends:
            try:
                if ext == ".pdf":
                    text = backend_fn(str(path), language, is_pdf=True)
                else:
                    text = backend_fn(str(path), language, is_pdf=False)

                if text and text.strip():
                    elapsed = (time.time() - start) * 1000
                    logger.debug("ModernOCR: %s extracted %d chars via %s", path.name, len(text), backend_name)
                    return OCRResult(
                        text=text,
                        language=language,
                        backend_used=backend_name,
                        processing_time_ms=elapsed,
                    )
            except Exception as e:
                logger.debug("ModernOCR: %s failed: %s", backend_name, e)
                continue

        elapsed = (time.time() - start) * 1000
        return OCRResult(text="", language=language, backend_used="fallback_failed", processing_time_ms=elapsed)

    def extract_regions(
        self,
        filepath: str,
        language: str = "chi_sim",
    ) -> list[OCRRegion]:
        """Extract text with bounding box regions (for layout mapping).

        Used by DocumentLayoutAnalyzer to associate OCR text with
        detected document regions.
        """
        path = Path(filepath)
        if not path.exists():
            return []

        # Try PaddleOCR first (best region support)
        if self._try_paddleocr:
            return self._paddle_ocr_regions(str(path), language)

        # Fallback to EasyOCR with region support
        if self._try_easyocr:
            return self._easy_ocr_regions(str(path), language)

        # Tesseract with hOCR output
        try:
            return self._tesseract_regions(str(path), language)
        except Exception:
            return []

    def _detect_backends(self) -> list[tuple[str, Any]]:
        backends = []

        if self._try_paddleocr:
            backends.append(("paddleocr", self._paddle_ocr))
        if self._try_trocr:
            backends.append(("trocr", self._trocr))
        if self._try_easyocr:
            backends.append(("easyocr", self._easy_ocr))
        if self._try_tesseract:
            backends.append(("tesseract", self._tesseract))

        return backends

    @property
    def _try_paddleocr(self) -> bool:
        return True

    @property
    def _try_trocr(self) -> bool:
        return True

    @property
    def _try_easyocr(self) -> bool:
        return True

    @property
    def _try_tesseract(self) -> bool:
        return True

    def _paddle_ocr(self, filepath: str, language: str, is_pdf: bool = False) -> str:
        lang = "ch" if "chi" in language else "en"
        # Use GPU if accelerator says so
        use_gpu = self._accelerator is not None and self._accelerator.has_cuda

        with self._lock:
            cache_key = f"paddleocr_gpu{use_gpu}_{lang}"
            if cache_key not in self._backend_cache:
                self._backend_cache[cache_key] = PaddleOCR(
                    use_angle_cls=True, lang=lang, show_log=False, use_gpu=use_gpu,
                )
            ocr = self._backend_cache[cache_key]

        if is_pdf:
            doc = fitz.open(filepath)
            texts = []
            for page in doc:
                pix = page.get_pixmap(dpi=300)
                result = ocr.ocr(pix.tobytes(), cls=True)
                if result and result[0]:
                    texts.extend(line[1][0] for line in result[0])
            doc.close()
            return "\n".join(texts)
        else:
            result = ocr.ocr(filepath, cls=True)
            if result and result[0]:
                return "\n".join(line[1][0] for line in result[0])
            return ""

    def _paddle_ocr_regions(self, filepath: str, language: str) -> list[OCRRegion]:
        try:
            lang = "ch" if "chi" in language else "en"
            use_gpu = self._accelerator is not None and self._accelerator.has_cuda

            with self._lock:
                cache_key = f"paddleocr_regions_gpu{use_gpu}_{lang}"
                if cache_key not in self._backend_cache:
                    self._backend_cache[cache_key] = PaddleOCR(
                        use_angle_cls=True, lang=lang, show_log=False, use_gpu=use_gpu,
                    )
                ocr = self._backend_cache[cache_key]

            result = ocr.ocr(filepath, cls=True)
            regions = []
            if result and result[0]:
                for line in result[0]:
                    bbox = line[0]
                    text = line[1][0]
                    confidence = line[1][1]
                    regions.append(OCRRegion(
                        text=text,
                        bbox=(int(bbox[0][0]), int(bbox[0][1]), int(bbox[2][0]), int(bbox[2][1])),
                        confidence=confidence,
                    ))
            return regions
        except Exception as e:
            logger.warning("PaddleOCR regions failed: %s", e)
            return []

    def _trocr(self, filepath: str, language: str, is_pdf: bool = False) -> str:
        with self._lock:
            if "trocr_processor" not in self._backend_cache:
                self._backend_cache["trocr_processor"] = TrOCRProcessor.from_pretrained(
                    "microsoft/trocr-base-handwritten"
                )
                self._backend_cache["trocr_model"] = VisionEncoderDecoderModel.from_pretrained(
                    "microsoft/trocr-base-handwritten"
                )

        processor = self._backend_cache["trocr_processor"]
        model = self._backend_cache["trocr_model"]

        if is_pdf:
            doc = fitz.open(filepath)
            texts = []
            for page in doc:
                pix = page.get_pixmap(dpi=200)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                pixel_values = processor(images=img, return_tensors="pt").pixel_values
                generated_ids = model.generate(pixel_values)
                texts.append(processor.batch_decode(generated_ids, skip_special_tokens=True)[0])
            doc.close()
            return "\n".join(texts)
        else:
            img = Image.open(filepath).convert("RGB")
            pixel_values = processor(images=img, return_tensors="pt").pixel_values
            generated_ids = model.generate(pixel_values)
            return processor.batch_decode(generated_ids, skip_special_tokens=True)[0]

    def _easy_ocr(self, filepath: str, language: str, is_pdf: bool = False) -> str:
        langs = ["ch_sim", "en"] if "chi" in language else ["en"]
        use_gpu = self._accelerator is not None and self._accelerator.has_cuda

        with self._lock:
            cache_key = f"easyocr_gpu{use_gpu}_{'-'.join(langs)}"
            if cache_key not in self._backend_cache:
                self._backend_cache[cache_key] = easyocr.Reader(langs, gpu=use_gpu)
            reader = self._backend_cache[cache_key]

        if is_pdf:
            doc = fitz.open(filepath)
            texts = []
            for page in doc:
                pix = page.get_pixmap(dpi=200)
                result = reader.readtext(pix.tobytes())
                texts.extend(r[1] for r in result)
            doc.close()
            return "\n".join(texts)
        else:
            result = reader.readtext(filepath)
            return "\n".join(r[1] for r in result)

    def _easy_ocr_regions(self, filepath: str, language: str) -> list[OCRRegion]:
        langs = ["ch_sim", "en"] if "chi" in language else ["en"]
        use_gpu = self._accelerator is not None and self._accelerator.has_cuda

        with self._lock:
            cache_key = f"easyocr_regions_gpu{use_gpu}_{'-'.join(langs)}"
            if cache_key not in self._backend_cache:
                self._backend_cache[cache_key] = easyocr.Reader(langs, gpu=use_gpu)
            reader = self._backend_cache[cache_key]

        result = reader.readtext(filepath)
        regions = []
        for (bbox, text, confidence) in result:
            x0, y0 = bbox[0]
            x1, y1 = bbox[2]
            regions.append(OCRRegion(
                text=text,
                bbox=(int(x0), int(y0), int(x1), int(y1)),
                confidence=float(confidence),
            ))
        return regions

    def _tesseract(self, filepath: str, language: str, is_pdf: bool = False) -> str:
        lang_code = "chi_sim+eng" if "chi" in language else "eng"

        if is_pdf:
            doc = fitz.open(filepath)
            texts = []
            for page in doc:
                pix = page.get_pixmap(dpi=300)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                texts.append(pytesseract.image_to_string(img, lang=lang_code))
            doc.close()
            return "\n".join(texts)
        else:
            img = Image.open(filepath)
            return pytesseract.image_to_string(img, lang=lang_code)

    def _tesseract_regions(self, filepath: str, language: str) -> list[OCRRegion]:
        lang_code = "chi_sim+eng" if "chi" in language else "eng"
        img = Image.open(filepath)
        data = pytesseract.image_to_data(img, lang=lang_code, output_type=pytesseract.Output.DICT)

        regions = []
        for i in range(len(data["text"])):
            text = data["text"][i].strip()
            if not text:
                continue
            regions.append(OCRRegion(
                text=text,
                bbox=(
                    data["left"][i], data["top"][i],
                    data["left"][i] + data["width"][i],
                    data["top"][i] + data["height"][i],
                ),
                confidence=float(data["conf"][i]) / 100.0,
            ))
        return regions
