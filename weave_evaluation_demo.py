"""
Weave Evaluation Demo

This script demonstrates:
1. Creating a Weave Evaluation
2. Recording custom metrics (including word frequency) in Evaluation
3. Comparing results across different Evaluations
"""

import weave
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
# Weave Model Definition
# ============================================================

class LLMResponseModel(weave.Model):
    """
    Simulated LLM response model
    Replace with real LLM API calls in production
    """
    model_name: str = "gpt-4"
    temperature: float = 0.7
    
    @weave.op()
    async def predict(self, input_text: str) -> dict:
        """Generate response"""
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
# Weave Evaluation Scorers
# ============================================================

@weave.op()
def word_frequency_scorer(input_text: str, model_output: dict) -> dict:
    """
    Word frequency analysis scorer
    Computes word frequency stats from response
    """
    response = model_output.get("response", "")
    tokens = tokenize_english(response)
    word_freq = Counter(tokens)
    
    total_tokens = len(tokens)
    unique_tokens = len(word_freq)
    avg_token_length = sum(len(t) for t in tokens) / max(total_tokens, 1)
    
    top_5 = dict(word_freq.most_common(5))
    
    return {
        "total_tokens": total_tokens,
        "unique_tokens": unique_tokens,
        "token_diversity": unique_tokens / max(total_tokens, 1),
        "avg_token_length": round(avg_token_length, 2),
        "top_5_words": top_5
    }


@weave.op()
def response_quality_scorer(input_text: str, model_output: dict) -> dict:
    """
    Response quality scorer
    """
    response = model_output.get("response", "")
    
    # Simple quality metrics
    length_score = min(len(response) / 100, 1.0)
    
    # Check for helpful keywords
    keywords = ["recommend", "suggest", "perfect", "great", "best"]
    keyword_count = sum(1 for kw in keywords if kw in response.lower())
    keyword_score = keyword_count / len(keywords)
    
    return {
        "length_score": round(length_score, 2),
        "keyword_score": round(keyword_score, 2),
        "overall_score": round((length_score + keyword_score) / 2, 2)
    }


@weave.op()
def token_efficiency_scorer(input_text: str, model_output: dict) -> dict:
    """
    Token efficiency scorer
    """
    input_tokens = model_output.get("input_tokens", 0)
    output_tokens = model_output.get("output_tokens", 0)
    
    ratio = output_tokens / max(input_tokens, 1)
    
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "token_ratio": round(ratio, 2),
        "total_tokens": input_tokens + output_tokens
    }


# ============================================================
# Evaluation Dataset
# ============================================================

def create_evaluation_dataset() -> list[dict]:
    """Create evaluation dataset"""
    return [
        {"input_text": "What's the weather like today?", "expected_topic": "weather"},
        {"input_text": "Can you recommend a good recipe?", "expected_topic": "recipe"},
        {"input_text": "What are the best travel destinations?", "expected_topic": "travel"},
        {"input_text": "How do I start programming?", "expected_topic": "programming"},
        {"input_text": "Explain machine learning basics", "expected_topic": "tech"},
        {"input_text": "Tips for healthy lifestyle", "expected_topic": "health"},
        {"input_text": "How to learn a new language?", "expected_topic": "learning"},
        {"input_text": "Best practices for writing emails", "expected_topic": "business"},
    ]


# ============================================================
# Main Function
# ============================================================

async def run_evaluation():
    """Run Weave Evaluation"""
    print("=" * 60)
    print("Weave Evaluation - Word Frequency Demo")
    print("=" * 60)
    
    # 1. Initialize Weave
    print("\n📌 Initializing Weave...")
    weave.init("weave-word-frequency-demo")
    
    # 2. Create model
    print("\n📌 Creating LLM model...")
    model = LLMResponseModel(model_name="gpt-4", temperature=0.7)
    
    # 3. Create evaluation dataset
    print("\n📌 Creating evaluation dataset...")
    dataset = create_evaluation_dataset()
    
    # 4. Run evaluation
    print("\n📌 Running Weave Evaluation...")
    evaluation = weave.Evaluation(
        name="word_frequency_evaluation",
        dataset=dataset,
        scorers=[
            word_frequency_scorer,
            response_quality_scorer,
            token_efficiency_scorer
        ]
    )
    
    results = await evaluation.evaluate(model)
    
    # 5. Print results summary
    print("\n" + "=" * 60)
    print("Evaluation Results Summary")
    print("=" * 60)
    print(f"Results: {results}")
    
    return results


if __name__ == "__main__":
    asyncio.run(run_evaluation())
    
    print("\n📊 View Weave Evaluation at your W&B project")
    print("✅ Evaluation complete! All data logged to Weave.")
