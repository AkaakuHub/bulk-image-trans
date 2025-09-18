"""
翻訳モジュール - Google Gemini APIを使用したテキスト翻訳機能
"""
import google.generativeai as genai
import os
import logging
import json
from typing import List, Optional, Dict, Any
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
            # プロンプトの作成（より明確な指示）
            if source_language:
                # prompt = f"Translate the following {source_language} text to {target_language}. Return ONLY the translated text, nothing else. If the text is already in {target_language}, translate it again: \"{text}\""
                prompt = f"あなたは、{source_language}から{target_language}への翻訳者です。以下のテキストを必ず{target_language}に翻訳してください。翻訳結果のみを返してください。他の情報は一切含めないでください。もしテキストが既に{target_language}で書かれている場合でも、再度翻訳してください: \"{text}\""
            else:
                # prompt = f"Translate the following text to {target_language}. Return ONLY the translated text, nothing else. If the text is already in {target_language}, translate it again: \"{text}\""
                prompt = f"あなたは、任意の言語から{target_language}への翻訳者です。以下のテキストを必ず{target_language}に翻訳してください。翻訳結果のみを返してください。他の情報は一切含めないでください。もしテキストが既に{target_language}で書かれている場合でも、再度翻訳してください: \"{text}\""

            # 翻訳実行
            response = self.model.generate_content(prompt)
            translated_text = response.text.strip()

            # デバッグログ
            self.logger.info(f"翻訳結果: '{text}' -> '{translated_text}'")

            return translated_text

        except Exception as e:
            self.logger.error(f"翻訳エラー ({text}): {e}")
            return text  # エラー時は原文を返す

  
    def bulk_translate_json(self, texts: List[str], target_language: str = "Japanese",
                          source_language: str = None, contexts: List[str] = None) -> Dict[str, Any]:
        """
        バルク翻訳 - 1回のAPIコールで複数テキストを翻訳

        Args:
            texts: 翻訳するテキストのリスト
            target_language: 目的言語
            source_language: ソース言語（オプション）
            contexts: 各テキストのコンテキスト情報（オプション）

        Returns:
            翻訳結果のJSON形式データ
        """
        if not texts:
            return {
                "request_type": "bulk_translation_response",
                "translations": [],
                "error": "No texts provided"
            }

        try:
            # リクエストJSONの構築
            request_data = {
                "request_type": "bulk_translation",
                "target_language": target_language,
                "source_language": source_language,
                "texts": []
            }

            for i, text in enumerate(texts):
                text_item = {
                    "id": i + 1,
                    "text": text
                }
                if contexts and i < len(contexts):
                    text_item["context"] = contexts[i]
                request_data["texts"].append(text_item)

            # プロンプトの作成（JSON形式でバルク翻訳を要求）
            prompt = f"""あなたはプロの翻訳者です。以下のJSONデータに含まれるすべてのテキストを{target_language}に翻訳してください。
コンテキスト情報を考慮して、一貫性のある翻訳を心がけてください。各テキストの文脈やニュアンスを保持しつつ、自然な{target_language}表現に翻訳してください。

以下のJSON形式で応答してください:
```json
{{
  "request_type": "bulk_translation_response",
  "translations": [
    {{
      "id": 1,
      "original_text": "元のテキスト",
      "translated_text": "翻訳されたテキスト",
      "confidence": 0.95
    }}
  ]
}}
```

翻訳対象データ:
```json
{json.dumps(request_data, ensure_ascii=False)}
```

重要: 上記のJSON形式のみで応答してください。他の説明やテキストは含めないでください。"""

            # バルク翻訳の実行
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()

            # JSONレスポンスのパース
            try:
                # コードブロックを除去
                if response_text.startswith("```json"):
                    response_text = response_text[7:]
                if response_text.endswith("```"):
                    response_text = response_text[:-3]

                result_data = json.loads(response_text.strip())

                # レスポンス形式の検証
                if result_data.get("request_type") == "bulk_translation_response":
                    self.logger.info(f"バルク翻訳成功: {len(result_data.get('translations', []))}件")
                    return result_data
                else:
                    self.logger.error(f"予期しないレスポンス形式: {result_data}")
                    return {
                        "request_type": "bulk_translation_response",
                        "translations": [],
                        "error": "Response format error"
                    }

            except json.JSONDecodeError as e:
                self.logger.error(f"JSONパースエラー: {e}")
                self.logger.error(f"レスポンステキスト: {response_text}")
                return {
                    "request_type": "bulk_translation_response",
                    "translations": [],
                    "error": "JSON parse error"
                }

        except Exception as e:
            self.logger.error(f"バルク翻訳エラー: {e}")
            return {
                "request_type": "bulk_translation_response",
                "translations": [],
                "error": str(e)
            }

  
    def bulk_translate_simple(self, texts: List[str], target_language: str = "Japanese") -> List[str]:
        """
        シンプルなバルク翻訳 - テキストリストを受け取り翻訳リストを返す

        Args:
            texts: 翻訳するテキストのリスト
            target_language: 目的言語

        Returns:
            翻訳されたテキストのリスト
        """
        result = self.bulk_translate_json(texts, target_language)

        if result.get("translations"):
            # ID順に翻訳結果をソートして返す
            sorted_translations = sorted(result["translations"], key=lambda x: x["id"])
            return [t["translated_text"] for t in sorted_translations]
        else:
            # エラー時は原文を返す
            return texts


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