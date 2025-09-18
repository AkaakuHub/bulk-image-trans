// 画像翻訳アプリケーション - JavaScript

class ImageTranslationApp {
    constructor() {
        this.socket = null;
        this.currentSessionId = null;
        this.isProcessing = false;

        this.initializeSocket();
        this.bindEvents();
        this.initializeModalEvents();
    }

    initializeSocket() {
        console.log('Initializing socket...');

        // Socket.IOの初期化
        this.socket = io();

        // 接続イベント
        this.socket.on('connect', () => {
            console.log('Socket connected');
            this.addLog('サーバーに接続しました', 'success');
        });

        // 切断イベント
        this.socket.on('disconnect', () => {
            console.log('Socket disconnected');
            this.addLog('サーバーから切断しました', 'warning');
        });

        // 接続エラー
        this.socket.on('connect_error', (error) => {
            console.error('Socket connection error:', error);
            this.addLog('サーバー接続エラー', 'error');
        });

        // 進捗イベント
        this.socket.on('progress', (data) => {
            console.log('Progress data:', data);
            this.updateProgress(data);
        });

        // エラーイベント
        this.socket.on('error', (data) => {
            console.error('Socket error:', data);
            this.addLog(`エラー: ${data.message}`, 'error');
            this.stopProcessing();
        });

        // 処理完了イベント
        this.socket.on('processing_complete', (data) => {
            console.log('Processing complete data:', data);
            this.addLog(data.message, 'success');
            this.showResults(data);
            this.stopProcessing();
        });
    }

    bindEvents() {
        console.log('Binding events...');

        // フォーム送信イベント
        const settingsForm = document.getElementById('settingsForm');
        if (settingsForm) {
            settingsForm.addEventListener('submit', (e) => {
                console.log('Form submitted');
                e.preventDefault();
                this.startProcessing();
            });
        } else {
            console.error('Settings form not found');
        }

        // キャンセルボタン
        const cancelBtn = document.getElementById('cancelBtn');
        if (cancelBtn) {
            cancelBtn.addEventListener('click', () => {
                console.log('Cancel button clicked');
                this.cancelProcessing();
            });
        } else {
            console.error('Cancel button not found');
        }

        // ログクリアボタン
        const clearLogBtn = document.getElementById('clearLogBtn');
        if (clearLogBtn) {
            clearLogBtn.addEventListener('click', () => {
                console.log('Clear log button clicked');
                this.clearLog();
            });
        } else {
            console.error('Clear log button not found');
        }

        // ファイル選択イベント
        const fileInput = document.getElementById('fileInput');
        if (fileInput) {
            fileInput.addEventListener('change', (e) => {
                console.log('File input changed');
                this.updateFileCount();
            });
        } else {
            console.error('File input not found');
        }
    }

    updateFileCount() {
        const fileInput = document.getElementById('fileInput');
        const fileCount = fileInput.files.length;

        if (fileCount > 0) {
            this.addLog(`${fileCount}個のファイルを選択しました`, 'success');
        }
    }

    async startProcessing() {
        console.log('startProcessing called');

        if (this.isProcessing) {
            this.addLog('既に処理中です', 'warning');
            return;
        }

        const fileInput = document.getElementById('fileInput');
        const files = fileInput.files;
        console.log('Selected files:', files);

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
        const ocrLang = document.getElementById('ocrLanguages').value;
        const targetLang = document.getElementById('targetLanguage').value;
        const useGpu = document.getElementById('useGpu').checked;

        console.log('Settings:', {ocrLang, targetLang, useGpu});

        formData.append('ocr_languages', ocrLang);
        formData.append('target_language', targetLang);
        formData.append('use_gpu', useGpu);

        try {
            this.isProcessing = true;
            this.showProgressPanel();
            this.disableForm(true);

            this.addLog('ファイルをアップロード中...', 'info');

            console.log('Sending request to /upload...');
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });

            console.log('Response status:', response.status);
            const result = await response.json();
            console.log('Response data:', result);

            if (response.ok) {
                this.currentSessionId = result.session_id;
                this.addLog(`${result.file_count}個のファイルをアップロードしました`, 'success');
                console.log('Session ID set to:', this.currentSessionId);
            } else {
                throw new Error(result.error || 'アップロードに失敗しました');
            }

        } catch (error) {
            console.error('Upload error:', error);
            this.addLog(`アップロードエラー: ${error.message}`, 'error');
            this.stopProcessing();
        }
    }

    cancelProcessing() {
        console.log('Cancel processing called');
        if (this.currentSessionId) {
            console.log('Clearing session:', this.currentSessionId);
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

        // 進捗パネルを非表示にする
        const progressPanel = document.getElementById('progressPanel');
        if (progressPanel) {
            progressPanel.style.display = 'none';
        }
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

    showResults(data) {
        console.log('showResults called with data:', data);

        const resultsPanel = document.getElementById('resultsPanel');
        const resultsContainer = document.getElementById('resultsContainer');

        console.log('Results panel element:', resultsPanel);
        console.log('Results container element:', resultsContainer);
        console.log('Results panel exists:', !!resultsPanel);
        console.log('Results container exists:', !!resultsContainer);

        if (!resultsPanel || !resultsContainer) {
            console.error('Required DOM elements not found!');
            this.addLog('DOM要素が見つかりません', 'error');
            return;
        }

        try {
            // コンテナをクリア
            resultsContainer.innerHTML = '';
            console.log('Cleared results container');

            // download_linksを使用して結果を表示
            if (data.download_links && data.download_links.length > 0) {
                console.log(`Processing ${data.download_links.length} files`);

                data.download_links.forEach((file, index) => {
                    console.log(`Creating result item ${index + 1}:`, file);
                    const resultItem = this.createResultItem(file);
                    console.log(`Created result item ${index + 1}:`, resultItem);
                    resultsContainer.appendChild(resultItem);
                    console.log(`Appended result item ${index + 1}`);
                });

                this.addLog(`${data.download_links.length}個の結果ファイルを生成しました`, 'success');
            } else {
                console.log('No download_links found');
                resultsContainer.innerHTML = '<p class="text-muted">結果ファイルがありません</p>';
                this.addLog('結果ファイルがありません', 'warning');
            }

            // パネルを表示
            resultsPanel.style.display = 'block';
            console.log('Results panel should now be visible');

            // 最終的なDOM状態を確認
            console.log('Final results container HTML:', resultsContainer.innerHTML.substring(0, 200) + '...');
            console.log('Results panel display style:', resultsPanel.style.display);
            console.log('Results container child count:', resultsContainer.children.length);

        } catch (error) {
            console.error('Error in showResults:', error);
            this.addLog(`結果表示エラー: ${error.message}`, 'error');
        }
    }

    createResultItem(file) {
        const div = document.createElement('div');
        div.className = 'result-item';

        // オリジナル画像URLを構築（セッションIDから）
        const sessionId = file.download_url.split('/')[2];
        const originalImageUrl = `/uploads/${sessionId}/${file.original_name}`;
        const translatedImageUrl = file.download_url;
        const translatedFilename = file.original_name.replace(/\.[^/.]+$/, '') + ' (翻訳済み)' + file.original_name.match(/\.[^/.]+$/)[0];

        div.innerHTML = `
            <div class="comparison-container">
                <div class="image-pair">
                    <div class="original-image">
                        <div class="image-label">元の画像</div>
                        <img src="${originalImageUrl}" alt="${file.original_name}" class="result-image" loading="lazy"
                             onerror="this.src='data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' width=\'200\' height=\'150\'%3E%3Crect width=\'200\' height=\'150\' fill=\'%23f8f9fa\'/%3E%3Ctext x=\'50%25\' y=\'50%25\' text-anchor=\'middle\' dy=\'.3em\' fill=\'%236c757d\'%3E画像が見つかりません%3C/text%3E%3C/svg%3E'"
                             data-caption="元の画像: ${file.original_name}">
                    </div>
                    <div class="translated-image">
                        <div class="image-label">翻訳済み</div>
                        <img src="${translatedImageUrl}" alt="${translatedFilename}" class="result-image" loading="lazy"
                             data-caption="翻訳済み: ${translatedFilename}">
                    </div>
                </div>
                <div class="result-info">
                    <div class="result-filename">${translatedFilename}</div>
                    <div class="result-actions">
                        <a href="${translatedImageUrl}" download="${file.original_name}" class="btn-download">
                            <i class="fas fa-download"></i> ダウンロード
                        </a>
                    </div>
                </div>
            </div>
        `;

        // 画像クリックイベントを追加
        const images = div.querySelectorAll('.result-image');
        images.forEach(img => {
            img.addEventListener('click', () => this.showImageModal(img));
        });

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

    showImageModal(img) {
        const modal = document.getElementById('imageModal');
        const modalImg = document.getElementById('modalImage');
        const modalCaption = document.getElementById('modalCaption');

        // モーダルに画像を設定
        modalImg.src = img.src;
        modalCaption.textContent = img.dataset.caption || img.alt;

        // モーダルを表示
        modal.style.display = 'block';
        document.body.style.overflow = 'hidden'; // 背景スクロールを防止

        // モーダル外クリックで閉じる処理
        const closeOnOutsideClick = (e) => {
            if (e.target === modal) {
                this.hideImageModal();
                modal.removeEventListener('click', closeOnOutsideClick);
            }
        };
        modal.addEventListener('click', closeOnOutsideClick);
    }

    hideImageModal() {
        const modal = document.getElementById('imageModal');
        modal.style.display = 'none';
        document.body.style.overflow = 'auto'; // 背景スクロールを再開
    }

    // モーダル関連のイベントリスナーを初期化メソッドに追加
    initializeModalEvents() {
        const modal = document.getElementById('imageModal');
        const closeBtn = modal.querySelector('.modal-close');

        // 閉じるボタンのクリックイベント
        closeBtn.addEventListener('click', () => this.hideImageModal());

        // ESCキーでモーダルを閉じる
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && modal.style.display === 'block') {
                this.hideImageModal();
            }
        });
    }
}

// アプリケーションの初期化
document.addEventListener('DOMContentLoaded', () => {
    console.log('DOM loaded, initializing app...');
    try {
        window.app = new ImageTranslationApp();
        console.log('App initialized successfully');
    } catch (error) {
        console.error('Error initializing app:', error);
    }
});

// ページアンロード時のクリーンアップ
window.addEventListener('beforeunload', () => {
    if (window.app && window.app.isProcessing) {
        return '処理中です。本当に終了しますか？';
    }
});