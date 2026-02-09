/**
 * リーガルレビュー - フロントエンドアプリケーション
 * Legal Review System - Frontend Application
 */

// --- State ---
let selectedReviewType = 'contract_review';
let isReviewing = false;
let currentResultText = '';

// --- Review type descriptions ---
const reviewDescriptions = {
    contract_review: '契約書の条項を詳細に分析し、リスクや問題点を指摘します',
    compliance_check: '法令・規制への準拠状況を確認します',
    risk_analysis: '法的リスクを評価し、対策を提案します',
    nda_review: '秘密保持契約の妥当性を評価します',
    terms_review: 'サービス利用規約の適法性を確認します',
    general_legal: '法務に関する一般的な質問にお答えします',
};

// --- DOM Elements ---
const documentInput = document.getElementById('documentInput');
const contextInput = document.getElementById('contextInput');
const charCount = document.getElementById('charCount');
const submitBtn = document.getElementById('submitBtn');
const copyBtn = document.getElementById('copyBtn');
const downloadBtn = document.getElementById('downloadBtn');
const placeholder = document.getElementById('placeholder');
const loading = document.getElementById('loading');
const resultContent = document.getElementById('resultContent');
const errorState = document.getElementById('errorState');
const errorMessage = document.getElementById('errorMessage');
const typeDescription = document.getElementById('typeDescription');

// --- Initialize ---
document.addEventListener('DOMContentLoaded', () => {
    // Character count
    documentInput.addEventListener('input', updateCharCount);

    // Review type buttons
    document.querySelectorAll('.review-type-btn').forEach(btn => {
        btn.addEventListener('click', () => selectReviewType(btn));
    });

    // Keyboard shortcut: Ctrl/Cmd + Enter to submit
    document.addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
            e.preventDefault();
            if (!isReviewing) submitReview();
        }
    });
});

// --- Functions ---

function updateCharCount() {
    const count = documentInput.value.length;
    charCount.textContent = `${count.toLocaleString()} 文字`;
}

function selectReviewType(btn) {
    // Update active state
    document.querySelectorAll('.review-type-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');

    selectedReviewType = btn.dataset.type;
    typeDescription.textContent = reviewDescriptions[selectedReviewType] || '';
}

function showState(state) {
    // Hide all states
    placeholder.style.display = 'none';
    loading.style.display = 'none';
    resultContent.style.display = 'none';
    errorState.style.display = 'none';

    // Show requested state
    switch (state) {
        case 'placeholder':
            placeholder.style.display = 'flex';
            break;
        case 'loading':
            loading.style.display = 'flex';
            break;
        case 'result':
            resultContent.style.display = 'block';
            break;
        case 'error':
            errorState.style.display = 'flex';
            break;
    }
}

function setButtonLoading(isLoading) {
    isReviewing = isLoading;
    submitBtn.disabled = isLoading;
    if (isLoading) {
        submitBtn.classList.add('loading');
        submitBtn.querySelector('.btn-text').textContent = 'レビュー中...';
    } else {
        submitBtn.classList.remove('loading');
        submitBtn.querySelector('.btn-text').textContent = 'レビューを開始';
    }
}

async function submitReview() {
    const document_text = documentInput.value.trim();

    if (!document_text) {
        showToast('レビュー対象の文書を入力してください');
        documentInput.focus();
        return;
    }

    if (isReviewing) return;

    // Start review
    setButtonLoading(true);
    showState('loading');
    currentResultText = '';
    copyBtn.disabled = true;
    downloadBtn.disabled = true;

    try {
        const response = await fetch('/api/review', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                document: document_text,
                review_type: selectedReviewType,
                context: contextInput.value.trim(),
            }),
        });

        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.error || 'サーバーエラーが発生しました');
        }

        // Switch to result state with streaming
        showState('result');
        resultContent.innerHTML = '<span class="streaming-cursor"></span>';

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6));
                        handleStreamEvent(data);
                    } catch (e) {
                        // Ignore parse errors for incomplete chunks
                    }
                }
            }
        }

        // Process remaining buffer
        if (buffer.startsWith('data: ')) {
            try {
                const data = JSON.parse(buffer.slice(6));
                handleStreamEvent(data);
            } catch (e) {}
        }

    } catch (error) {
        showState('error');
        errorMessage.textContent = error.message;
    } finally {
        setButtonLoading(false);
    }
}

function handleStreamEvent(data) {
    switch (data.type) {
        case 'content':
            currentResultText += data.text;
            renderMarkdown(currentResultText, true);
            break;
        case 'done':
            renderMarkdown(currentResultText, false);
            copyBtn.disabled = false;
            downloadBtn.disabled = false;
            break;
        case 'error':
            showState('error');
            errorMessage.textContent = data.message;
            break;
    }
}

function renderMarkdown(text, isStreaming) {
    try {
        let html = marked.parse(text);
        if (isStreaming) {
            html += '<span class="streaming-cursor"></span>';
        }
        resultContent.innerHTML = html;
        // Auto-scroll to bottom during streaming
        resultContent.scrollTop = resultContent.scrollHeight;
    } catch (e) {
        resultContent.textContent = text;
    }
}

function clearAll() {
    documentInput.value = '';
    contextInput.value = '';
    currentResultText = '';
    updateCharCount();
    showState('placeholder');
    copyBtn.disabled = true;
    downloadBtn.disabled = true;
    documentInput.focus();
}

async function copyResult() {
    if (!currentResultText) return;
    try {
        await navigator.clipboard.writeText(currentResultText);
        showToast('レビュー結果をコピーしました');
    } catch (e) {
        // Fallback
        const textarea = document.createElement('textarea');
        textarea.value = currentResultText;
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
        showToast('レビュー結果をコピーしました');
    }
}

function downloadResult() {
    if (!currentResultText) return;

    const now = new Date();
    const dateStr = now.toISOString().slice(0, 10);
    const timeStr = now.toTimeString().slice(0, 5).replace(':', '');
    const typeName = reviewDescriptions[selectedReviewType] ? selectedReviewType : 'review';
    const filename = `legal_review_${typeName}_${dateStr}_${timeStr}.md`;

    const blob = new Blob([currentResultText], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    showToast('レビュー結果を保存しました');
}

function showToast(message) {
    // Remove existing toast
    const existing = document.querySelector('.toast');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => {
        if (toast.parentNode) toast.remove();
    }, 3000);
}
