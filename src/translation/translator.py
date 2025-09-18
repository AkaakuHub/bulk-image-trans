"""
翻訳モジュール - Google Gemini APIを使用したテキスト翻訳機能
"""
import google.generativeai as genai
import time
import os
import logging
from typing import List, Optional
from dotenv import load_dotenv

class GeminiTranslator:
    """Google Gemini APIを使用した翻訳クラス"""

    def __init__(self, api_key: str = None, model_name: str = 'gemini-2.0-flash'):
        """
        初期化

        Args:
            api_key: Gemini APIキー（Noneの場合は環境変数から取得）
            model_name: 使用するモデル名
        """
        self.model_name = model_name
        self.model = None
        self.logger = logging.getLogger(__name__)

        # 環境変数の読み込み
        load_dotenv()

        # APIキーの設定
        if api_key:
            self.api_key = api_key
        else:
            self.api_key = os.getenv('GOOGLE_API_KEY')

        if not self.api_key:
            raise ValueError("Gemini APIキーが設定されていません。環境変数GOOGLE_API_KEYを設定してください。")

        self._initialize_model()

        # レート制限設定
        self.requests_per_minute_limit = 15  # Gemini 1.5 Flashの無料枠制限
        self.delay_between_requests = 60 / self.requests_per_minute_limit + 1  # 余裕を持たせる

    def _initialize_model(self):
        """Geminiモデルの初期化"""
        try:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(self.model_name)
            self.logger.info(f"Geminiモデル '{self.model_name}' を初期化しました")
        except Exception as e:
            self.logger.error(f"Geminiモデルの初期化に失敗: {e}")
            raise

    def translate_text(self, text: str, target_language: str = "Japanese", source_language: str = None) -> str:
        """
        単一のテキストを翻訳

        Args:
            text: 翻訳するテキスト
            target_language: 目的言語（デフォルト: 日本語）
            source_language: ソース言語（Noneの場合は自動検出）

        Returns:
            翻訳されたテキスト
        """
        if not text.strip():
            return ""

        try:
            # プロンプトの作成
            if source_language:
                prompt = f"Translate the following {source_language} text to {target_language}. Do not add any extra explanation or context, just return the translated text: \"{text}\""
            else:
                prompt = f"Translate the following text to {target_language}. Do not add any extra explanation or context, just return the translated text: \"{text}\""

            # 翻訳実行
            response = self.model.generate_content(prompt)
            translated_text = response.text.strip()

            self.logger.debug(f"原文: {text} -> 翻訳: {translated_text}")
            return translated_text

        except Exception as e:
            self.logger.error(f"翻訳エラー ({text}): {e}")
            return text  # エラー時は原文を返す

    def translate_texts(self, texts: List[str], target_language: str = "Japanese", source_language: str = None) -> List[str]:
        """
        テキストのリストを翻訳（レート制限を考慮）

        Args:
            texts: 翻訳するテキストのリスト
            target_language: 目的言語
            source_language: ソース言語

        Returns:
            翻訳されたテキストのリスト
        """
        translations = []

        for i, text in enumerate(texts):
            if not text.strip():
                translations.append("")
                continue

            try:
                # 翻訳実行
                translated_text = self.translate_text(text, target_language, source_language)
                translations.append(translated_text)

                # レート制限を回避するための待機
                if i < len(texts) - 1:  # 最後の要素では待機しない
                    time.sleep(self.delay_between_requests)

            except Exception as e:
                self.logger.error(f"バッチ翻訳エラー (要素 {i}): {e}")
                translations.append(text)  # エラー時は原文を返す

        return translations

    def translate_with_retry(self, text: str, target_language: str = "Japanese", max_retries: int = 3) -> str:
        """
        リトライ機能付き翻訳

        Args:
            text: 翻訳するテキスト
            target_language: 目的言語
            max_retries: 最大リトライ回数

        Returns:
            翻訳されたテキスト
        """
        for attempt in range(max_retries):
            try:
                return self.translate_text(text, target_language)
            except Exception as e:
                self.logger.warning(f"翻訳失敗 (試行 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    # 指数バックオフ
                    wait_time = (2 ** attempt) * self.delay_between_requests
                    self.logger.info(f"{wait_time:.1f}秒後に再試行します...")
                    time.sleep(wait_time)
                else:
                    self.logger.error(f"最大リトライ回数に達しました: {text}")
                    return text  # 最終的に原文を返す

    def batch_translate_with_progress(self, texts: List[str], target_language: str = "Japanese",
                                   progress_callback=None) -> List[str]:
        """
        進捗コールバック機能付きバッチ翻訳

        Args:
            texts: 翻訳するテキストのリスト
            target_language: 目的言語
            progress_callback: 進捗報告用コールバック関数 (current, total)

        Returns:
            翻訳されたテキストのリスト
        """
        total = len(texts)
        translations = []

        for i, text in enumerate(texts):
            if progress_callback:
                progress_callback(i + 1, total)

            if not text.strip():
                translations.append("")
                continue

            try:
                translated_text = self.translate_with_retry(text, target_language)
                translations.append(translated_text)

                # レート制限対応
                if i < total - 1:
                    time.sleep(self.delay_between_requests)

            except Exception as e:
                self.logger.error(f"バッチ翻訳エラー (要素 {i}): {e}")
                translations.append(text)

        return translations


def create_translator(api_key: str = None) -> GeminiTranslator:
    """
    翻訳クラスのファクトリ関数

    Args:
        api_key: APIキー

    Returns:
        GeminiTranslatorインスタンス
    """
    return GeminiTranslator(api_key)


if __name__ == "__main__":
    # テスト用コード
    logging.basicConfig(level=logging.INFO)

    try:
        translator = create_translator()

        # 単一テキスト翻訳テスト
        test_text = "Hello, how are you today?"
        result = translator.translate_text(test_text)
        print(f"原文: {test_text}")
        print(f"翻訳: {result}")
        print()

        # バッチ翻訳テスト
        test_texts = [
            "Good morning!",
            "Thank you very much.",
            "Where is the nearest restaurant?",
            "I need help with this translation."
        ]

        def progress_callback(current, total):
            print(f"進捗: {current}/{total}")

        results = translator.batch_translate_with_progress(test_texts, progress_callback=progress_callback)

        print("\nバッチ翻訳結果:")
        for original, translated in zip(test_texts, results):
            print(f"原文: {original}")
            print(f"翻訳: {translated}")
            print()

    except Exception as e:
        print(f"エラー: {e}")
        print("APIキーが設定されているか確認してください。")