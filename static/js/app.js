// 画像翻訳アプリケーション - JavaScript

class ImageTranslationApp {
    constructor() {
        this.socket = null;
        this.currentSessionId = null;
        this.isProcessing = false;

        this.initializeSocket();
        this.bindEvents();
    }

    initializeSocket() {
        // Socket.IOの初期化
        this.socket = io();

        // 接続イベント
        this.socket.on('connect', () => {
            this.addLog('サーバーに接続しました', 'success');
        });

        // 切断イベント
        this.socket.on('disconnect', () => {
            this.addLog('サーバーから切断しました', 'warning');
        });

        // 進捗イベント
        this.socket.on('progress', (data) => {
            this.updateProgress(data);
        });

        // エラーイベント
        this.socket.on('error', (data) => {
            this.addLog(`エラー: ${data.message}`, 'error');
            this.stopProcessing();
        });

        // 処理完了イベント
        this.socket.on('processing_complete', (data) => {
            this.addLog(data.message, 'success');
            this.showResults(data);
            this.stopProcessing();
        });
    }

    bindEvents() {
        // フォーム送信イベント
        document.getElementById('settingsForm').addEventListener('submit', (e) => {
            e.preventDefault();
            this.startProcessing();
        });

        // キャンセルボタン
        document.getElementById('cancelBtn').addEventListener('click', () => {
            this.cancelProcessing();
        });

        // ログクリアボタン
        document.getElementById('clearLogBtn').addEventListener('click', () => {
            this.clearLog();
        });

        // ファイル選択イベント
        document.getElementById('fileInput').addEventListener('change', (e) => {
            this.updateFileCount();
        });
    }

    updateFileCount() {
        const fileInput = document.getElementById('fileInput');
        const fileCount = fileInput.files.length;

        if (fileCount > 0) {
            this.addLog(`${fileCount}個のファイルを選択しました`, 'success');
        }
    }

    async startProcessing() {
        if (this.isProcessing) {
            this.addLog('既に処理中です', 'warning');
            return;
        }

        const fileInput = document.getElementById('fileInput');
        const files = fileInput.files;

        if (files.length === 0) {
            this.addLog('ファイルを選択してください', 'warning');
            return;
        }

        // フォームデータの取得
        const formData = new FormData();
        for (let i = 0; i < files.length; i++) {
            formData.append('files', files[i]);
        }

        // 設定値の追加
        formData.append('ocr_languages', document.getElementById('ocrLanguages').value);
        formData.append('target_language', document.getElementById('targetLanguage').value);
        formData.append('use_gpu', document.getElementById('useGpu').checked);

        try {
            this.isProcessing = true;
            this.showProgressPanel();
            this.disableForm(true);

            this.addLog('ファイルをアップロード中...', 'info');

            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            if (response.ok) {
                this.currentSessionId = result.session_id;
                this.addLog(`${result.file_count}個のファイルをアップロードしました`, 'success');
            } else {
                throw new Error(result.error || 'アップロードに失敗しました');
            }

        } catch (error) {
            this.addLog(`アップロードエラー: ${error.message}`, 'error');
            this.stopProcessing();
        }
    }

    cancelProcessing() {
        if (this.currentSessionId) {
            // セッションをクリア（サーバー側で処理を停止）
            this.currentSessionId = null;
        }
        this.stopProcessing();
        this.addLog('処理を中止しました', 'warning');
    }

    stopProcessing() {
        this.isProcessing = false;
        this.disableForm(false);
        document.getElementById('cancelBtn').disabled = true;
    }

    showProgressPanel() {
        const progressPanel = document.getElementById('progressPanel');
        const progressBar = document.getElementById('progressBar');
        const progressStatus = document.getElementById('progressStatus');
        const progressText = document.getElementById('progressText');

        progressPanel.style.display = 'block';
        progressBar.style.width = '0%';
        progressBar.setAttribute('aria-valuenow', 0);
        progressStatus.textContent = '準備中...';
        progressText.textContent = '0/0';

        document.getElementById('cancelBtn').disabled = false;
    }

    updateProgress(data) {
        const progressBar = document.getElementById('progressBar');
        const progressStatus = document.getElementById('progressStatus');
        const progressText = document.getElementById('progressText');

        // 進捗バーの更新
        if (data.progress !== undefined) {
            progressBar.style.width = `${data.progress}%`;
            progressBar.setAttribute('aria-valuenow', data.progress);
        }

        // ステータスメッセージの更新
        if (data.message) {
            progressStatus.textContent = data.message;
            this.addLog(data.message, 'info');
        }

        // 進捗テキストの更新
        if (data.current_file !== undefined && data.total_files !== undefined) {
            progressText.textContent = `${data.current_file}/${data.total_files}`;
        }

        // 完了した場合
        if (data.completed) {
            progressStatus.textContent = '処理完了';
            progressBar.classList.add('bg-success');
        }
    }

    async showResults(data) {
        const resultsPanel = document.getElementById('resultsPanel');
        const resultsContainer = document.getElementById('resultsContainer');

        try {
            // 結果ファイルの一覧を取得
            const response = await fetch(`/output/${data.session_id}`);
            const result = await response.json();

            if (response.ok) {
                resultsContainer.innerHTML = '';

                if (result.files.length === 0) {
                    resultsContainer.innerHTML = '<p class="text-muted">結果ファイルがありません</p>';
                } else {
                    result.files.forEach(file => {
                        const resultItem = this.createResultItem(file);
                        resultsContainer.appendChild(resultItem);
                    });
                }

                resultsPanel.style.display = 'block';
                this.addLog(`${result.files.length}個の結果ファイルを生成しました`, 'success');
            } else {
                throw new Error(result.error || '結果の取得に失敗しました');
            }

        } catch (error) {
            this.addLog(`結果取得エラー: ${error.message}`, 'error');
        }
    }

    createResultItem(file) {
        const div = document.createElement('div');
        div.className = 'result-item';

        const filename = file.name.replace('_translated', ' (翻訳済み)');

        div.innerHTML = `
            <img src="${file.url}" alt="${filename}" class="result-image" loading="lazy">
            <div class="result-info">
                <div class="result-filename">${filename}</div>
                <div class="result-actions">
                    <a href="${file.url}" download="${file.name}" class="btn-download">
                        <i class="fas fa-download"></i> ダウンロード
                    </a>
                </div>
            </div>
        `;

        return div;
    }

    disableForm(disabled) {
        const form = document.getElementById('settingsForm');
        const inputs = form.querySelectorAll('input, select, button');

        inputs.forEach(input => {
            if (input.type !== 'submit' && input.id !== 'cancelBtn' && input.id !== 'clearLogBtn') {
                input.disabled = disabled;
            }
        });

        const startBtn = document.getElementById('startBtn');
        if (disabled) {
            startBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 処理中...';
            startBtn.disabled = true;
        } else {
            startBtn.innerHTML = '<i class="fas fa-play"></i> 翻訳開始';
            startBtn.disabled = false;
        }
    }

    addLog(message, type = 'info') {
        const logContainer = document.getElementById('logContainer');
        const logItem = document.createElement('div');
        logItem.className = 'log-item';

        const now = new Date();
        const timeStr = now.toLocaleTimeString('ja-JP');

        logItem.innerHTML = `
            <span class="log-time">${timeStr}</span>
            <span class="log-message ${type}">${this.escapeHtml(message)}</span>
        `;

        logContainer.appendChild(logItem);
        logContainer.scrollTop = logContainer.scrollHeight;

        // ログアイテムの数を制限
        const maxLogItems = 100;
        while (logContainer.children.length > maxLogItems) {
            logContainer.removeChild(logContainer.firstChild);
        }
    }

    clearLog() {
        const logContainer = document.getElementById('logContainer');
        logContainer.innerHTML = `
            <div class="log-item">
                <span class="log-time">${new Date().toLocaleTimeString('ja-JP')}</span>
                <span class="log-message">ログをクリアしました</span>
            </div>
        `;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// アプリケーションの初期化
document.addEventListener('DOMContentLoaded', () => {
    window.app = new ImageTranslationApp();
});

// ページアンロード時のクリーンアップ
window.addEventListener('beforeunload', () => {
    if (window.app && window.app.isProcessing) {
        return '処理中です。本当に終了しますか？';
    }
});