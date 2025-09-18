"""
ファイル管理・クリーンアップモジュール
"""
import os
import json
import shutil
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging

class FileManager:
    """ファイル管理・クリーンアップクラス"""

    def __init__(self, base_dir: str = ".", max_age_hours: int = 24):
        """
        初期化

        Args:
            base_dir: ベースディレクトリ
            max_age_hours: ファイルの最大保持時間（時間）
        """
        self.base_dir = base_dir
        self.max_age_hours = max_age_hours
        self.uploads_dir = os.path.join(base_dir, 'uploads')
        self.output_dir = os.path.join(base_dir, 'output')
        self.metadata_file = os.path.join(base_dir, 'file_metadata.json')
        self.logger = logging.getLogger(__name__)

        # メタデータファイルの読み込み
        self.metadata = self._load_metadata()

    def _load_metadata(self) -> Dict:
        """メタデータファイルを読み込む"""
        if os.path.exists(self.metadata_file):
            try:
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.error(f"メタデータ読み込みエラー: {e}")
                return {}
        return {}

    def _save_metadata(self):
        """メタデータを保存する"""
        try:
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(self.metadata, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"メタデータ保存エラー: {e}")

    def register_session(self, session_id: str, files: List[Dict], settings: Dict) -> Dict:
        """
        セッションを登録する

        Args:
            session_id: セッションID
            files: ファイル情報のリスト
            settings: 処理設定

        Returns:
            登録されたセッション情報
        """
        session_data = {
            'session_id': session_id,
            'created_at': datetime.now().isoformat(),
            'files': files,
            'settings': settings,
            'status': 'processing',
            'completed_files': [],
            'output_files': []
        }

        self.metadata[session_id] = session_data
        self._save_metadata()
        self.logger.info(f"セッション登録: {session_id}")

        return session_data

    def update_session_status(self, session_id: str, status: str):
        """
        セッションのステータスを更新

        Args:
            session_id: セッションID
            status: 新しいステータス
        """
        if session_id in self.metadata:
            self.metadata[session_id]['status'] = status
            self.metadata[session_id]['updated_at'] = datetime.now().isoformat()
            self._save_metadata()

    def add_completed_file(self, session_id: str, original_name: str, output_path: str):
        """
        完了したファイルを追加

        Args:
            session_id: セッションID
            original_name: オリジナルファイル名
            output_path: 出力ファイルパス
        """
        if session_id in self.metadata:
            completed_file = {
                'original_name': original_name,
                'output_path': output_path,
                'completed_at': datetime.now().isoformat(),
                'download_url': f"/output/{session_id}/{os.path.basename(output_path)}"
            }

            self.metadata[session_id]['completed_files'].append(completed_file)
            self.metadata[session_id]['updated_at'] = datetime.now().isoformat()
            self._save_metadata()

            self.logger.info(f"完了ファイル追加: {session_id} - {original_name}")

    def get_session_info(self, session_id: str) -> Optional[Dict]:
        """
        セッション情報を取得

        Args:
            session_id: セッションID

        Returns:
            セッション情報、存在しない場合はNone
        """
        return self.metadata.get(session_id)

    def get_all_sessions(self) -> List[Dict]:
        """
        全てのセッション情報を取得

        Returns:
            セッション情報のリスト
        """
        sessions = []
        for session_id, session_data in self.metadata.items():
            session_info = session_data.copy()
            session_info['session_id'] = session_id
            sessions.append(session_info)
        return sessions

    def cleanup_old_files(self, dry_run: bool = False) -> Dict:
        """
        古いファイルをクリーンアップする

        Args:
            dry_run: ドライラン（実際には削除しない）

        Returns:
            クリーンアップ結果
        """
        cutoff_time = datetime.now() - timedelta(hours=self.max_age_hours)
        result = {
            'deleted_sessions': [],
            'deleted_files': [],
            'freed_space': 0,
            'errors': []
        }

        self.logger.info(f"クリーンアップ開始: {cutoff_time.isoformat()} より古いファイル")

        # 古いセッションを特定
        sessions_to_delete = []
        for session_id, session_data in self.metadata.items():
            created_at = datetime.fromisoformat(session_data['created_at'])
            if created_at < cutoff_time:
                sessions_to_delete.append(session_id)

        # セッションと関連ファイルを削除
        for session_id in sessions_to_delete:
            try:
                session_data = self.metadata[session_id]

                # アップロードディレクトリを削除
                upload_session_dir = os.path.join(self.uploads_dir, session_id)
                if os.path.exists(upload_session_dir):
                    if not dry_run:
                        shutil.rmtree(upload_session_dir)
                        size = self._get_dir_size(upload_session_dir)
                        result['freed_space'] += size
                        self.logger.info(f"アップロードディレクトリ削除: {upload_session_dir} ({size} bytes)")
                    else:
                        self.logger.info(f"[ドライラン] アップロードディレクトリ削除予定: {upload_session_dir}")

                # 出力ディレクトリを削除
                output_session_dir = os.path.join(self.output_dir, session_id)
                if os.path.exists(output_session_dir):
                    if not dry_run:
                        shutil.rmtree(output_session_dir)
                        size = self._get_dir_size(output_session_dir)
                        result['freed_space'] += size
                        self.logger.info(f"出力ディレクトリ削除: {output_session_dir} ({size} bytes)")
                    else:
                        self.logger.info(f"[ドライラン] 出力ディレクトリ削除予定: {output_session_dir}")

                result['deleted_sessions'].append(session_id)
                if not dry_run:
                    del self.metadata[session_id]

            except Exception as e:
                error_msg = f"セッション {session_id} のクリーンアップ中にエラー: {e}"
                result['errors'].append(error_msg)
                self.logger.error(error_msg)

        # メタデータを保存
        if not dry_run and result['deleted_sessions']:
            self._save_metadata()

        # 孤立したディレクトリをクリーンアップ
        self._cleanup_orphaned_directories(result, dry_run)

        result['freed_space_mb'] = result['freed_space'] / (1024 * 1024)
        self.logger.info(f"クリーンアップ完了: {len(result['deleted_sessions'])} セッション削除, {result['freed_space_mb']:.2f} MB 解放")

        return result

    def _cleanup_orphaned_directories(self, result: Dict, dry_run: bool):
        """孤立したディレクトリをクリーンアップ"""
        cutoff_time = datetime.now() - timedelta(hours=self.max_age_hours)

        # uploadsディレクトリのクリーンアップ
        if os.path.exists(self.uploads_dir):
            for dirname in os.listdir(self.uploads_dir):
                dirpath = os.path.join(self.uploads_dir, dirname)
                if os.path.isdir(dirpath):
                    if dirname not in self.metadata:
                        try:
                            dir_time = datetime.fromtimestamp(os.path.getctime(dirpath))
                            if dir_time < cutoff_time:
                                if not dry_run:
                                    shutil.rmtree(dirpath)
                                    size = self._get_dir_size(dirpath)
                                    result['freed_space'] += size
                                    result['deleted_files'].append(f"uploads/{dirname}")
                                    self.logger.info(f"孤立アップロードディレクトリ削除: {dirpath}")
                                else:
                                    self.logger.info(f"[ドライラン] 孤立アップロードディレクトリ削除予定: {dirpath}")
                        except Exception as e:
                            self.logger.error(f"孤立ディレクトリ処理エラー {dirpath}: {e}")

        # outputディレクトリのクリーンアップ
        if os.path.exists(self.output_dir):
            for dirname in os.listdir(self.output_dir):
                dirpath = os.path.join(self.output_dir, dirname)
                if os.path.isdir(dirpath):
                    if dirname not in self.metadata:
                        try:
                            dir_time = datetime.fromtimestamp(os.path.getctime(dirpath))
                            if dir_time < cutoff_time:
                                if not dry_run:
                                    shutil.rmtree(dirpath)
                                    size = self._get_dir_size(dirpath)
                                    result['freed_space'] += size
                                    result['deleted_files'].append(f"output/{dirname}")
                                    self.logger.info(f"孤立出力ディレクトリ削除: {dirpath}")
                                else:
                                    self.logger.info(f"[ドライラン] 孤立出力ディレクトリ削除予定: {dirpath}")
                        except Exception as e:
                            self.logger.error(f"孤立ディレクトリ処理エラー {dirpath}: {e}")

    def _get_dir_size(self, dirpath: str) -> int:
        """ディレクトリのサイズを取得"""
        total_size = 0
        try:
            for dirpath, _, filenames in os.walk(dirpath):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    if os.path.exists(fp):
                        total_size += os.path.getsize(fp)
        except Exception:
            pass
        return total_size

    def get_storage_stats(self) -> Dict:
        """
        ストレージ統計情報を取得

        Returns:
            ストレージ情報
        """
        stats = {
            'total_sessions': len(self.metadata),
            'uploads_size_mb': self._get_dir_size(self.uploads_dir) / (1024 * 1024),
            'output_size_mb': self._get_dir_size(self.output_dir) / (1024 * 1024),
            'old_sessions_count': 0
        }

        cutoff_time = datetime.now() - timedelta(hours=self.max_age_hours)
        for session_id, session_data in self.metadata.items():
            created_at = datetime.fromisoformat(session_data['created_at'])
            if created_at < cutoff_time:
                stats['old_sessions_count'] += 1

        return stats


def create_file_manager(base_dir: str = ".", max_age_hours: int = 24) -> FileManager:
    """
    ファイルマネージャーのファクトリ関数

    Args:
        base_dir: ベースディレクトリ
        max_age_hours: 最大保持時間

    Returns:
        FileManagerインスタンス
    """
    return FileManager(base_dir, max_age_hours)


if __name__ == "__main__":
    # テスト用コード
    logging.basicConfig(level=logging.INFO)
    fm = create_file_manager(max_age_hours=1)  # 1時間でテスト

    # ストレージ統計表示
    stats = fm.get_storage_stats()
    print("ストレージ統計:")
    for key, value in stats.items():
        print(f"  {key}: {value}")

    # ドライランクリーンアップ
    print("\nドライランクリーンアップ:")
    result = fm.cleanup_old_files(dry_run=True)
    print(f"削除予定セッション: {len(result['deleted_sessions'])}")
    print(f"解放予定容量: {result['freed_space_mb']:.2f} MB")