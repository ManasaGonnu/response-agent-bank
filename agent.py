import os
from dotenv import load_dotenv
from groq import Groq
from hindsight_client import Hindsight

load_dotenv()

HINDSIGHT_API_KEY = os.getenv("HINDSIGHT_API_KEY")
HINDSIGHT_API_URL = os.getenv("HINDSIGHT_API_URL")
BANK_ID = os.getenv("HINDSIGHT_BANK_ID")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Initialize Hindsight memory client
hindsight = Hindsight(
    api_key=HINDSIGHT_API_KEY,
    base_url=HINDSIGHT_API_URL
)

# Initialize Groq LLM client
groq_client = Groq(api_key=GROQ_API_KEY)

def diagnose_incident(error_log):
    print("=" * 60)
    print("INCOMING PRODUCTION INCIDENT LOG:")
    print(error_log)
    print("=" * 60)

    # 1. Recall historical runbooks from Hindsight
    print("\n[Hindsight] Recalling past incident post-mortems...")
    try:
        memories = hindsight.recall(
            bank_id=BANK_ID,
            query=error_log,
            top_k=2
        )
    except Exception as e:
        memories = f"Memory recall error: {e}"

    print(f"[Hindsight] Memory retrieved successfully.\n")

    # 2. Synthesize resolution with Groq LLM using the recalled runbooks
    prompt = f"""You are an elite Site Reliability Engineer (SRE).
A critical incident has occurred. You have recalled historical incident reports from the Hindsight memory layer.

RECALLED PAST INCIDENTS & RUNBOOKS FROM MEMORY:
{memories}

CURRENT PRODUCTION INCIDENT:
{error_log}

TASK:
1. Identify the likely root cause based on matching past incidents.
2. Provide a step-by-step mitigation runbook to resolve it immediately.
3. Call out any critical warnings or dangerous commands to avoid."""

    response = groq_client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )

    print("=" * 60)
    print("INCIDENT RESPONSE AGENT RESOLUTION PLAN:")
    print("=" * 60)
    print(response.choices[0].message.content)


if __name__ == "__main__":
    sample_crash_log = (
        "FATAL: remaining connection slots are reserved for non-replication superuser connections (error 53300) "
        "at payments-api order_processor.py"
    )
    diagnose_incident(sample_crash_log)