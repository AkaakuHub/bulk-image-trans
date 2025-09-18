#!/usr/bin/env python3
"""
テキスト描画デバッグ用スクリプト
"""
import sys
import os
import cv2
import numpy as np

# srcディレクトリをパスに追加
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from text_rendering.text_renderer import TextRenderer

def create_test_image():
    """テスト用画像を作成"""
    # 複雑な背景を持つテスト画像
    image = np.ones((400, 600, 3), dtype=np.uint8) * 200  # グレー背景

    # 背景に模様を追加（デバッグしやすくするため）
    cv2.rectangle(image, (50, 50), (550, 350), (180, 180, 180), -1)
    cv2.circle(image, (300, 200), 80, (160, 160, 160), -1)

    # テキストエリアを示す矩形
    cv2.rectangle(image, (100, 100), (200, 150), (100, 100, 255), 2)  # 青
    cv2.rectangle(image, (250, 120), (400, 180), (100, 255, 100), 2)  # 緑
    cv2.rectangle(image, (150, 220), (350, 280), (255, 100, 100), 2)  # 赤

    return image

def test_text_rendering():
    """テキスト描画の各種パターンをテスト"""
    print("=== テキスト描画デバッグ開始 ===")

    # テスト画像を作成
    test_image = create_test_image()

    # テキストレンダラーの初期化
    font_path = os.path.join(os.path.dirname(__file__), '..', 'fonts', 'NotoSansJP-Regular.ttf')
    if not os.path.exists(font_path):
        print(f"警告: フォントファイルが見つかりません: {font_path}")
        font_path = None
    else:
        print(f"✅ フォントファイルが見つかりました: {font_path}")

    renderer = TextRenderer(font_path=font_path, default_font_size=16)

    # テストケース
    test_cases = [
        {
            'text': '商品情報',
            'position': (100, 100),
            'bbox': [[100, 100], [200, 100], [200, 150], [100, 150]],
            'name': '短い日本語'
        },
        {
            'text': 'これは長い日本語のテキストです。折り返しが正しく動作するかテストします。',
            'position': (250, 120),
            'bbox': [[250, 120], [400, 120], [400, 180], [250, 180]],
            'name': '長い日本語（折り返し）'
        },
        {
            'text': '日本語とEnglish混合テキスト',
            'position': (150, 220),
            'bbox': [[150, 220], [350, 220], [350, 280], [150, 280]],
            'name': '日英混合'
        }
    ]

    # 各テストケースを実行
    for i, case in enumerate(test_cases):
        print(f"\n--- テスト {i+1}: {case['name']} ---")
        print(f"テキスト: {case['text']}")
        print(f"位置: {case['position']}")
        print(f"バウンディングボックス: {case['bbox']}")

        # 画像をコピー
        test_img = test_image.copy()

        # テキストを描画
        try:
            result_img = renderer.render_text(
                test_img,
                case['text'],
                case['position'],
                case['bbox'],
                font_size=None,
                auto_fit=True
            )

            # 結果を保存
            output_path = f'test/debug/test_{i+1}_{case["name"].replace(" ", "_")}.png'
            cv2.imwrite(output_path, result_img)
            print(f"✅ 成功: {output_path}")

        except Exception as e:
            print(f"❌ エラー: {e}")

    # 総合テスト（全てのテキストを一度に描画）
    print(f"\n--- 総合テスト ---")
    combined_image = test_image.copy()

    try:
        for case in test_cases:
            combined_image = renderer.render_text(
                combined_image,
                case['text'],
                case['position'],
                case['bbox'],
                auto_fit=True
            )

        cv2.imwrite('test/debug/combined_test.png', combined_image)
        print("✅ 総合テスト成功: test/debug/combined_test.png")

    except Exception as e:
        print(f"❌ 総合テストエラー: {e}")

def test_outline_rendering():
    """縁取りテキストのテスト"""
    print(f"\n=== 縁取りテキストテスト ===")

    # 縁取り専用テスト
    test_image = np.ones((300, 500, 3), dtype=np.uint8) * 100  # 暗い背景

    font_path = os.path.join(os.path.dirname(__file__), '..', 'fonts', 'NotoSansJP-Regular.ttf')
    if not os.path.exists(font_path):
        print(f"警告: フォントファイルが見つかりません: {font_path}")
        font_path = None
    else:
        print(f"✅ フォントファイルが見つかりました: {font_path}")

    renderer = TextRenderer(font_path=font_path, default_font_size=20)

    # 縁取りのテスト
    bbox = [[50, 50], [450, 50], [450, 150], [50, 150]]

    # 異なる縁取り太さでテスト
    outline_tests = [
        {'text': '縁取り1px', 'width': 1, 'pos': (50, 50)},
        {'text': '縁取り2px', 'width': 2, 'pos': (50, 100)},
        {'text': '縁取り3px', 'width': 3, 'pos': (50, 150)},
    ]

    for test in outline_tests:
        try:
            result = renderer.render_text_with_outline(
                test_image.copy(),
                test['text'],
                test['pos'],
                bbox,
                text_color=(0, 0, 0),      # 黒
                outline_color=(255, 255, 255),  # 白
                outline_width=test['width']
            )

            output_path = f'test/debug/outline_{test["width"]}px.png'
            cv2.imwrite(output_path, result)
            print(f"✅ 縁取り{test['width']}px: {output_path}")

        except Exception as e:
            print(f"❌ 縁取り{test['width']}pxエラー: {e}")

def main():
    """メイン関数"""
    print("テキスト描画デバッグスクリプトを開始します...")

    # 出力ディレクトリの確認
    os.makedirs('test/debug', exist_ok=True)

    # テスト実行
    test_text_rendering()
    test_outline_rendering()

    print(f"\n=== デバッグ完了 ===")
    print("生成されたファイル:")
    for file in os.listdir('test/debug'):
        if file.endswith('.png'):
            print(f"  - test/debug/{file}")

if __name__ == "__main__":
    main()