"""
Flask Webアプリケーション
"""
import os
import sys
import uuid
import logging
import eventlet

# eventletをパッチ - 他のモジュールをインポートする前に実行
eventlet.monkey_patch()

from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_socketio import SocketIO
from flask_cors import CORS
from werkzeug.utils import secure_filename
import threading

# srcディレクトリをパスに追加
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.ocr import TextExtractor
from src.translation import GeminiTranslator
from src.image_processing import TextInpainter
from src.text_rendering import TextRenderer
from src.file_management import FileManager
from dotenv import load_dotenv

def adjust_ocr_languages(languages):
    """
    EasyOCRの制限に合わせて言語組み合わせを調整
    入力: 中国語または英語のみ
    """
    # 中国語が含まれる場合は英語を追加
    if any(lang in ['ch_sim', 'ch_tra'] for lang in languages):
        if 'ch_sim' in languages:
            return ['ch_sim', 'en']
        elif 'ch_tra' in languages:
            return ['ch_tra', 'en']

    # 英語のみの場合
    if 'en' in languages:
        return ['en']

    # その他の場合はそのまま返す
    return languages

# 設定
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB
app.config['OUTPUT_FOLDER'] = 'output'

# 許可されるファイル形式
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'bmp', 'tiff'}

# SocketIOの設定
socketio = SocketIO(app, cors_allowed_origins="*")
CORS(app)

# ロギング設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 環境変数の読み込み
load_dotenv()

# ファイル管理の初期化
file_manager = FileManager(base_dir='.', max_age_hours=24)

# グローバル変数（セッション管理）
processing_sessions = {}

def allowed_file(filename):
    """ファイル拡張子のチェック"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

class ImageTranslationPipeline:
    """画像翻訳パイプライン"""

    def __init__(self, settings):
        self.settings = settings
        self.logger = logging.getLogger(__name__)

        # 各コンポーネントの初期化
        self.text_extractor = TextExtractor(
            languages=settings['ocr_languages'],
            gpu=settings['use_gpu']
        )

        self.translator = GeminiTranslator()

        self.inpainter = TextInpainter(
            method='ns',
            inpaint_radius=3
        )

        self.renderer = TextRenderer(
            font_path='fonts/NotoSansJP-Regular.ttf',
            default_font_size=12
        )

    def process_single_image(self, image_path, output_path, session_id):
        """単一の画像を処理"""
        try:
            self.logger.info(f"処理開始: {os.path.basename(image_path)}")

            # 1. テキスト抽出
            extracted_texts = self.text_extractor.extract_text(image_path)
            if not extracted_texts:
                self.logger.warning(f"テキストが検出されませんでした: {image_path}")
                return False

            # 進捗更新
            socketio.emit('progress', {
                'session_id': session_id,
                'message': f'テキスト検出完了: {len(extracted_texts)}個の領域',
                'progress': 25
            })

            # 2. 翻訳
            original_texts = [item['text'] for item in extracted_texts]
            translated_texts = self.translator.translate_texts(
                original_texts,
                target_language=self.settings['target_language']
            )

            socketio.emit('progress', {
                'session_id': session_id,
                'message': '翻訳完了',
                'progress': 50
            })

            # 3. 元の画像を読み込み
            import cv2
            original_image = cv2.imread(image_path)
            if original_image is None:
                self.logger.error(f"画像の読み込みに失敗: {image_path}")
                return False

            # 4. テキスト除去
            bboxes = [item['bbox'] for item in extracted_texts]
            inpainted_image = self.inpainter.remove_text(original_image, bboxes)

            socketio.emit('progress', {
                'session_id': session_id,
                'message': 'テキスト除去完了',
                'progress': 75
            })

            # 5. 翻訳テキストを描画
            text_data = []
            for i, (extracted, translated) in enumerate(zip(extracted_texts, translated_texts)):
                text_data.append({
                    'text': translated,
                    'bbox': extracted['bbox'],
                    'color': None
                })

            result_image = self.renderer.batch_render_text(inpainted_image, text_data)

            # 6. 結果を保存
            cv2.imwrite(output_path, result_image)
            self.logger.info(f"保存完了: {output_path}")

            socketio.emit('progress', {
                'session_id': session_id,
                'message': '処理完了',
                'progress': 100,
                'completed': True
            })

            return True

        except Exception as e:
            self.logger.error(f"画像処理エラー: {e}")
            socketio.emit('error', {
                'session_id': session_id,
                'message': f'処理エラー: {str(e)}'
            })
            return False

@app.route('/')
def index():
    """メインページ"""
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_files():
    """ファイルアップロード"""
    try:
        if 'files' not in request.files:
            return jsonify({'error': 'ファイルが選択されていません'}), 400

        files = request.files.getlist('files')
        settings = request.form

        # セッションIDの生成
        session_id = str(uuid.uuid4())

        # アップロードフォルダの作成
        upload_folder = os.path.join(app.config['UPLOAD_FOLDER'], session_id)
        os.makedirs(upload_folder, exist_ok=True)

        # 出力フォルダの作成
        output_folder = os.path.join(app.config['OUTPUT_FOLDER'], session_id)
        os.makedirs(output_folder, exist_ok=True)

        # ファイルの保存
        uploaded_files = []
        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file_path = os.path.join(upload_folder, filename)
                file.save(file_path)
                uploaded_files.append({
                    'original_name': filename,
                    'path': file_path
                })

        # 設定の取得（中国語または英語単体のみ）
        raw_language = settings.get('ocr_languages', 'en').split(',')[0].strip()

        # 言語コードをEasyOCR対応に変換
        language_mapping = {
            'chinese': 'ch_sim',
            'zh': 'ch_sim',
            'english': 'en',
            'en': 'en'
        }

        ocr_language = language_mapping.get(raw_language.lower(), raw_language)

        # EasyOCRの制限に合わせて言語組み合わせを調整
        ocr_languages = adjust_ocr_languages([ocr_language])

        pipeline_settings = {
            'ocr_languages': ocr_languages,
            'target_language': settings.get('target_language', 'Japanese'),
            'use_gpu': settings.get('use_gpu', 'true').lower() == 'true'
        }

        # ファイルマネージャーにセッションを登録
        session_data = {
            'session_id': session_id,
            'files': uploaded_files,
            'settings': pipeline_settings,
            'output_folder': output_folder,
            'completed': 0,
            'total': len(uploaded_files)
        }
        file_manager.register_session(session_id, uploaded_files, pipeline_settings)

        # 互換性のためグローバル変数にも保存
        processing_sessions[session_id] = session_data

        # バックグラウンドで処理を開始
        thread = threading.Thread(
            target=process_files_background,
            args=(session_id,)
        )
        thread.daemon = True
        thread.start()

        return jsonify({
            'session_id': session_id,
            'file_count': len(uploaded_files)
        })

    except Exception as e:
        logger.error(f"アップロードエラー: {e}")
        return jsonify({'error': str(e)}), 500

def process_files_background(session_id):
    """バックグラウンドでファイルを処理"""
    try:
        session = processing_sessions.get(session_id)
        if not session:
            return

        pipeline = ImageTranslationPipeline(session['settings'])

        for i, file_info in enumerate(session['files']):
            if session_id not in processing_sessions:
                break  # セッションが削除された場合

            # 進捗更新
            socketio.emit('progress', {
                'session_id': session_id,
                'message': f'処理中 ({i+1}/{session["total"]}): {file_info["original_name"]}',
                'progress': int((i / session["total"]) * 100),
                'current_file': i + 1,
                'total_files': session["total"]
            })

            # 出力パスの生成
            name, ext = os.path.splitext(file_info["original_name"])
            output_path = os.path.join(
                session['output_folder'],
                f"{name}_translated{ext}"
            )

            # 画像処理
            success = pipeline.process_single_image(
                file_info['path'],
                output_path,
                session_id
            )

            if success:
                session['completed'] += 1
                # ファイルマネージャーに完了ファイルを登録
                original_name = file_info["original_name"]
                name, ext = os.path.splitext(original_name)
                output_filename = f"{name}_translated{ext}"
                output_path = os.path.join(session['output_folder'], output_filename)

                if os.path.exists(output_path):
                    file_manager.add_completed_file(session_id, original_name, output_path)

        # セッション情報を更新
        file_manager.update_session_status(session_id, 'completed')

        # セッション情報を取得してダウンロードリンクを作成
        session_info = file_manager.get_session_info(session_id)
        download_links = []
        if session_info and 'completed_files' in session_info:
            download_links = session_info['completed_files']

        # 処理完了（ダウンロードリンク付き）
        logger.info(f"処理完了イベントを送信: session_id={session_id}, download_links={len(download_links)}件")
        logger.info(f"ダウンロードリンク: {download_links}")
        socketio.emit('processing_complete', {
            'session_id': session_id,
            'message': f'処理完了: {session["completed"]}/{session["total"]}ファイル',
            'download_links': download_links,
            'output_folder': f'/output/{session_id}'
        })

    except Exception as e:
        logger.error(f"バックグラウンド処理エラー: {e}")
        socketio.emit('error', {
            'session_id': session_id,
            'message': f'処理エラー: {str(e)}'
        })

@app.route('/output/<session_id>/<filename>')
def download_file(session_id, filename):
    """結果ファイルのダウンロード"""
    try:
        output_folder = os.path.join(app.config['OUTPUT_FOLDER'], session_id)
        return send_from_directory(output_folder, filename)
    except Exception as e:
        logger.error(f"ダウンロードエラー: {e}")
        return jsonify({'error': 'ファイルが見つかりません'}), 404

@app.route('/uploads/<session_id>/<filename>')
def serve_uploaded_file(session_id, filename):
    """アップロードされた元ファイルの表示"""
    try:
        upload_folder = os.path.join(app.config['UPLOAD_FOLDER'], session_id)
        return send_from_directory(upload_folder, filename)
    except Exception as e:
        logger.error(f"元ファイル表示エラー: {e}")
        return jsonify({'error': 'ファイルが見つかりません'}), 404

@app.route('/output/<session_id>')
def list_output_files(session_id):
    """出力ファイルの一覧（メタデータ付き）"""
    try:
        # ファイルマネージャーからセッション情報を取得
        session_info = file_manager.get_session_info(session_id)
        if session_info and 'completed_files' in session_info:
            return jsonify({
                'session_id': session_id,
                'files': session_info['completed_files'],
                'created_at': session_info.get('created_at'),
                'settings': session_info.get('settings', {})
            })
        else:
            return jsonify({'files': []})
    except Exception as e:
        logger.error(f"ファイル一覧エラー: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/session/<session_id>')
def get_session_info(session_id):
    """セッション情報を取得"""
    try:
        session_info = file_manager.get_session_info(session_id)
        if session_info:
            return jsonify(session_info)
        else:
            return jsonify({'error': 'Session not found'}), 404
    except Exception as e:
        logger.error(f"セッション情報取得エラー: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/sessions')
def get_all_sessions():
    """全てのセッション情報を取得"""
    try:
        sessions = file_manager.get_all_sessions()
        return jsonify({'sessions': sessions})
    except Exception as e:
        logger.error(f"セッション一覧取得エラー: {e}")
        return jsonify({'error': str(e)}), 500

@socketio.on('connect')
def handle_connect():
    """SocketIO接続"""
    logger.info('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    """SocketIO切断"""
    logger.info('Client disconnected')

if __name__ == '__main__':
    # 必要なフォルダの作成
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

    # 起動時にクリーンアップを実行
    logger.info("起動時クリーンアップを実行します...")
    cleanup_result = file_manager.cleanup_old_files()
    logger.info(f"クリーンアップ完了: {cleanup_result['deleted_sessions']} セッション削除, {cleanup_result['freed_space_mb']:.2f} MB 解放")

    # サーバーの起動
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)