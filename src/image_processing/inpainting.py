"""
画像処理モジュール - OpenCVによるインペインティング機能
"""
import cv2
import numpy as np
import logging
from typing import List, Tuple, Optional

class TextInpainter:
    """OpenCVを使用してテキストを除去するクラス"""

    def __init__(self, method: str = 'ns', inpaint_radius: int = 3):
        """
        初期化

        Args:
            method: インペインティング手法 ('ns': Navier-Stokes, 'telea': Telea)
            inpaint_radius: インペインティング半径
        """
        self.method = method
        self.inpaint_radius = inpaint_radius
        self.logger = logging.getLogger(__name__)

        # インペインティング手法の設定
        if method.lower() == 'ns':
            self.cv2_method = cv2.INPAINT_NS
            self.logger.info("Navier-Stokes法を選択しました")
        elif method.lower() == 'telea':
            self.cv2_method = cv2.INPAINT_TELEA
            self.logger.info("Telea法を選択しました")
        else:
            raise ValueError("methodは'ns'または'telea'である必要があります")

    def create_mask(self, image: np.ndarray, bboxes: List[List[List[int]]]) -> np.ndarray:
        """
        バウンディングボックスからマスクを作成

        Args:
            image: 入力画像
            bboxes: バウンディングボックスのリスト [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]

        Returns:
            マスク画像（白: テキスト領域, 黒: 背景）
        """
        height, width = image.shape[:2]
        mask = np.zeros((height, width), dtype=np.uint8)

        for bbox in bboxes:
            # バウンディングボックスの座標をnumpy配列に変換
            points = np.array(bbox, dtype=np.int32)
            # 多角形を塗りつぶし
            cv2.fillPoly(mask, [points], 255)

        return mask

    def create_enlarged_mask(self, image: np.ndarray, bboxes: List[List[List[int]]],
                           expansion_pixels: int = 2) -> np.ndarray:
        """
        拡張されたマスクを作成（より自然な除去のため）

        Args:
            image: 入力画像
            bboxes: バウンディングボックスのリスト
            expansion_pixels: 拡張するピクセル数

        Returns:
            拡張されたマスク
        """
        height, width = image.shape[:2]
        mask = np.zeros((height, width), dtype=np.uint8)

        for bbox in bboxes:
            # バウンディングボックスの座標をnumpy配列に変換
            points = np.array(bbox, dtype=np.int32)

            # バウンディングボックスを少し拡張
            centroid = np.mean(points, axis=0)
            expanded_points = []

            for point in points:
                # 中心から外側に拡張
                direction = point - centroid
                direction_norm = direction / (np.linalg.norm(direction) + 1e-6)
                expanded_point = point + direction_norm * expansion_pixels
                expanded_points.append(expanded_point)

            expanded_points = np.array(expanded_points, dtype=np.int32)
            cv2.fillPoly(mask, [expanded_points], 255)

        return mask

    def remove_text(self, image: np.ndarray, bboxes: List[List[List[int]]],
                   use_enlarged_mask: bool = True) -> np.ndarray:
        """
        画像からテキストを除去

        Args:
            image: 入力画像
            bboxes: テキスト領域のバウンディングボックスリスト
            use_enlarged_mask: 拡張マスクを使用するかどうか

        Returns:
            テキストが除去された画像
        """
        try:
            # マスクの作成
            if use_enlarged_mask:
                mask = self.create_enlarged_mask(image, bboxes)
            else:
                mask = self.create_mask(image, bboxes)

            # インペインティング実行
            result = cv2.inpaint(image, mask, self.inpaint_radius, self.cv2_method)

            self.logger.info(f"Removed text from {len(bboxes)} regions")
            return result

        except Exception as e:
            self.logger.error(f"テキスト除去エラー: {e}")
            return image.copy()  # エラー時は元の画像を返す

    def remove_text_single_region(self, image: np.ndarray, bbox: List[List[int]]) -> np.ndarray:
        """
        単一のテキスト領域を除去

        Args:
            image: 入力画像
            bbox: 単一のバウンディングボックス

        Returns:
            テキストが除去された画像
        """
        return self.remove_text(image, [bbox])

    def remove_text_from_path(self, image_path: str, bboxes: List[List[List[int]]],
                             output_path: str = None) -> np.ndarray:
        """
        ファイルパスからテキストを除去

        Args:
            image_path: 入力画像パス
            bboxes: バウンディングボックスリスト
            output_path: 出力パス（Noneの場合は返すのみ）

        Returns:
            テキストが除去された画像
        """
        try:
            image = cv2.imread(image_path)
            if image is None:
                raise ValueError(f"画像が読み込めません: {image_path}")

            result = self.remove_text(image, bboxes)

            if output_path:
                cv2.imwrite(output_path, result)
                self.logger.info(f"結果を保存しました: {output_path}")

            return result

        except Exception as e:
            self.logger.error(f"ファイル処理エラー: {e}")
            return None

    def blend_with_original(self, inpainted_image: np.ndarray, original_image: np.ndarray,
                          blend_alpha: float = 0.1) -> np.ndarray:
        """
        インペインティング結果と元の画像をブレンド

        Args:
            inpainted_image: インペインティングされた画像
            original_image: 元の画像
            blend_alpha: ブレンド係数（0に近いほど元の画像に近い）

        Returns:
            ブレンドされた画像
        """
        try:
            # 画像サイズの確認
            if inpainted_image.shape != original_image.shape:
                raise ValueError("画像サイズが一致しません")

            # アルファブレンディング
            blended = cv2.addWeighted(original_image, blend_alpha,
                                    inpainted_image, 1 - blend_alpha, 0)

            return blended

        except Exception as e:
            self.logger.error(f"ブレンド処理エラー: {e}")
            return inpainted_image.copy()

    def preview_mask(self, image: np.ndarray, mask: np.ndarray) -> np.ndarray:
        """
        マスクを可視化

        Args:
            image: 元の画像
            mask: マスク画像

        Returns:
            マスクが重ねられた画像
        """
        try:
            # マスクをカラーに変換
            mask_color = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
            mask_color[mask_color > 0] = [0, 0, 255]  # 赤色で表示

            # 半透明で重ねる
            preview = cv2.addWeighted(image, 0.7, mask_color, 0.3, 0)

            return preview

        except Exception as e:
            self.logger.error(f"マスクプレビューエラー: {e}")
            return image.copy()

    def estimate_best_inpaint_radius(self, image: np.ndarray, bboxes: List[List[List[int]]]) -> int:
        """
        画像サイズとテキスト領域に基づいて最適なインペインティング半径を推定

        Args:
            image: 入力画像
            bboxes: バウンディングボックスリスト

        Returns:
            推定された最適半径
        """
        try:
            if not bboxes:
                return 3  # デフォルト値

            # テキスト領域の平均サイズを計算
            heights = []
            for bbox in bboxes:
                height = abs(bbox[2][1] - bbox[0][1])  # 高さを計算
                heights.append(height)

            avg_height = np.mean(heights)

            # 画像の高さに基づいて半径を調整
            image_height = image.shape[0]
            base_radius = max(1, int(avg_height / 20))

            # 画像サイズによる制限
            max_radius = min(10, int(image_height / 100))

            return min(base_radius, max_radius)

        except Exception as e:
            self.logger.error(f"半径推定エラー: {e}")
            return 3  # デフォルト値を返す


def create_inpainter(method: str = 'ns', inpaint_radius: int = 3) -> TextInpainter:
    """
    インペインタークラスのファクトリ関数

    Args:
        method: インペインティング手法
        inpaint_radius: インペインティング半径

    Returns:
        TextInpainterインスタンス
    """
    return TextInpainter(method, inpaint_radius)


if __name__ == "__main__":
    # テスト用コード
    logging.basicConfig(level=logging.INFO)

    # テスト用のダミーバウンディングボックス
    test_bboxes = [
        [[50, 50], [150, 50], [150, 80], [50, 80]],  # 矩形のテキスト領域
        [[200, 100], [280, 95], [285, 130], [205, 135]]  # 少し傾いたテキスト領域
    ]

    # ダミー画像でテスト
    test_image = np.ones((300, 400, 3), dtype=np.uint8) * 255  # 白い画像
    cv2.putText(test_image, "Test Text", (60, 70), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)

    # インペインターの作成
    inpainter = create_inpainter('ns', 3)

    # マスク作成のテスト
    mask = inpainter.create_mask(test_image, test_bboxes)
    print(f"マスク作成完了。形状: {mask.shape}")

    # テキスト除去のテスト
    result = inpainter.remove_text(test_image, test_bboxes)
    print(f"テキスト除去完了。結果形状: {result.shape}")

    # 結果保存
    cv2.imwrite("test_original.png", test_image)
    cv2.imwrite("test_mask.png", mask)
    cv2.imwrite("test_result.png", result)

    print("テスト完了")