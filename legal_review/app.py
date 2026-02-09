"""
リーガルレビュー - Claude API を活用した法務文書レビューシステム
Japanese Legal Review Interface powered by Claude API
"""

import os
import json
from flask import Flask, render_template, request, jsonify, Response, stream_with_context
import anthropic

app = Flask(__name__)

# Claude API client
client = None


def get_client():
    """Get or create Anthropic client."""
    global client
    if client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY 環境変数が設定されていません。\n"
                "export ANTHROPIC_API_KEY=your_api_key_here"
            )
        client = anthropic.Anthropic(api_key=api_key)
    return client


# Review type configurations with Japanese prompts
REVIEW_TYPES = {
    "contract_review": {
        "name": "契約書レビュー",
        "description": "契約書の条項を詳細に分析し、リスクや問題点を指摘します",
        "icon": "📄",
        "system_prompt": (
            "あなたは日本法に精通した優秀な法務専門家です。"
            "契約書のレビューを行い、以下の観点から詳細な分析を提供してください：\n\n"
            "1. **契約概要**: 契約の種類、当事者、主要な取引内容\n"
            "2. **重要条項の分析**: 各重要条項の法的意味と影響\n"
            "3. **リスク評価**: 潜在的なリスクを高・中・低で分類\n"
            "4. **問題点・懸念事項**: 不利な条項、曖昧な表現、欠落している条項\n"
            "5. **修正提案**: 具体的な修正案と理由\n"
            "6. **総合評価**: 契約全体の評価とアドバイス\n\n"
            "回答は必ず日本語で、法務専門家として分かりやすく構造化して提供してください。"
            "Markdown形式で見出しや箇条書きを活用してください。"
        ),
    },
    "compliance_check": {
        "name": "コンプライアンスチェック",
        "description": "法令・規制への準拠状況を確認します",
        "icon": "✅",
        "system_prompt": (
            "あなたは日本のコンプライアンスに精通した法務専門家です。"
            "提供された文書について、以下の観点からコンプライアンスチェックを行ってください：\n\n"
            "1. **関連法令の特定**: 適用される可能性のある法令・規制\n"
            "2. **準拠状況の評価**: 各法令への準拠状況（準拠/一部準拠/非準拠）\n"
            "3. **違反リスク**: 法令違反の可能性がある箇所と具体的なリスク\n"
            "4. **改善提案**: コンプライアンス上の改善点と具体的な対応策\n"
            "5. **優先度**: 対応の優先度（緊急/高/中/低）\n\n"
            "主な確認対象法令：民法、商法、会社法、個人情報保護法、"
            "消費者契約法、特定商取引法、下請法、独占禁止法、労働基準法等\n\n"
            "回答は必ず日本語で、構造化して提供してください。"
        ),
    },
    "risk_analysis": {
        "name": "リスク分析",
        "description": "法的リスクを評価し、対策を提案します",
        "icon": "⚠️",
        "system_prompt": (
            "あなたは日本法に精通したリスク分析の専門家です。"
            "提供された法務文書について、包括的なリスク分析を行ってください：\n\n"
            "1. **リスクマップ**: 特定されたリスクを影響度×発生確率でマッピング\n"
            "2. **高リスク項目**: 最も注意が必要な項目の詳細分析\n"
            "3. **中リスク項目**: 注意すべき項目の概要\n"
            "4. **低リスク項目**: 軽微なリスクの列挙\n"
            "5. **リスク緩和策**: 各リスクに対する具体的な対策\n"
            "6. **推奨アクション**: 優先的に実施すべきアクションプラン\n\n"
            "回答は必ず日本語で、リスクレベルを明確に示して構造化してください。"
        ),
    },
    "nda_review": {
        "name": "NDA（秘密保持契約）レビュー",
        "description": "秘密保持契約の妥当性を評価します",
        "icon": "🔒",
        "system_prompt": (
            "あなたは秘密保持契約（NDA）のレビューに精通した法務専門家です。"
            "提供されたNDAについて、以下の観点から詳細なレビューを行ってください：\n\n"
            "1. **秘密情報の定義**: 範囲の適切性、除外事項の網羅性\n"
            "2. **義務の範囲**: 秘密保持義務、使用制限、返還義務\n"
            "3. **有効期間**: 契約期間と秘密保持義務の存続期間の妥当性\n"
            "4. **例外規定**: 開示が許可される場合の条件\n"
            "5. **損害賠償・違約金**: 違反時の対応と賠償条項\n"
            "6. **双務性**: 一方当事者に不利な条項の有無\n"
            "7. **修正提案**: 具体的な修正案\n\n"
            "回答は必ず日本語で提供してください。"
        ),
    },
    "terms_review": {
        "name": "利用規約レビュー",
        "description": "サービス利用規約の適法性を確認します",
        "icon": "📋",
        "system_prompt": (
            "あなたは利用規約・プライバシーポリシーのレビューに精通した法務専門家です。"
            "提供された利用規約について、以下の観点からレビューを行ってください：\n\n"
            "1. **消費者契約法との整合性**: 不当条項の有無\n"
            "2. **特定商取引法への準拠**: 必要記載事項の確認\n"
            "3. **個人情報保護法への準拠**: プライバシー関連条項の適切性\n"
            "4. **知的財産権**: 著作権・商標等の取扱い\n"
            "5. **免責条項**: 免責範囲の妥当性\n"
            "6. **紛争解決**: 管轄裁判所・準拠法の適切性\n"
            "7. **改善提案**: 具体的な修正案と理由\n\n"
            "回答は必ず日本語で、ユーザー保護の観点も含めて提供してください。"
        ),
    },
    "general_legal": {
        "name": "一般法務相談",
        "description": "法務に関する一般的な質問にお答えします",
        "icon": "💬",
        "system_prompt": (
            "あなたは日本法に精通した法務アドバイザーです。"
            "法務に関する質問に対して、正確で分かりやすい回答を提供してください。\n\n"
            "回答に際しては：\n"
            "- 関連する法令や判例を引用してください\n"
            "- 実務上の注意点も含めてください\n"
            "- 必要に応じて具体例を挙げてください\n"
            "- 専門家への相談が必要な場合はその旨を明記してください\n\n"
            "**注意**: この回答は参考情報であり、正式な法的助言ではありません。"
            "重要な法的判断には弁護士等の専門家にご相談ください。\n\n"
            "回答は必ず日本語で提供してください。"
        ),
    },
}


@app.route("/")
def index():
    """Render the main legal review page."""
    return render_template("index.html", review_types=REVIEW_TYPES)


@app.route("/api/review_types")
def get_review_types():
    """Return available review types."""
    types = {
        key: {"name": val["name"], "description": val["description"], "icon": val["icon"]}
        for key, val in REVIEW_TYPES.items()
    }
    return jsonify(types)


@app.route("/api/review", methods=["POST"])
def review():
    """Perform a legal review using Claude API (streaming)."""
    data = request.json
    if not data:
        return jsonify({"error": "リクエストデータが不正です"}), 400

    document_text = data.get("document", "").strip()
    review_type = data.get("review_type", "contract_review")
    additional_context = data.get("context", "").strip()

    if not document_text:
        return jsonify({"error": "レビュー対象の文書を入力してください"}), 400

    if review_type not in REVIEW_TYPES:
        return jsonify({"error": "不正なレビュータイプです"}), 400

    review_config = REVIEW_TYPES[review_type]
    system_prompt = review_config["system_prompt"]

    # Build user message
    user_message = f"以下の文書をレビューしてください：\n\n---\n{document_text}\n---"
    if additional_context:
        user_message += f"\n\n補足情報・特に確認してほしい点：\n{additional_context}"

    def generate():
        try:
            api_client = get_client()
            with api_client.messages.stream(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            ) as stream:
                for text in stream.text_stream:
                    yield f"data: {json.dumps({'type': 'content', 'text': text}, ensure_ascii=False)}\n\n"

            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except anthropic.APIConnectionError:
            yield f"data: {json.dumps({'type': 'error', 'message': 'Claude APIへの接続に失敗しました。ネットワーク接続を確認してください。'}, ensure_ascii=False)}\n\n"
        except anthropic.RateLimitError:
            yield f"data: {json.dumps({'type': 'error', 'message': 'APIレート制限に達しました。しばらく待ってから再度お試しください。'}, ensure_ascii=False)}\n\n"
        except anthropic.APIStatusError as e:
            yield f"data: {json.dumps({'type': 'error', 'message': f'APIエラーが発生しました: {str(e)}'}, ensure_ascii=False)}\n\n"
        except ValueError as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': f'予期せぬエラーが発生しました: {str(e)}'}, ensure_ascii=False)}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.route("/api/health")
def health():
    """Health check endpoint."""
    has_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    return jsonify({
        "status": "ok",
        "api_key_configured": has_key,
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    print(f"\n🏛️  リーガルレビューシステム起動中...")
    print(f"📍 http://localhost:{port}")
    print(f"🔑 API Key: {'設定済み' if os.environ.get('ANTHROPIC_API_KEY') else '未設定'}\n")
    app.run(host="0.0.0.0", port=port, debug=debug)
