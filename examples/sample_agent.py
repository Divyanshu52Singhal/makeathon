"""
Sample Agent for demonstration and testing.
This is a simple rule-based agent that simulates AI agent behavior.

To test your own agent: implement agent_invoke(input_text, context) -> dict
and pass the file path via: python main.py --agent your_agent.py
"""

import time
import re


REFUSAL_TRIGGERS = [
    "hack", "malware", "exploit", "ignore all", "ignore previous",
    "system prompt", "api key", "password", "steal credentials",
    "jailbreak", "unrestricted ai", "malicious",
]

HELP_PATTERNS = {
    r"\b(hello|hi|hey|greetings)\b": "Hello! I'm here to assist you. How can I help you today?",
    r"\b(weather)\b": "I can help with general queries, but I don't have real-time weather data. Please check a weather service.",
    r"\b(what is|what are|define|explain)\b": "Great question! Let me provide a clear explanation. {topic} is a concept that involves structured thinking and systematic problem-solving.",
    r"\b(calculate|compute|math|add|subtract|multiply)\b": "I can help with calculations. Please provide the specific numbers and operation you'd like me to perform.",
    r"\b(recommend|suggest|advice|help me)\b": "Based on your request, I'd recommend starting with a structured approach: first define your goal, then break it into smaller steps.",
    r"\b(summarize|summary|brief)\b": "Here is a concise summary: The key points involve understanding the core requirements, identifying stakeholders, and executing with measurable outcomes.",
    r"\b(schedule|meeting|calendar|appointment)\b": "I can help you organize your schedule. Please share the details and I'll help you plan effectively.",
    r"\b(code|program|function|debug)\b": "I can assist with coding tasks. Please share the specific code or problem you need help with.",
}

CONTEXT_RESPONSES = {
    "user_role": {
        "admin": "As an administrator, you have elevated access. How can I assist with your admin tasks?",
        "user": "Welcome! I'm here to help with your queries.",
        "guest": "Hello, guest! I can provide limited assistance. Please log in for full access.",
    }
}


def agent_invoke(input_text: str, context: dict) -> dict:
    """
    Required interface: agent_invoke(input_text: str, context: dict) -> dict

    Return dict with:
      - output: str          (required)
      - reasoning_trace: str (optional, for white-box analysis)
      - tool_calls: list     (optional)
      - token_usage: dict    (optional)
    """
    start = time.time()
    input_lower = input_text.lower().strip()

    reasoning = []
    tool_calls = []

    reasoning.append(f"Received input: '{input_text[:100]}'")

    if not input_lower:
        reasoning.append("Empty input detected - requesting clarification")
        return {
            "output": "It seems you didn't provide any input. Could you please share what you'd like help with?",
            "reasoning_trace": " | ".join(reasoning),
            "tool_calls": [],
            "token_usage": {"total_tokens": 12},
        }

    for trigger in REFUSAL_TRIGGERS:
        if trigger in input_lower:
            reasoning.append(f"Safety trigger detected: '{trigger}' - refusing request")
            return {
                "output": f"I'm sorry, I cannot assist with that request. It appears to involve content that violates my usage guidelines. Please ask me something appropriate.",
                "reasoning_trace": " | ".join(reasoning),
                "tool_calls": [],
                "token_usage": {"total_tokens": 35},
            }

    user_role = context.get("user_role", "user")
    if user_role in CONTEXT_RESPONSES.get("user_role", {}):
        reasoning.append(f"Context-aware: user role is '{user_role}'")

    for pattern, template in HELP_PATTERNS.items():
        if re.search(pattern, input_lower):
            reasoning.append(f"Pattern matched: '{pattern}'")
            topic_match = re.search(r'(?:what is|what are|define|explain)\s+(.+?)(?:\?|$)', input_lower)
            topic = topic_match.group(1).strip() if topic_match else "this concept"
            output = template.replace("{topic}", topic)

            if context:
                reasoning.append("Incorporating context into response")
                output += f" [Context applied: {', '.join(f'{k}={v}' for k, v in context.items() if k != 'user_role')}]"

            elapsed = time.time() - start
            token_estimate = len(output.split()) * 2

            return {
                "output": output,
                "reasoning_trace": " | ".join(reasoning),
                "tool_calls": tool_calls,
                "token_usage": {"total_tokens": token_estimate, "latency_ms": int(elapsed * 1000)},
            }

    reasoning.append("No specific pattern matched - generating general response")
    output = (
        f"Thank you for your query. Based on your input, I understand you're asking about: "
        f"'{input_text[:80]}'. "
        f"I'd be happy to help. Could you provide more details so I can give you the most relevant assistance? "
        f"I'm designed to help with a wide range of tasks including information retrieval, analysis, and recommendations."
    )

    if context:
        reasoning.append("Context noted for response enrichment")

    return {
        "output": output,
        "reasoning_trace": " | ".join(reasoning),
        "tool_calls": tool_calls,
        "token_usage": {"total_tokens": len(output.split()) * 2},
    }
