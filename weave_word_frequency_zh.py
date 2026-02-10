"""
Weave 中文词频分析 Demo
Weave Chinese Word Frequency Analysis Demo

本脚本演示:
1. 使用 Weave 追踪 LLM 对话
2. 使用 jieba 进行中文分词
3. 计算中文词频统计
4. 所有数据通过 Weave traces 自动追踪

灵感来源: wandb/llm-leaderboard (Nejumi Leaderboard - 日文 LLM 评测)
目标: 构建中文版 LLM 评测和可视化能力
"""

import weave
from collections import Counter
import re

# Try to import jieba for Chinese tokenization
try:
    import jieba
    import jieba.analyse
    JIEBA_AVAILABLE = True
except ImportError:
    JIEBA_AVAILABLE = False
    print("Warning: jieba not installed. Using basic Chinese tokenization.")
    print("Install with: pip install jieba")


# ============================================================
# 中文分词器 (Chinese Tokenizer)
# ============================================================

# 中文停用词表 (Chinese Stopwords)
CHINESE_STOPWORDS = {
    '的', '了', '在', '是', '我', '有', '和', '就', '不', '人',
    '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去',
    '你', '会', '着', '没有', '看', '好', '自己', '这', '他', '她',
    '它', '么', '那', '被', '从', '些', '还', '对', '吗', '呢',
    '把', '让', '给', '等', '用', '又', '能', '但', '为', '以',
    '及', '或', '与', '则', '而', '所', '其', '之', '可以', '因为',
    '所以', '如果', '但是', '虽然', '虽', '然', '然后', '这个', '那个',
    '什么', '怎么', '哪', '哪个', '哪些', '为什么', '怎样', '如何',
    '多少', '几', '啊', '吧', '呀', '嗯', '哦', '哈', '嘛', '呗',
    '地', '得', '过', '来', '去', '起来', '下去', '出来', '进去',
    '回来', '上去', '下来', '起', '开', '着', '了', '过', '比',
    '更', '最', '非常', '十分', '特别', '相当', '比较', '稍微',
}


def tokenize_chinese(text: str) -> list[str]:
    """
    中文分词器
    使用 jieba 进行分词, 过滤停用词和标点

    Args:
        text: 待分词的中文文本
    Returns:
        分词后的词语列表
    """
    if JIEBA_AVAILABLE:
        # 使用 jieba 精确模式分词
        words = jieba.lcut(text)
    else:
        # 基础分词: 按单字切分 (不推荐, 仅作为后备方案)
        words = list(text)

    # 过滤停用词、标点符号和空白字符
    filtered = []
    for w in words:
        w = w.strip()
        if not w:
            continue
        if w in CHINESE_STOPWORDS:
            continue
        # 过滤纯标点和数字
        if re.match(r'^[\W\d]+$', w) and not re.match(r'[\u4e00-\u9fff]', w):
            continue
        # 过滤单字 (通常信息量低)
        if len(w) < 2 and not re.match(r'[\u4e00-\u9fff]', w):
            continue
        filtered.append(w)

    return filtered


def extract_keywords_chinese(text: str, top_k: int = 20) -> list[tuple[str, float]]:
    """
    提取中文关键词 (使用 TF-IDF)

    Args:
        text: 中文文本
        top_k: 返回前 K 个关键词
    Returns:
        [(关键词, 权重), ...] 列表
    """
    if JIEBA_AVAILABLE:
        keywords = jieba.analyse.extract_tags(text, topK=top_k, withWeight=True)
        return keywords
    else:
        # 后备方案: 简单词频统计
        tokens = tokenize_chinese(text)
        freq = Counter(tokens)
        total = sum(freq.values())
        return [(w, c / total) for w, c in freq.most_common(top_k)]


# ============================================================
# Weave 装饰函数 - 调用自动追踪
# ============================================================

@weave.op()
def tokenize_conversation_zh(conversation: str) -> dict:
    """
    对单条对话进行中文分词, 返回词频统计
    此函数由 Weave 自动追踪
    """
    tokens = tokenize_chinese(conversation)
    word_freq = dict(Counter(tokens))

    return {
        "tokens": tokens,
        "word_frequency": word_freq,
        "total_tokens": len(tokens),
        "unique_tokens": len(word_freq)
    }


@weave.op()
def create_word_frequency_summary_zh(word_freq: dict) -> dict:
    """
    创建中文词频摘要
    输出自动记录到 Weave
    """
    sorted_freq = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)

    result = {
        "total_unique_words": len(word_freq),
        "total_word_count": sum(word_freq.values()),
        "top_20_words": dict(sorted_freq[:20]),
    }

    # 添加前10个高频词作为独立数值字段 (用于 Trace Plots)
    for i, (word, count) in enumerate(sorted_freq[:10]):
        result[f"top_{i+1}_word"] = word
        result[f"top_{i+1}_count"] = count

    return result


@weave.op()
def analyze_conversations_zh(conversations: list[str]) -> dict:
    """
    分析多条中文对话的词频
    所有统计数据自动记录到 Weave
    """
    all_tokens = []
    conversation_stats = []

    for i, conv in enumerate(conversations):
        tokens = tokenize_chinese(conv)
        all_tokens.extend(tokens)
        conversation_stats.append({
            "conversation_id": i,
            "token_count": len(tokens),
            "unique_tokens": len(set(tokens))
        })

    total_freq = dict(Counter(all_tokens))
    sorted_freq = sorted(total_freq.items(), key=lambda x: x[1], reverse=True)

    result = {
        "total_word_frequency": dict(sorted_freq[:20]),
        "conversation_stats": conversation_stats,
        # 用于 Trace Plots 可视化的数值字段
        "total_tokens": len(all_tokens),
        "unique_tokens": len(total_freq),
        "token_diversity_ratio": len(total_freq) / max(len(all_tokens), 1),
        "avg_tokens_per_conversation": len(all_tokens) / max(len(conversations), 1),
    }

    # 添加前10个高频词作为数值字段
    for i, (word, count) in enumerate(sorted_freq[:10]):
        result[f"word_{i+1}"] = word
        result[f"word_{i+1}_freq"] = count

    return result


@weave.op()
def simulate_llm_conversation_zh(user_input: str, model_name: str = "gpt-4") -> dict:
    """
    模拟中文 LLM 对话 (生产环境中替换为真实 API 调用)
    输入和输出自动记录到 Weave
    """
    # 基于关键词的模拟中文回复
    simulated_responses = {
        "天气": "今天天气晴朗，气温大约25度，非常适合户外活动。预报显示下午将持续晴天，紫外线指数中等，建议做好防晒措施。",
        "食谱": "我推荐试试清炒时蔬配蒜蓉。先将新鲜蔬菜洗净切好，热锅凉油，加入蒜末爆香，然后大火快炒蔬菜，最后加盐调味即可。简单美味又健康。",
        "旅行": "推荐去云南大理旅行。大理有着美丽的洱海风光、古城文化和白族特色美食。最佳旅行时间是春秋两季，气候宜人，风景如画。",
        "编程": "对于编程初学者，我建议从Python开始学习。Python语法简洁清晰，拥有丰富的库和活跃的社区支持，非常适合入门学习。可以从基础数据类型和控制流开始。",
        "机器学习": "机器学习是人工智能的一个子领域，它使计算机系统能够从数据中学习。核心概念包括训练集、验证集、模型评估和超参数调优。深度学习是其中最热门的分支。",
        "大模型": "大语言模型（LLM）是基于Transformer架构的大规模预训练模型。代表性模型包括GPT系列、Claude、Llama等。评估大模型的能力需要多维度的基准测试。",
        "评测": "LLM评测是衡量大语言模型能力的重要手段。中文评测基准包括C-Eval、CMMLU、SuperCLUE等，涵盖知识理解、推理能力、安全性等多个维度。",
    }

    # 根据输入选择回复
    response = "感谢您的提问。我很乐意为您提供更多相关信息和帮助。"
    for key, val in simulated_responses.items():
        if key in user_input:
            response = val
            break

    return {
        "user_input": user_input,
        "assistant_response": response,
        "model_name": model_name,
        "input_chars": len(user_input),
        "output_chars": len(response)
    }


@weave.op()
def full_conversation_analysis_zh(user_inputs: list[str]) -> dict:
    """
    完整的中文对话分析流水线
    包括: 模拟对话 -> 分词 -> 词频统计
    整个流程由 Weave 追踪
    """
    # 1. 模拟所有对话
    conversations = []
    for user_input in user_inputs:
        result = simulate_llm_conversation_zh(user_input)
        conversations.append(result)

    # 2. 合并所有文本
    all_texts = [c["user_input"] + " " + c["assistant_response"] for c in conversations]

    # 3. 分析词频
    analysis = analyze_conversations_zh(all_texts)

    # 4. 创建词频摘要
    word_freq = {}
    for text in all_texts:
        tokens = tokenize_chinese(text)
        for token in tokens:
            word_freq[token] = word_freq.get(token, 0) + 1

    summary = create_word_frequency_summary_zh(word_freq)

    # 5. 提取关键词 (TF-IDF)
    combined_text = " ".join(all_texts)
    keywords = extract_keywords_chinese(combined_text, top_k=15)

    return {
        "conversations": conversations,
        "analysis": analysis,
        "word_frequency_summary": summary,
        "tfidf_keywords": [{"keyword": kw, "weight": round(w, 4)} for kw, w in keywords]
    }


# ============================================================
# 主函数 - 演示完整流程
# ============================================================

def main():
    """
    完整演示: Weave 追踪 + 中文分词 + 词频分析
    所有数据自动记录到 Weave
    """
    print("=" * 60)
    print("Weave 中文词频分析 Demo")
    print("Weave Chinese Word Frequency Analysis Demo")
    print("=" * 60)

    # 1. 初始化 Weave
    print("\n📌 步骤 1: 初始化 Weave...")
    weave.init("weave-word-frequency-zh-demo")

    # 2. 运行完整分析流水线
    print("\n📌 步骤 2: 运行中文对话分析...")
    sample_conversations = [
        "今天的天气怎么样？",
        "能推荐一个好的食谱吗？",
        "我想去旅行，有什么建议？",
        "如何入门编程？",
        "用简单的话解释一下机器学习。",
        "大模型有哪些代表性的？",
        "如何评测大语言模型的能力？",
        "推荐一些中文的编程学习资源。",
    ]

    # 调用 full_conversation_analysis_zh - 整个流程由 Weave 追踪
    result = full_conversation_analysis_zh(sample_conversations)

    # 3. 输出结果摘要
    print("\n📌 步骤 3: 分析结果...")
    print(f"  对话数量: {len(result['conversations'])}")
    print(f"  总词数: {result['analysis']['total_tokens']}")
    print(f"  不重复词数: {result['analysis']['unique_tokens']}")
    print(f"  词汇多样性: {result['analysis']['token_diversity_ratio']:.2%}")

    print(f"\n  前10个高频词:")
    for word, freq in list(result['analysis']['total_word_frequency'].items())[:10]:
        print(f"    {word}: {freq}")

    if result.get('tfidf_keywords'):
        print(f"\n  TF-IDF 关键词:")
        for item in result['tfidf_keywords'][:10]:
            print(f"    {item['keyword']}: {item['weight']}")

    print("\n" + "=" * 60)
    print("✅ 完成! 所有数据已自动记录到 Weave")
    print("📊 在 W&B 项目中查看 Weave Traces")
    print("=" * 60)


if __name__ == "__main__":
    main()
