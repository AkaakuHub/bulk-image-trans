"""
テキスト再描画モジュール - Pillowによるテキスト描画機能
"""
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import os
import logging
from typing import List, Tuple, Optional, Dict, Any
from sklearn.cluster import KMeans

class TextRenderer:
    """Pillowを使用して翻訳テキストを描画するクラス"""

    def __init__(self, font_path: str = None, default_font_size: int = 12):
        """
        初期化

        Args:
            font_path: フォントファイルのパス
            default_font_size: デフォルトのフォントサイズ
        """
        self.font_path = font_path
        self.default_font_size = default_font_size
        self.logger = logging.getLogger(__name__)

        # フォントの初期化
        self.font = None
        self._initialize_font()

    def _initialize_font(self):
        """フォントの初期化"""
        try:
            if self.font_path and os.path.exists(self.font_path):
                self.font = ImageFont.truetype(self.font_path, self.default_font_size)
                self.logger.info(f"フォントを読み込みました: {self.font_path}")
            else:
                raise FileNotFoundError(f"フォントファイルが見つかりません: {self.font_path}")
        except Exception as e:
            self.logger.error(f"フォントの初期化に失敗: {e}")
            raise

    def set_font_size(self, size: int):
        """
        フォントサイズを設定

        Args:
            size: フォントサイズ
        """
        try:
            if self.font_path and os.path.exists(self.font_path):
                self.font = ImageFont.truetype(self.font_path, size)
            else:
                # デフォルトフォントではサイズ変更が難しいのでログのみ
                self.logger.warning("デフォルトフォントのためサイズ変更は制限されます")
        except Exception as e:
            self.logger.error(f"フォントサイズの設定に失敗: {e}")

    def wrap_text(self, text: str, max_width: int, font: ImageFont.FreeTypeFont = None) -> List[str]:
        """
        テキストを指定幅に合わせて折り返す（日本語対応）

        Args:
            text: 折り返すテキスト
            max_width: 最大幅（ピクセル）
            font: 使用するフォント（Noneの場合はself.fontを使用）

        Returns:
            折り返されたテキストの行リスト
        """
        if font is None:
            font = self.font

        lines = []
        current_line = ""

        # 1文字ずつ処理
        for char in text:
            # 現在の行に文字を追加した場合の幅を計算
            test_line = current_line + char
            bbox = font.getbbox(test_line)
            text_width = bbox[2] - bbox[0]

            if text_width <= max_width:
                current_line = test_line
            else:
                # 幅を超える場合は現在の行を確定して新しい行を開始
                if current_line:
                    lines.append(current_line)
                    current_line = char
                else:
                    # 1文字で幅を超える場合（非常に小さいmax_width）
                    lines.append(char)
                    current_line = ""

        # 最後の行を追加
        if current_line:
            lines.append(current_line)

        return lines

    def calculate_text_dimensions(self, text: str, font: ImageFont.FreeTypeFont = None) -> Tuple[int, int]:
        """
        テキストの寸法を計算

        Args:
            text: テキスト
            font: 使用するフォント

        Returns:
            (幅, 高さ)のタプル
        """
        if font is None:
            font = self.font

        try:
            bbox = font.getbbox(text)
            width = bbox[2] - bbox[0]
            height = bbox[3] - bbox[1]
            return width, height
        except Exception as e:
            self.logger.error(f"テキスト寸法の計算に失敗: {e}")
            return 100, 20  # デフォルト値

    def find_optimal_font_size(self, text: str, target_width: int, target_height: int,
                             min_size: int = 8, max_size: int = 72) -> int:
        """
        最適なフォントサイズを見つける

        Args:
            text: 描画するテキスト
            target_width: 目標幅
            target_height: 目標高さ
            min_size: 最小フォントサイズ
            max_size: 最大フォントサイズ

        Returns:
            最適なフォントサイズ
        """
        best_size = min_size
        best_fit_score = float('inf')

        for size in range(min_size, max_size + 1):
            try:
                if self.font_path and os.path.exists(self.font_path):
                    font = ImageFont.truetype(self.font_path, size)
                else:
                    font = ImageFont.load_default()

                # テキストを折り返して寸法を計算
                lines = self.wrap_text(text, target_width, font)
                total_height = len(lines) * self.calculate_text_dimensions("あ", font)[1]

                # フィットスコアを計算（小さいほど良い）
                width_fit = abs(target_width - max([self.calculate_text_dimensions(line, font)[0] for line in lines]))
                height_fit = abs(target_height - total_height)
                fit_score = width_fit + height_fit * 2  # 高さを重視

                if fit_score < best_fit_score and total_height <= target_height:
                    best_fit_score = fit_score
                    best_size = size

            except Exception as e:
                self.logger.warning(f"フォントサイズ {size} の計算に失敗: {e}")
                continue

        return best_size

    def extract_dominant_color(self, image: np.ndarray, bbox: List[List[int]],
                             n_colors: int = 3) -> Tuple[int, int, int]:
        """
        指定領域から主要な色を抽出

        Args:
            image: 入力画像
            bbox: バウンディングボックス [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
            n_colors: 抽出する色の数

        Returns:
            主要な色 (R, G, B)
        """
        try:
            # バウンディングボックスから矩形領域を抽出
            points = np.array(bbox, dtype=np.int32)
            x_coords = points[:, 0]
            y_coords = points[:, 1]

            x_min, x_max = np.min(x_coords), np.max(x_coords)
            y_min, y_max = np.min(y_coords), np.max(y_coords)

            # 領域を切り抜き
            region = image[y_min:y_max, x_min:x_max]

            # リサンプリングしてピクセルを収集
            small_region = cv2.resize(region, (50, 50))
            pixels = small_region.reshape(-1, 3)

            # K-meansクラスタリングで主要な色を抽出
            kmeans = KMeans(n_clusters=min(n_colors, len(pixels)), random_state=42, n_init=10)
            kmeans.fit(pixels)

            # 最も頻度の高いクラスタ中心を返す
            colors = kmeans.cluster_centers_.astype(int)
            return tuple(colors[0])  # 最初のクラスタ中心を返す

        except Exception as e:
            self.logger.error(f"色抽出エラー: {e}")
            return (0, 0, 0)  # デフォルト: 黒

    def render_text_with_outline(self, image: np.ndarray, text: str, position: Tuple[int, int],
                              bbox: List[List[int]], text_color: Tuple[int, int, int] = (0, 0, 0),
                              outline_color: Tuple[int, int, int] = (255, 255, 255),
                              outline_width: int = 2, font_size: int = None, auto_fit: bool = True) -> np.ndarray:
        """
        縁取り付きテキストを描画

        Args:
            image: 入力画像
            text: 描画するテキスト
            position: 描画位置 (x, y)
            bbox: バウンディングボックス（自動フィット用）
            text_color: テキスト色 (R, G, B)
            outline_color: 縁取り色 (R, G, B)
            outline_width: 縁取りの太さ
            font_size: フォントサイズ
            auto_fit: 自動サイズ調整を行うかどうか

        Returns:
            テキストが描画された画像
        """
        try:
            # PIL画像に変換
            pil_image = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
            draw = ImageDraw.Draw(pil_image)

            # バウンディングボックスの寸法を計算
            points = np.array(bbox, dtype=np.int32)
            x_coords = points[:, 0]
            y_coords = points[:, 1]
            bbox_width = np.max(x_coords) - np.min(x_coords)
            bbox_height = np.max(y_coords) - np.min(y_coords)

            # フォントサイズの設定
            if auto_fit:
                target_width = bbox_width - outline_width * 2  # 縁取り分の余白
                target_height = bbox_height - outline_width * 2
                font_size = self.find_optimal_font_size(text, target_width, target_height)

            # フォントの設定
            if font_size:
                self.set_font_size(font_size)

            # テキストの折り返し
            if auto_fit:
                target_width = bbox_width - outline_width * 2
                lines = self.wrap_text(text, target_width, self.font)
            else:
                lines = [text]

            # 縁取りテキスト描画
            y_offset = 0
            for line in lines:
                # 縁取りを描画（8方向にオフセットして描画）
                for dx in [-outline_width, 0, outline_width]:
                    for dy in [-outline_width, 0, outline_width]:
                        if dx == 0 and dy == 0:
                            continue  # 中心はスキップ
                        draw.text((position[0] + dx, position[1] + y_offset + dy), line,
                                 fill=outline_color, font=self.font)

                # メインのテキストを描画
                draw.text((position[0], position[1] + y_offset), line,
                         fill=text_color, font=self.font)

                # 行間を計算
                line_height = self.calculate_text_dimensions(line, self.font)[1]
                y_offset += line_height + 1  # 少しの行間

            # numpy配列に戻す
            result = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
            return result

        except Exception as e:
            self.logger.error(f"縁取りテキスト描画エラー: {e}")
            return image.copy()

    def render_text(self, image: np.ndarray, text: str, position: Tuple[int, int],
                   bbox: List[List[int]], color: Tuple[int, int, int] = None,
                   font_size: int = None, auto_fit: bool = True) -> np.ndarray:
        """
        画像にテキストを描画（縁取り付き）

        Args:
            image: 入力画像
            text: 描画するテキスト
            position: 描画位置 (x, y)
            bbox: バウンディングボックス（自動フィット用）
            color: テキスト色 (R, G, B) - Noneの場合は黒
            font_size: フォントサイズ
            auto_fit: 自動サイズ調整を行うかどうか

        Returns:
            テキストが描画された画像
        """
        # 黒いテキストに白い縁取りで描画
        text_color = (0, 0, 0)  # 黒
        outline_color = (255, 255, 255)  # 白
        return self.render_text_with_outline(image, text, position, bbox, text_color, outline_color, 2, font_size, auto_fit)

    def render_text_centered(self, image: np.ndarray, text: str, bbox: List[List[int]],
                           color: Tuple[int, int, int] = None) -> np.ndarray:
        """
        バウンディングボックスの左上からテキストを描画（元のテキスト位置に合わせる）

        Args:
            image: 入力画像
            text: 描画するテキスト
            bbox: バウンディングボックス
            color: テキスト色

        Returns:
            テキストが描画された画像
        """
        try:
            # バウンディングボックスの左上座標を計算
            points = np.array(bbox, dtype=np.int32)
            x_coords = points[:, 0]
            y_coords = points[:, 1]

            # 左上座標を取得（若干のマージンを加える）
            top_left_x = int(np.min(x_coords)) + 2
            top_left_y = int(np.min(y_coords)) + 2

            # 左上から描画
            result = self.render_text(image, text, (top_left_x, top_left_y), bbox, color)

            return result

        except Exception as e:
            self.logger.error(f"テキスト描画エラー: {e}")
            return image.copy()

    def batch_render_text(self, image: np.ndarray, text_data: List[Dict[str, Any]]) -> np.ndarray:
        """
        複数のテキストを一括で描画

        Args:
            image: 入力画像
            text_data: テキストデータのリスト。各要素は以下のキーを含む:
                - 'text': 描画するテキスト
                - 'bbox': バウンディングボックス
                - 'color': テキスト色（オプション）
                - 'position': 描画位置（オプション）

        Returns:
            テキストが描画された画像
        """
        result = image.copy()

        for data in text_data:
            try:
                text = data['text']
                bbox = data['bbox']
                color = data.get('color')
                position = data.get('position')

                if position:
                    result = self.render_text(result, text, position, bbox, color)
                else:
                    result = self.render_text_centered(result, text, bbox, color)

            except Exception as e:
                self.logger.error(f"バッチ描画エラー: {e}")
                continue

        return result


def create_renderer(font_path: str = None, default_font_size: int = 12) -> TextRenderer:
    """
    テキストレンダラークラスのファクトリ関数

    Args:
        font_path: フォントファイルのパス
        default_font_size: デフォルトのフォントサイズ

    Returns:
        TextRendererインスタンス
    """
    return TextRenderer(font_path, default_font_size)


if __name__ == "__main__":
    # テスト用コード
    logging.basicConfig(level=logging.INFO)

    # テスト用画像
    test_image = np.ones((300, 400, 3), dtype=np.uint8) * 255  # 白い背景

    # テスト用バウンディングボックス
    test_bbox = [[50, 50], [200, 50], [200, 100], [50, 100]]

    # レンダラーの作成
    renderer = create_renderer()

    # テキスト描画テスト
    test_text = "これはテスト用の日本語テキストです。"
    result = renderer.render_text_centered(test_image, test_text, test_bbox)

    # 結果保存
    cv2.imwrite("test_text_render.png", result)

    print("テキスト描画テスト完了")