"""
Weave Word Frequency Analysis Demo

This script demonstrates:
1. Using Weave to track LLM conversations
2. Tokenizing English text
3. Computing word frequency
4. All data is automatically tracked via Weave traces
"""

import weave
from collections import Counter
import re


def tokenize_english(text: str) -> list[str]:
    """
    Simple English tokenizer
    Returns list of words (lowercase, filtered stopwords)
    """
    # Common English stopwords
    stopwords = {
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
        'should', 'may', 'might', 'must', 'shall', 'can', 'need', 'dare',
        'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from', 'as',
        'into', 'through', 'during', 'before', 'after', 'above', 'below',
        'between', 'under', 'again', 'further', 'then', 'once', 'here',
        'there', 'when', 'where', 'why', 'how', 'all', 'each', 'few', 'more',
        'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only', 'own',
        'same', 'so', 'than', 'too', 'very', 'just', 'and', 'but', 'if', 'or',
        'because', 'until', 'while', 'about', 'against', 'this', 'that', 'these',
        'those', 'i', 'me', 'my', 'myself', 'we', 'our', 'ours', 'ourselves',
        'you', 'your', 'yours', 'yourself', 'yourselves', 'he', 'him', 'his',
        'himself', 'she', 'her', 'hers', 'herself', 'it', 'its', 'itself',
        'they', 'them', 'their', 'theirs', 'themselves', 'what', 'which', 'who',
        'whom', 'up', 'down', 'out', 'off', 'over'
    }
    
    # Convert to lowercase and extract words
    text = text.lower()
    words = re.findall(r'\b[a-z]+\b', text)
    
    # Filter stopwords and short words
    return [w for w in words if w not in stopwords and len(w) > 2]


# ============================================================
# Weave decorated functions - these calls are automatically tracked
# ============================================================

@weave.op()
def tokenize_conversation(conversation: str) -> dict:
    """
    Tokenize a single conversation and return word frequency stats
    This function is automatically tracked by Weave
    """
    tokens = tokenize_english(conversation)
    word_freq = dict(Counter(tokens))
    
    return {
        "tokens": tokens,
        "word_frequency": word_freq,
        "total_tokens": len(tokens),
        "unique_tokens": len(word_freq)
    }


@weave.op()
def create_word_frequency_summary(word_freq: dict) -> dict:
    """
    Create word frequency summary
    Output is automatically logged to Weave
    """
    sorted_freq = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
    
    result = {
        "total_unique_words": len(word_freq),
        "total_word_count": sum(word_freq.values()),
        "top_20_words": dict(sorted_freq[:20]),
    }
    
    # Add top 10 words as separate numeric fields for Trace Plots
    for i, (word, count) in enumerate(sorted_freq[:10]):
        result[f"top_{i+1}_word"] = word
        result[f"top_{i+1}_count"] = count
    
    return result


@weave.op()
def analyze_conversations(conversations: list[str]) -> dict:
    """
    Analyze word frequency across multiple conversations
    All stats are automatically logged to Weave
    """
    all_tokens = []
    conversation_stats = []
    
    for i, conv in enumerate(conversations):
        tokens = tokenize_english(conv)
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
        # Numeric fields for Trace Plots visualization
        "total_tokens": len(all_tokens),
        "unique_tokens": len(total_freq),
        "token_diversity_ratio": len(total_freq) / max(len(all_tokens), 1),
        "avg_tokens_per_conversation": len(all_tokens) / max(len(conversations), 1),
    }
    
    # Add top 10 word frequencies as numeric fields
    for i, (word, count) in enumerate(sorted_freq[:10]):
        result[f"word_{i+1}"] = word
        result[f"word_{i+1}_freq"] = count
    
    return result


@weave.op()
def simulate_llm_conversation(user_input: str, model_name: str = "gpt-4") -> dict:
    """
    Simulate LLM conversation (replace with real API call in production)
    Input and output are automatically logged to Weave
    """
    # Simulated responses based on keywords
    simulated_responses = {
        "weather": "Today's weather is sunny with a temperature of about 75°F. It's a perfect day for outdoor activities. The forecast shows clear skies throughout the afternoon.",
        "recipe": "I recommend trying a fresh vegetable salad with seasonal ingredients. Start with mixed greens, add cherry tomatoes, cucumber, and top with a light vinaigrette dressing.",
        "travel": "For travel destinations, I highly recommend visiting national parks. They offer stunning natural beauty, hiking trails, and camping opportunities.",
        "programming": "For programming beginners, I suggest starting with Python. It has a clean syntax, extensive libraries, and a supportive community for learning.",
        "machine learning": "Machine learning is a subset of artificial intelligence that enables systems to learn from data. Key concepts include training, validation, and model evaluation.",
    }
    
    # Select response based on input
    response = "Thank you for your question. I'd be happy to help you with more information."
    for key, val in simulated_responses.items():
        if key in user_input.lower():
            response = val
            break
    
    return {
        "user_input": user_input,
        "assistant_response": response,
        "model_name": model_name,
        "input_tokens": len(user_input.split()),
        "output_tokens": len(response.split())
    }


@weave.op()
def full_conversation_analysis(user_inputs: list[str]) -> dict:
    """
    Complete conversation analysis pipeline
    Includes: simulate conversations -> tokenize -> word frequency stats
    The entire flow is tracked by Weave
    """
    # 1. Simulate all conversations
    conversations = []
    for user_input in user_inputs:
        result = simulate_llm_conversation(user_input)
        conversations.append(result)
    
    # 2. Combine all text
    all_texts = [c["user_input"] + " " + c["assistant_response"] for c in conversations]
    
    # 3. Analyze word frequency
    analysis = analyze_conversations(all_texts)
    
    # 4. Create word frequency summary
    word_freq = {}
    for text in all_texts:
        tokens = tokenize_english(text)
        for token in tokens:
            word_freq[token] = word_freq.get(token, 0) + 1
    
    summary = create_word_frequency_summary(word_freq)
    
    return {
        "conversations": conversations,
        "analysis": analysis,
        "word_frequency_summary": summary
    }


# ============================================================
# Main function - demonstrates complete flow
# ============================================================

def main():
    """
    Full demo: Weave tracing + English tokenization
    All data is automatically logged to Weave
    """
    print("=" * 60)
    print("Weave Word Frequency Analysis Demo")
    print("=" * 60)
    
    # 1. Initialize Weave
    print("\n📌 Step 1: Initializing Weave...")
    weave.init("weave-word-frequency-demo")
    
    # 2. Run full analysis pipeline
    print("\n📌 Step 2: Running conversation analysis...")
    sample_conversations = [
        "What's the weather like today?",
        "Can you recommend a good recipe for dinner?",
        "I'm planning a travel trip, any suggestions?",
        "How do I get started with programming?",
        "Explain machine learning to me in simple terms.",
        "What are the best programming languages to learn?",
        "Tell me about weather patterns in different seasons.",
        "I need travel tips for Europe.",
    ]
    
    # Call full_conversation_analysis - the entire flow is tracked by Weave
    result = full_conversation_analysis(sample_conversations)
    
    # 3. Print results summary
    print("\n📌 Step 3: Analysis Results...")
    print(f"  Conversations: {len(result['conversations'])}")
    print(f"  Total Tokens: {result['analysis']['total_tokens']}")
    print(f"  Unique Tokens: {result['analysis']['unique_tokens']}")
    print(f"  Diversity Ratio: {result['analysis']['token_diversity_ratio']:.2%}")
    
    print(f"\n  Top 10 Word Frequency:")
    for word, freq in list(result['analysis']['total_word_frequency'].items())[:10]:
        print(f"    {word}: {freq}")
    
    print("\n" + "=" * 60)
    print("✅ Done! All data has been automatically logged to Weave")
    print("📊 View Weave Traces at your W&B project")
    print("=" * 60)


if __name__ == "__main__":
    main()
