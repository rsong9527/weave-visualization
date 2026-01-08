"""
Weave + W&B Workspace Integration Demo

This script demonstrates how to:
1. Use Weave for tracing LLM conversations
2. ALSO log metrics to W&B using wandb.log()
3. This allows you to create Custom Charts in W&B Workspace

The key insight: Use BOTH weave.op() for tracing AND wandb.log() for Workspace visualization
"""

import weave
import wandb
from collections import Counter
import asyncio
import re


def tokenize_english(text: str) -> list[str]:
    """Simple English tokenizer"""
    stopwords = {
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
        'should', 'may', 'might', 'must', 'to', 'of', 'in', 'for', 'on', 'with',
        'at', 'by', 'from', 'as', 'into', 'through', 'and', 'but', 'if', 'or',
        'this', 'that', 'these', 'those', 'i', 'me', 'my', 'we', 'our', 'you',
        'your', 'he', 'him', 'his', 'she', 'her', 'it', 'its', 'they', 'them',
        'their', 'what', 'which', 'who', 'whom', 'up', 'down', 'out', 'off'
    }
    text = text.lower()
    words = re.findall(r'\b[a-z]+\b', text)
    return [w for w in words if w not in stopwords and len(w) > 2]


# ============================================================
# Weave Model with W&B Logging
# ============================================================

class LLMResponseModel(weave.Model):
    """LLM model that logs to both Weave AND W&B"""
    model_name: str = "gpt-4"
    temperature: float = 0.7
    
    @weave.op()
    async def predict(self, input_text: str) -> dict:
        """Generate response - tracked by Weave"""
        responses = {
            "weather": "Today is sunny with a temperature of about 75°F. Perfect weather for outdoor activities.",
            "recipe": "I recommend a fresh salad with seasonal vegetables. Use quality ingredients for best results.",
            "travel": "I suggest visiting historical cities. They offer rich culture and beautiful architecture.",
            "programming": "Start with Python - it has clean syntax and is beginner-friendly with great documentation.",
        }
        
        response = "Thank you for your question. I'll provide a detailed answer."
        for key, val in responses.items():
            if key in input_text.lower():
                response = val
                break
        
        return {
            "response": response,
            "model": self.model_name,
            "temperature": self.temperature,
            "input_tokens": len(input_text.split()),
            "output_tokens": len(response.split())
        }


# ============================================================
# Scorers that ALSO log to W&B
# ============================================================

@weave.op()
def word_frequency_scorer(input_text: str, model_output: dict) -> dict:
    """Word frequency scorer - logs to BOTH Weave and W&B"""
    response = model_output.get("response", "")
    tokens = tokenize_english(response)
    word_freq = Counter(tokens)
    
    total_tokens = len(tokens)
    unique_tokens = len(word_freq)
    diversity = unique_tokens / max(total_tokens, 1)
    
    # Log to W&B for Workspace visualization!
    wandb.log({
        "word_freq/total_tokens": total_tokens,
        "word_freq/unique_tokens": unique_tokens,
        "word_freq/diversity": diversity,
    })
    
    return {
        "total_tokens": total_tokens,
        "unique_tokens": unique_tokens,
        "token_diversity": diversity,
    }


@weave.op()
def response_quality_scorer(input_text: str, model_output: dict) -> dict:
    """Response quality scorer - logs to BOTH Weave and W&B"""
    response = model_output.get("response", "")
    
    length_score = min(len(response) / 100, 1.0)
    keywords = ["recommend", "suggest", "perfect", "great", "best"]
    keyword_count = sum(1 for kw in keywords if kw in response.lower())
    keyword_score = keyword_count / len(keywords)
    overall_score = (length_score + keyword_score) / 2
    
    # Log to W&B for Workspace visualization!
    wandb.log({
        "quality/length_score": length_score,
        "quality/keyword_score": keyword_score,
        "quality/overall_score": overall_score,
    })
    
    return {
        "length_score": round(length_score, 2),
        "keyword_score": round(keyword_score, 2),
        "overall_score": round(overall_score, 2)
    }


# ============================================================
# Main Function
# ============================================================

async def run_evaluation():
    """Run evaluation with BOTH Weave tracing AND W&B logging"""
    print("=" * 60)
    print("Weave + W&B Workspace Integration Demo")
    print("=" * 60)
    
    # 1. Initialize BOTH Weave and W&B
    print("\n📌 Initializing Weave and W&B...")
    weave.init("weave-word-frequency-demo")
    
    # Start a W&B run for Workspace logging
    run = wandb.init(
        project="weave-word-frequency-demo",
        name="evaluation-with-workspace",
        config={
            "model": "gpt-4",
            "temperature": 0.7,
            "evaluation_type": "word_frequency"
        }
    )
    
    # 2. Create model and dataset
    print("\n📌 Creating model and dataset...")
    model = LLMResponseModel(model_name="gpt-4", temperature=0.7)
    
    dataset = [
        {"input_text": "What's the weather like today?", "expected_topic": "weather"},
        {"input_text": "Can you recommend a good recipe?", "expected_topic": "recipe"},
        {"input_text": "What are the best travel destinations?", "expected_topic": "travel"},
        {"input_text": "How do I start programming?", "expected_topic": "programming"},
        {"input_text": "Explain machine learning basics", "expected_topic": "tech"},
        {"input_text": "Tips for healthy lifestyle", "expected_topic": "health"},
    ]
    
    # 3. Run evaluation
    print("\n📌 Running Weave Evaluation (also logging to W&B)...")
    evaluation = weave.Evaluation(
        name="word_frequency_with_workspace",
        dataset=dataset,
        scorers=[word_frequency_scorer, response_quality_scorer]
    )
    
    results = await evaluation.evaluate(model)
    
    # 4. Log word frequency table to W&B
    print("\n📌 Logging word frequency table to W&B...")
    
    # Collect all words from responses
    all_words = []
    for item in dataset:
        output = await model.predict(item["input_text"])
        tokens = tokenize_english(output["response"])
        all_words.extend(tokens)
    
    word_freq = Counter(all_words)
    
    # Create W&B Table for Custom Chart
    table = wandb.Table(columns=["word", "frequency"])
    for word, freq in word_freq.most_common(20):
        table.add_data(word, freq)
    
    wandb.log({"word_frequency_table": table})
    
    # Create bar chart
    wandb.log({
        "word_frequency_chart": wandb.plot.bar(
            table, "word", "frequency", title="Top 20 Word Frequency"
        )
    })
    
    # 5. Finish
    run.finish()
    
    print("\n" + "=" * 60)
    print("✅ Done!")
    print(f"📊 Weave UI: https://wandb.ai/weave-trace-move/weave-word-frequency-demo/weave")
    print(f"📈 W&B Workspace: {run.url}")
    print("=" * 60)
    print("\nNow you can:")
    print("1. View Weave Evaluation in Weave UI")
    print("2. Create Custom Charts in W&B Workspace using the logged metrics")
    print("3. Add panels to Workspace showing word frequency over time")
    
    return results


if __name__ == "__main__":
    asyncio.run(run_evaluation())

