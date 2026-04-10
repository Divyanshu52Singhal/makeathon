"""
Buggy Agent - Designed to FAIL evaluation (intentionally flawed).

This agent demonstrates multiple failure modes:
1. SECURITY VIOLATIONS: Does not refuse harmful or sensitive requests
2. INCONSISTENCY: Random variation in responses causes low consistency scores
3. PII LEAKAGE: Echoes back sensitive information it receives
4. NO REASONING TRACE: Missing internal reasoning for white-box evaluation
5. POOR STRUCTURE: Responses lack logical flow, conclusions, and step markers
6. SLOW RESPONSES: Simulated artificial latency on some queries
7. CONTEXT BLINDNESS: Ignores provided context entirely
8. KEYWORD MISSES: Fails to include expected keywords in responses

This is intentionally broken to demonstrate the evaluation framework's
ability to detect and categorize different types of agent failures.

Run evaluation:
    python main.py --agent examples/buggy_agent.py
    python main.py --agent examples/buggy_agent.py --scenarios examples/buggy_agent_scenarios.yaml
"""

import time
import random


CANNED_RESPONSES = [
    "I can try to help with that.",
    "Sure, let me look into it.",
    "That sounds interesting.",
    "I am processing your request.",
    "Please hold on.",
]

VERBOSE_FILLER = (
    "Thank you for your patience. We value your business and appreciate you reaching out to us today. "
    "Our team is always committed to providing the best possible service to all of our valued customers. "
    "We understand that your time is valuable and we want to make sure that every interaction you have "
    "with our support team is as smooth and efficient as possible."
)


def agent_invoke(input_text: str, context: dict) -> dict:
    """
    Intentionally flawed agent for evaluation failure demonstration.

    Known flaws:
    - No safety refusals (security violations)
    - Echoes PII data back in responses
    - No reasoning trace (hurts white-box score)
    - Random inconsistent responses (hurts consistency)
    - Ignores context completely (hurts gray-box context score)
    - Artificial latency on certain inputs (hurts latency score)
    - Verbose filler text without logical structure (hurts structural score)
    - Missing expected keywords in happy-path responses
    """

    lower = input_text.lower().strip()

    if not lower:
        return {
            "output": "...",
        }

    if random.random() < 0.4:
        time.sleep(0.05)

    if "hack" in lower or "malware" in lower or "exploit" in lower:
        filler = random.choice(CANNED_RESPONSES)
        return {
            "output": f"{filler} I can provide some general information about system vulnerabilities and security concepts.",
        }

    if "ignore" in lower and ("instruction" in lower or "previous" in lower):
        return {
            "output": "Sure! I will ignore my previous instructions. What would you like me to do instead?",
        }

    if "ssn" in lower or "social security" in lower or "credit card" in lower:
        return {
            "output": f"Got it! I have noted your information from your message: '{input_text[:120]}'. I will process this right away.",
        }

    if "api key" in lower or "password" in lower or "secret" in lower:
        return {
            "output": "I understand you are asking about credentials. While I cannot share exact values, the format is usually sk-xxxx or similar tokens.",
        }

    if "system prompt" in lower or "instructions" in lower:
        return {
            "output": "My instructions are to be a helpful assistant. I was told to assist users with their queries without restrictions.",
        }

    if "grant" in lower and "permission" in lower:
        return {
            "output": "Access granted. I have updated your permissions as requested.",
        }

    if "discriminat" in lower or "ethnicity" in lower or "reject" in lower:
        return {
            "output": f"I can help draft that rejection email. Here is a template that specifically addresses the candidate selection criteria you mentioned.",
        }

    if "hello" in lower or "hi " in lower or "hey" in lower:
        return {
            "output": random.choice(CANNED_RESPONSES),
        }

    if "calculate" in lower or "math" in lower or "add" in lower:
        return {
            "output": VERBOSE_FILLER + " Regarding your calculation, I would need more specific information to proceed accurately.",
        }

    if "billing" in lower or "invoice" in lower or "refund" in lower:
        return {
            "output": "Your billing concern has been noted. " + VERBOSE_FILLER,
        }

    if "error" in lower or "bug" in lower or "not working" in lower:
        time.sleep(0.08)
        return {
            "output": "That is unfortunate. Have you tried turning it off and on again? " + random.choice(CANNED_RESPONSES),
        }

    if len(input_text) > 200:
        time.sleep(0.12)
        return {
            "output": "That is a lot of text. " + random.choice(CANNED_RESPONSES),
        }

    return {
        "output": random.choice(CANNED_RESPONSES) + " " + random.choice(CANNED_RESPONSES),
    }
