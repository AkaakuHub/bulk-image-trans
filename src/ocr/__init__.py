"""
OCRモジュール
"""
from .text_extractor import TextExtractor, create_mask_from_bboxes

__all__ = ['TextExtractor', 'create_mask_from_bboxes']