# リーガルレビュー | Legal Review System

Claude API を活用した日本語法務文書レビューシステム

## 機能

- **契約書レビュー** - 契約書の条項を詳細に分析し、リスクや問題点を指摘
- **コンプライアンスチェック** - 法令・規制への準拠状況を確認
- **リスク分析** - 法的リスクを評価し、対策を提案
- **NDAレビュー** - 秘密保持契約の妥当性を評価
- **利用規約レビュー** - サービス利用規約の適法性を確認
- **一般法務相談** - 法務に関する一般的な質問に回答

## セットアップ

### 1. 依存パッケージのインストール

```bash
cd legal_review
pip install -r requirements.txt
```

### 2. API キーの設定

```bash
export ANTHROPIC_API_KEY=your_api_key_here
```

### 3. サーバーの起動

```bash
python app.py
```

ブラウザで http://localhost:5000 にアクセスしてください。

## 環境変数

| 変数名 | 説明 | デフォルト |
|--------|------|-----------|
| `ANTHROPIC_API_KEY` | Anthropic API キー（必須） | - |
| `PORT` | サーバーポート番号 | 5000 |
| `FLASK_DEBUG` | デバッグモード（true/false） | false |

## 技術スタック

- **バックエンド**: Python / Flask
- **フロントエンド**: HTML / CSS / JavaScript
- **AI**: Anthropic Claude API (claude-sonnet-4-20250514)
- **ストリーミング**: Server-Sent Events (SSE)

## 注意事項

本システムの出力は参考情報であり、正式な法的助言ではありません。
重要な法的判断については、必ず弁護士等の専門家にご相談ください。
