import os
import streamlit as st
from dotenv import load_dotenv
from groq import Groq
from hindsight_client import Hindsight

# 1. Load environment variables
load_dotenv()

HINDSIGHT_API_KEY = os.getenv("HINDSIGHT_API_KEY")
HINDSIGHT_API_URL = os.getenv("HINDSIGHT_API_URL", "https://api.hindsight.vectorize.io")
BANK_ID = os.getenv("HINDSIGHT_BANK_ID", "incident-response-bank")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# 2. Configure Streamlit page
st.set_page_config(
    page_title="Incident Response Memory Agent",
    page_icon="🛡️",
    layout="wide"
)

st.title("🛡️ Incident Response & Runbook Agent")
st.markdown(
    "Automated production outage triage powered by **Hindsight Agent Memory** and **Groq (GPT-OSS-120B)**."
)

# 3. Input Form Area
st.subheader("1. Incident Intake")
default_log = (
    "FATAL: remaining connection slots are reserved for non-replication "
    "superuser connections (error 53300) at payments-api order_processor.py"
)

error_input = st.text_area(
    "Paste Incident Crash Log or Alert Stack Trace:",
    value=default_log,
    height=120
)

# 4. Action Button
if st.button("🚀 Analyze Incident & Recall Runbook", type="primary"):
    if not error_input.strip():
        st.warning("Please provide an incident log snippet to analyze.")
    else:
        # Initialize Clients according to the SDK signature
        hindsight = Hindsight(
            base_url=HINDSIGHT_API_URL,
            api_key=HINDSIGHT_API_KEY
        )
        groq_client = Groq(api_key=GROQ_API_KEY)

        col_left, col_right = st.columns(2)

        # Left Column: Hindsight Memory Recall
        with col_left:
            st.subheader("🧠 Recalled Hindsight Memory")
            with st.spinner("Searching memory bank for past post-mortems..."):
                try:
                    response_obj = hindsight.recall(
                        bank_id=BANK_ID,
                        query=error_input
                    )
                    
                    # Convert response object to dict/text for display
                    if hasattr(response_obj, "model_dump"):
                        memories_data = response_obj.model_dump()
                    elif hasattr(response_obj, "to_dict"):
                        memories_data = response_obj.to_dict()
                    else:
                        memories_data = str(response_obj)
                    
                    st.success("Matching historical runbooks retrieved!")
                    st.json(memories_data)
                    memory_context = str(memories_data)
                except Exception as e:
                    st.error(f"Recall Failed: {e}")
                    memory_context = "No historical incident context found."

        # Right Column: Groq LLM Synthesis
        with col_right:
            st.subheader("⚡ Automated Mitigation Runbook")
            with st.spinner("Synthesizing step-by-step mitigation plan..."):
                prompt = f"""You are an elite Site Reliability Engineer (SRE).
A production outage has occurred. Use the recalled historical runbooks from Hindsight memory to resolve the current error.

RECALLED PAST INCIDENTS & RUNBOOKS FROM MEMORY:
{memory_context}

CURRENT PRODUCTION INCIDENT:
{error_input}

TASK:
1. State the identified root cause based on matching historical post-mortems.
2. Provide a clear, executable step-by-step shell runbook.
3. List critical warnings and dangerous commands that the engineer must avoid."""

                try:
                    response = groq_client.chat.completions.create(
                        model="openai/gpt-oss-120b",
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.2
                    )
                    st.markdown(response.choices[0].message.content)
                except Exception as e:
                    st.error(f"LLM Generation Failed: {e}")