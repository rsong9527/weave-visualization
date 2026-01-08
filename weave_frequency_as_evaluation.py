"""
Using Weave Evaluation for Conversation Analysis Visualization

How it works:
Weave Evaluation has powerful automatic visualization capabilities.
We structure daily conversation analysis as an Evaluation:
1. Dataset: Actual user conversation history
2. Model: Pass-through model
3. Scorer: Topic classifier and keyword presence analyzer

The Evaluation page will automatically generate histograms and scatter plots!
"""

import weave
import asyncio
from collections import Counter

# 1. Sample conversation data (travel-focused topic)
CONVERSATION_HISTORY = [
    {"input": "Best hotels in Hawaii", "expected": "travel"},
    {"input": "I want to go diving in Florida", "expected": "travel"},
    {"input": "Great pizza places in New York", "expected": "food"},
    {"input": "When is the best time to visit California", "expected": "travel"},
    {"input": "How to book train tickets", "expected": "travel"},
    {"input": "Is it going to rain today", "expected": "weather"},
    {"input": "Tourist attractions in Boston", "expected": "travel"},
    {"input": "How to make pasta", "expected": "food"},
    {"input": "Python programming error", "expected": "tech"},
    {"input": "I want to visit the Grand Canyon", "expected": "travel"}
]

# 2. Define model: Pass-through model that returns input as-is
class PassThroughModel(weave.Model):
    @weave.op()
    async def predict(self, input: str) -> dict:
        return {"response": input}

# 3. Define Scorers: These become visualization dimensions
# Tip: Define a scorer for each keyword of interest to see distribution charts

@weave.op()
def topic_classifier(input: str, output: dict) -> dict:
    """Simple rule-based classifier"""
    text = input.lower()
    topic = "other"
    if any(w in text for w in ["weather", "rain", "sunny", "temperature"]):
        topic = "weather"
    elif any(w in text for w in ["food", "pizza", "pasta", "restaurant", "cooking"]):
        topic = "food"
    elif any(w in text for w in ["travel", "visit", "hotel", "tourist", "vacation", "trip", "diving", "attractions", "canyon"]):
        topic = "travel"
    elif any(w in text for w in ["python", "programming", "code", "error", "software"]):
        topic = "tech"
        
    return {"topic": topic}

@weave.op()
def keyword_presence(input: str, output: dict) -> dict:
    """Keyword presence statistics (one-hot like)"""
    text = input.lower()
    return {
        "has_weather": 1 if "weather" in text or "rain" in text else 0,
        "has_travel": 1 if any(w in text for w in ["travel", "visit", "hotel", "trip"]) else 0,
        "has_tech": 1 if "programming" in text or "python" in text else 0,
        "length": len(text)
    }

# 4. Run Evaluation
async def main():
    print("🚀 Running conversation analysis evaluation...")
    weave.init("weave-word-frequency-demo")
    
    # Create dataset
    dataset = CONVERSATION_HISTORY
    
    # Run evaluation
    evaluation = weave.Evaluation(
        name="daily_conversation_analysis",
        dataset=dataset,
        scorers=[topic_classifier, keyword_presence]
    )
    
    model = PassThroughModel()
    results = await evaluation.evaluate(model)
    
    print("\n✅ Analysis complete!")
    print("📊 View the Evaluation page for comparison charts at your W&B project")

if __name__ == "__main__":
    asyncio.run(main())
