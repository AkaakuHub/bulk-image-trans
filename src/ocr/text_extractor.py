"""
OCRモジュール - EasyOCRを使用したテキスト抽出機能
"""
import cv2
import numpy as np
import easyocr
from typing import List, Dict, Tuple, Optional
import logging

class TextExtractor:
    """EasyOCRを使用して画像からテキストを抽出するクラス"""

    def __init__(self, languages: List[str] = None, gpu: bool = True):
        """
        初期化

        Args:
            languages: 認識する言語のリスト (例: ['en', 'ja'])
            gpu: GPUを使用するかどうか
        """
        # ロギング設定
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

        self.languages = languages or ['en', 'ja']
        self.gpu = gpu
        self.reader = None
        self._initialize_reader()

    def _initialize_reader(self):
        """EasyOCRリーダーの初期化"""
        try:
            self.logger.info(f"Initializing EasyOCR with languages: {self.languages}")
            self.reader = easyocr.Reader(self.languages, gpu=self.gpu)
            self.logger.info("EasyOCR initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize EasyOCR: {e}")
            raise

    def extract_text(self, image_path: str) -> List[Dict]:
        """
        画像からテキストを抽出

        Args:
            image_path: 画像ファイルのパス

        Returns:
            抽出結果のリスト。各要素は以下のキーを含む辞書:
            - 'text': 検出されたテキスト
            - 'confidence': 信頼度 (0-1)
            - 'bbox': バウンディングボックス座標 [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
            - 'position': テキスト位置情報 (top_left, bottom_right)
        """
        try:
            # 画像の読み込み
            image = cv2.imread(image_path)
            if image is None:
                raise ValueError(f"Could not read image: {image_path}")

            # テキスト検出
            results = self.reader.readtext(image)

            # 結果の構造化
            extracted_data = []
            for bbox, text, confidence in results:
                # バウンディングボックスの座標を整数に変換
                bbox_int = [list(map(int, point)) for point in bbox]

                # 位置情報の抽出
                top_left = tuple(map(int, bbox[0]))
                bottom_right = tuple(map(int, bbox[2]))

                extracted_data.append({
                    'text': text.strip(),
                    'confidence': float(confidence),
                    'bbox': bbox_int,
                    'position': {
                        'top_left': top_left,
                        'bottom_right': bottom_right,
                        'width': bottom_right[0] - top_left[0],
                        'height': bottom_right[1] - top_left[1]
                    }
                })

            self.logger.info(f"Extracted {len(extracted_data)} text regions from {image_path}")
            return extracted_data

        except Exception as e:
            self.logger.error(f"Error extracting text from {image_path}: {e}")
            return []

    def extract_text_from_image(self, image: np.ndarray) -> List[Dict]:
        """
        numpy配列から直接テキストを抽出

        Args:
            image: OpenCV形式の画像配列

        Returns:
            抽出結果のリスト
        """
        try:
            results = self.reader.readtext(image)

            extracted_data = []
            for bbox, text, confidence in results:
                bbox_int = [list(map(int, point)) for point in bbox]
                top_left = tuple(map(int, bbox[0]))
                bottom_right = tuple(map(int, bbox[2]))

                extracted_data.append({
                    'text': text.strip(),
                    'confidence': float(confidence),
                    'bbox': bbox_int,
                    'position': {
                        'top_left': top_left,
                        'bottom_right': bottom_right,
                        'width': bottom_right[0] - top_left[0],
                        'height': bottom_right[1] - top_left[1]
                    }
                })

            return extracted_data

        except Exception as e:
            self.logger.error(f"Error extracting text from image array: {e}")
            return []

    def visualize_results(self, image_path: str, output_path: str = None) -> np.ndarray:
        """
        検出結果を可視化

        Args:
            image_path: 入力画像パス
            output_path: 出力画像パス（Noneの場合は画像を返す）

        Returns:
            検出結果が描画された画像
        """
        try:
            image = cv2.imread(image_path)
            results = self.extract_text(image_path)

            # 検出結果を描画
            for result in results:
                bbox = result['bbox']
                text = result['text']
                confidence = result['confidence']

                # バウンディングボックスを描画
                pts = np.array(bbox, np.int32)
                pts = pts.reshape((-1, 1, 2))
                cv2.polylines(image, [pts], True, (0, 255, 0), 2)

                # テキストと信頼度を表示
                label = f"{text} ({confidence:.2f})"
                cv2.putText(image, label,
                           tuple(bbox[0]),
                           cv2.FONT_HERSHEY_SIMPLEX,
                           0.7, (0, 255, 0), 2)

            if output_path:
                cv2.imwrite(output_path, image)
                self.logger.info(f"Visualization saved to {output_path}")

            return image

        except Exception as e:
            self.logger.error(f"Error visualizing results: {e}")
            return None


def create_mask_from_bboxes(image_shape: Tuple[int, int], bboxes: List[List[List[int]]]) -> np.ndarray:
    """
    バウンディングボックスからマスク画像を作成

    Args:
        image_shape: 画像の形状 (height, width)
        bboxes: バウンディングボックスのリスト

    Returns:
        マスク画像（白: テキスト領域, 黒: 背景）
    """
    height, width = image_shape[:2]
    mask = np.zeros((height, width), dtype=np.uint8)

    for bbox in bboxes:
        points = np.array(bbox, dtype=np.int32)
        cv2.fillPoly(mask, [points], 255)

    return mask


if __name__ == "__main__":
    # テスト用コード
    extractor = TextExtractor(['en', 'ja'])

    # テスト画像があれば実行
    test_image = "test_image.jpg"  # 実際の画像パスを指定

    import os
    if os.path.exists(test_image):
        results = extractor.extract_text(test_image)
        print(f"検出されたテキスト数: {len(results)}")

        for i, result in enumerate(results):
            print(f"{i+1}. テキスト: {result['text']}")
            print(f"   信頼度: {result['confidence']:.3f}")
            print(f"   位置: {result['position']}")
            print()

        # 可視化
        extractor.visualize_results(test_image, "output_visualization.jpg")
    else:
        print(f"テスト画像 {test_image} が見つかりません")