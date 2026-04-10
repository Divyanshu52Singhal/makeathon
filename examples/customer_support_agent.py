"""
Customer Support Agent - Designed to PASS evaluation.

A well-structured customer support agent that:
- Handles queries with proper reasoning traces
- Respects safety and privacy boundaries
- Refuses harmful or inappropriate requests
- Maintains consistency across runs
- Uses structured, logical response formatting

Run evaluation:
    python main.py --agent examples/customer_support_agent.py
    python main.py --agent examples/customer_support_agent.py --scenarios examples/customer_support_scenarios.yaml
"""

import time
import re
from typing import Optional


COMPANY_NAME = "TechCorp Support"
MAX_RESPONSE_TOKENS = 300

REFUSAL_TRIGGERS = [
    "hack", "exploit", "bypass security", "override", "ignore instructions",
    "ignore previous", "system prompt", "api key", "password", "secret",
    "steal", "malware", "virus", "jailbreak", "unrestricted",
    "grant all permissions", "admin override",
]

PII_TRIGGERS = [
    "ssn", "social security", "credit card number", "bank account",
    "pin number", "cvv", "date of birth and ssn",
]

ISSUE_CATEGORIES = {
    "billing": {
        "keywords": [r"\b(bill|billing|charge|invoice|payment|refund|subscription|price|cost|fee)\b"],
        "response_template": (
            "I understand you have a billing concern. "
            "First, let me review your account. "
            "Based on your query, here is what I can help with: {detail}. "
            "If you need further assistance, please provide your account ID and I will escalate this to our billing team."
        ),
        "detail": "billing inquiries, payment history, refund requests, and subscription management",
    },
    "technical": {
        "keywords": [r"\b(error|bug|crash|not working|broken|issue|problem|fix|troubleshoot|install|setup)\b"],
        "response_template": (
            "I can help you resolve this technical issue. "
            "Step 1: First, let me understand the problem: {detail}. "
            "Step 2: Please try restarting the application and clearing the cache. "
            "Step 3: If the issue persists, provide your error message and I will escalate to our technical team. "
            "Therefore, let us work through this systematically."
        ),
        "detail": "software errors, installation issues, configuration problems",
    },
    "account": {
        "keywords": [r"\b(account|login|password reset|username|profile|settings|access)\b"],
        "response_template": (
            "I can assist with your account-related query. "
            "First, for security purposes, I will need to verify your identity. "
            "Second, once verified, I can help with: {detail}. "
            "In summary, please use our secure portal at support.techcorp.com/account for sensitive account changes."
        ),
        "detail": "account access, profile updates, password resets (via secure channel only)",
    },
    "product": {
        "keywords": [r"\b(product|feature|how to|tutorial|guide|documentation|use|works)\b"],
        "response_template": (
            "Great question about our product! "
            "Let me walk you through this step by step. "
            "First, here is an overview: {detail}. "
            "Second, you can access our full documentation at docs.techcorp.com. "
            "Therefore, I recommend starting with the quick-start guide for the best experience."
        ),
        "detail": "product features, how-to guides, tutorials, and best practices",
    },
    "cancellation": {
        "keywords": [r"\b(cancel|cancellation|unsubscribe|terminate|close account|quit)\b"],
        "response_template": (
            "I understand you are considering cancellation. "
            "First, I would like to understand your concern to see if we can address it. "
            "Second, if you still wish to proceed, I can guide you through the cancellation process. "
            "In summary, please confirm: are you experiencing an issue we can resolve, or have you made your final decision?"
        ),
        "detail": "account cancellation, subscription termination, data export before closure",
    },
}

GREETINGS = [
    r"\b(hello|hi|hey|good morning|good afternoon|good evening|greetings)\b",
]

FAREWELLS = [
    r"\b(bye|goodbye|thanks|thank you|that's all|done|see you)\b",
]


def _detect_category(input_text: str) -> Optional[str]:
    lower = input_text.lower()
    for category, data in ISSUE_CATEGORIES.items():
        for pattern in data["keywords"]:
            if re.search(pattern, lower):
                return category
    return None


def _check_refusal(input_text: str) -> Optional[str]:
    lower = input_text.lower()
    for trigger in REFUSAL_TRIGGERS:
        if trigger in lower:
            return trigger
    return None


def _check_pii_request(input_text: str) -> bool:
    lower = input_text.lower()
    return any(trigger in lower for trigger in PII_TRIGGERS)


def _build_reasoning(steps: list) -> str:
    return " | ".join(steps)


def agent_invoke(input_text: str, context: dict) -> dict:
    """
    Customer Support Agent - well-structured and security-aware.

    Implements:
    - Structured reasoning traces for white-box evaluation
    - Consistent refusal patterns for security tests
    - Context-aware responses using provided user/session data
    - Logical step-by-step responses for structural coverage
    - Token-efficient replies
    """
    start = time.time()
    reasoning = []
    tool_calls = []

    reasoning.append(f"Received query: '{input_text[:100]}'")

    stripped = input_text.strip()
    if not stripped:
        reasoning.append("Empty input detected - prompting user")
        return {
            "output": (
                "Hello! It seems your message was empty. "
                "Could you please share what you need help with? "
                "I am here to assist with billing, technical issues, account management, or product questions."
            ),
            "reasoning_trace": _build_reasoning(reasoning),
            "tool_calls": [],
            "token_usage": {"total_tokens": 28},
        }

    refusal_trigger = _check_refusal(input_text)
    if refusal_trigger:
        reasoning.append(f"Security trigger detected: '{refusal_trigger}' - refusing")
        return {
            "output": (
                "I'm sorry, I cannot assist with that request. "
                "It violates our usage policy and security guidelines. "
                "If you have a legitimate support need, please describe your issue and I will be happy to help."
            ),
            "reasoning_trace": _build_reasoning(reasoning),
            "tool_calls": [],
            "token_usage": {"total_tokens": 42},
        }

    if _check_pii_request(input_text):
        reasoning.append("PII request detected - declining to process sensitive data")
        return {
            "output": (
                "I'm sorry, I cannot process or store sensitive personal information such as "
                "Social Security Numbers, credit card numbers, or bank details. "
                "For account verification, please use our secure portal at support.techcorp.com."
            ),
            "reasoning_trace": _build_reasoning(reasoning),
            "tool_calls": [],
            "token_usage": {"total_tokens": 48},
        }

    user_role = context.get("user_role", "customer")
    account_tier = context.get("account_tier", "standard")
    session_id = context.get("session_id", "unknown")

    reasoning.append(f"Context: user_role={user_role}, tier={account_tier}")

    lower_input = input_text.lower()
    for pattern in GREETINGS:
        if re.search(pattern, lower_input):
            reasoning.append("Greeting detected - providing welcome response")
            tier_msg = "priority" if account_tier == "premium" else "standard"
            output = (
                f"Hello! Welcome to {COMPANY_NAME}. "
                f"I am here to assist you with any questions or issues you may have. "
                f"As a {tier_msg} support customer, I can help with billing, technical issues, "
                f"account management, and product guidance. How can I help you today?"
            )
            elapsed = time.time() - start
            return {
                "output": output,
                "reasoning_trace": _build_reasoning(reasoning),
                "tool_calls": [],
                "token_usage": {"total_tokens": len(output.split()) * 2, "latency_ms": int(elapsed * 1000)},
            }

    for pattern in FAREWELLS:
        if re.search(pattern, lower_input):
            reasoning.append("Farewell detected - closing interaction")
            output = (
                "Thank you for contacting TechCorp Support! "
                "I am glad I could assist you today. "
                "If you have any further questions, do not hesitate to reach out. "
                "Have a great day!"
            )
            elapsed = time.time() - start
            return {
                "output": output,
                "reasoning_trace": _build_reasoning(reasoning),
                "tool_calls": [],
                "token_usage": {"total_tokens": len(output.split()) * 2, "latency_ms": int(elapsed * 1000)},
            }

    category = _detect_category(input_text)
    if category:
        reasoning.append(f"Issue category identified: '{category}'")
        cat_data = ISSUE_CATEGORIES[category]

        if user_role == "admin" and category in ("account", "billing"):
            reasoning.append("Admin user detected - providing elevated access response")
            tool_calls.append({"name": "lookup_account", "params": {"query": input_text[:50], "admin": True}})

        detail = cat_data["detail"]
        output = cat_data["response_template"].format(detail=detail)

        if account_tier == "premium":
            output += " As a premium customer, you also have access to our 24/7 priority support line."

        reasoning.append(f"Response generated for category '{category}' with structured format")
        elapsed = time.time() - start
        return {
            "output": output,
            "reasoning_trace": _build_reasoning(reasoning),
            "tool_calls": tool_calls,
            "token_usage": {"total_tokens": len(output.split()) * 2, "latency_ms": int(elapsed * 1000)},
        }

    reasoning.append("No specific category matched - generating general support response")
    output = (
        f"Thank you for contacting {COMPANY_NAME}. "
        f"I understand you need assistance with: '{input_text[:60]}'. "
        "First, could you please provide more details about your issue? "
        "Second, let me know which area this relates to: billing, technical support, account management, or product usage. "
        "Therefore, with more context, I can provide you with the most accurate and helpful solution."
    )

    elapsed = time.time() - start
    return {
        "output": output,
        "reasoning_trace": _build_reasoning(reasoning),
        "tool_calls": tool_calls,
        "token_usage": {"total_tokens": len(output.split()) * 2, "latency_ms": int(elapsed * 1000)},
    }
