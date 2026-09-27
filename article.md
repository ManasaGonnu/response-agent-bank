# Building a Stateful SRE Incident Memory Agent with Hindsight and Groq

When a critical production service fails at 3:00 AM, mean time to resolution (MTTR) is rarely bottlenecked by compute speed. It is bottlenecked by human memory retrieval.

In modern distributed architectures, teams frequently resolve identical or subtly mutating variants of past outages: connection pool leaks, cascading timeouts, or unevicted memory segments. The institutional knowledge required to resolve these emergencies typically sits trapped in static wiki documents, old Jira post-mortems, or the memory of veteran engineers.

When teams attempt to plug standard LLMs into live incident triage, standard context-window prompting breaks down:

* **Context Bloat:** Stuffing hundreds of historical incident post-mortems into an LLM prompt burns token budgets and degrades reasoning accuracy.
* **Hallucinated Runbooks:** Generic models lack the topology context of an organization's internal architecture, recommending destructive default actions (like rebooting a master database node during an active write spike).
* **Stateless Operations:** Vanilla LLM agents cannot distinguish between past incident patterns, operational warnings, and verified remediation procedures.

To solve this, we engineered an **Autonomous Incident Response & Runbook Memory Agent**. By decoupling persistent institutional memory from high-speed LLM synthesis, this system enables real-time root-cause analysis and executable mitigation runbooks grounded in verified operational history.

---

## High-Level System Architecture

The agent combines low-latency inference with semantic memory retrieval:

```text
                          +-------------------------+
                          |   Production Incident   |
                          |   (Crash Log / Stack)   |
                          +------------+------------+
                                       |
                                       v
               +-----------------------------------------------+
               |                 Streamlit UI                  |
               +-----------------------+-----------------------+
                                       |
                     +-----------------+-----------------+
                     |                                   |
                     v                                   v
       +----------------------------+     +----------------------------+
       |   Hindsight Memory Bank    |     |      Groq LPU Engine       |
       |  (Retain & Recall Engine)  |     |   (openai/gpt-oss-120b)    |
       +--------------+-------------+     +--------------+-------------+
                      |                                  ^
                      | Recalled Runbooks & Warnings     |
                      +----------------------------------+
                                       |
                                       v
                        +------------------------------+
                        |  Targeted Mitigation Plan    |
                        |   & Dangerous Action Guards  |
                        +------------------------------+
```

--- 

## Core Architecture Components

1. **Storage & Ingestion Layer (`Hindsight Memory Bank`):** Historical post-mortems are indexed into Hindsight Cloud (`incident-response-bank`). Hindsight indexes these records as semantic incident entities containing symptoms, log patterns, root causes, and explicit operational warnings.
2. **Fast Reasoning Engine (`Groq LPUs`):** Groq's low-latency inference engine runs `openai/gpt-oss-120b`. By leveraging deterministic compute execution on LPUs, the agent synthesizes multi-step runbooks in seconds.
3. **Interactive Control Plane (`Streamlit UI`):** A dual-column interface designed for on-call engineers to inspect raw retrieved incident memories side-by-side with generated mitigation procedures.

---

## Deep Dive: Hindsight Agent Memory

Standard Vector Database Retrieval-Augmented Generation (RAG) often struggles in SRE pipelines because raw vector proximity does not equate to operational causality. Simple vector search matches error strings while frequently discarding critical constraints attached to those errors.

Hindsight acts as a persistent cognitive layer for agents. By establishing a dedicated memory bank, our agent retains structured post-mortem records:

```python
# seed_memory.py - Incident Post-Mortem Retention
import json
import os
from dotenv import load_dotenv
from hindsight_client import Hindsight

load_dotenv()

client = Hindsight(
    base_url=os.getenv("HINDSIGHT_API_URL"),
    api_key=os.getenv("HINDSIGHT_API_KEY")
)

BANK_ID = os.getenv("HINDSIGHT_BANK_ID")

def seed():
    with open("incidents.json", "r") as f:
        incidents = json.load(f)

    for item in incidents:
        content = (
            f"Incident ID: {item['incident_id']}\n"
            f"Service: {item['service']}\n"
            f"Symptom: {item['symptom']}\n"
            f"Log Snippet: {item['log_snippet']}\n"
            f"Root Cause: {item['root_cause']}\n"
            f"Runbook Fix:\n{item['runbook_fix']}\n"
            f"Critical Warning: {item['warning']}"
        )
        
        client.retain(
            bank_id=BANK_ID,
            content=content,
            metadata={
                "incident_id": item["incident_id"],
                "service": item["service"]
            }
        )
        print(f"Retained {item['incident_id']} into Hindsight memory.")

if __name__ == "__main__":
    seed()


```

When an alert triggers, the agent runs `client.recall(bank_id=BANK_ID, query=error_input)`. Rather than relying on rigid keyword search, Hindsight analyzes the semantic context of the crash trace and retrieves the matching post-mortem, validated mitigation steps, and operational constraints.

---

## High-Speed Synthesis with Groq (`openai/gpt-oss-120b`)

Once Hindsight retrieves the historical record, it is supplied directly to `openai/gpt-oss-120b` via Groq. Fast execution is critical during production outages where every minute of delay multiplies downstream service degradation.

The synthesis prompt explicitly instructs the LLM to ground its remediation plan in the recalled runbooks and explicitly surface dangerous actions:

```python
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

```

## Live Incident Scenario: PostgreSQL Connection Pool Exhaustion

To evaluate the system, we simulated a catastrophic production alert from an order-processing pipeline:

```text
FATAL: remaining connection slots are reserved for non-replication superuser connections (error 53300) at payments-api order_processor.py

```
 
## The "Memoryless LLM" Failure Mode

When passed to an off-the-shelf, stateless LLM without organizational memory, the model typically recommends:
* Running `systemctl restart postgresql`
* Hard-rebooting the primary database instance.

In high-concurrency production environments, rebooting the primary database terminates thousands of active checkout transactions, triggers replica lag, and creates locks that extend an outage significantly.

## The Stateful Agent Response

Our agent queried Hindsight and recalled historical incident **`INC-101`**:

* **Identified Root Cause:** PostgreSQL connection pool saturation driven by unclosed DB connections in the `order_processor` deployment.
* **Mitigation Runbook:**
  1. Scale down the stateless consumer deployment to shed incoming connection load:  
     `kubectl scale deployment order-processor --replicas=2`
  2. Increase client connection allocations in the PgBouncer configuration pool from 100 to 400.
  3. Gracefully reload PgBouncer without terminating active client transaction sockets.
* **Critical Operational Guard:** **"DO NOT restart the primary PostgreSQL master instance directly, as it will abort active in-flight checkout transactions."**

The agent avoided catastrophic downtime by prioritizing verified operational parameters over generic generative completion.

---

## Interactive Streamlit Operations Dashboard

To make this system accessible during high-pressure incidents, we wrapped the pipeline in a dual-column Streamlit interface:

```python
import os
import streamlit as st
from dotenv import load_dotenv
from groq import Groq
from hindsight_client import Hindsight

load_dotenv()

st.set_page_config(page_title="Incident Response Memory Agent", page_icon="🛡️", layout="wide")
st.title("🛡️ Incident Response & Runbook Agent")
st.markdown("Automated production outage triage powered by **Hindsight Agent Memory** and **Groq (GPT-OSS-120B)**.")

error_input = st.text_area(
    "Paste Incident Crash Log or Alert Stack Trace:",
    value="FATAL: remaining connection slots are reserved for non-replication superuser connections (error 53300) at payments-api order_processor.py",
    height=120
)

if st.button("🚀 Analyze Incident & Recall Runbook", type="primary"):
    hindsight = Hindsight(
        base_url=os.getenv("HINDSIGHT_API_URL"),
        api_key=os.getenv("HINDSIGHT_API_KEY")
    )
    groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("🧠 Recalled Hindsight Memory")
        with st.spinner("Searching memory bank for past post-mortems..."):
            response_obj = hindsight.recall(
                bank_id=os.getenv("HINDSIGHT_BANK_ID"),
                query=error_input
            )
            memories_data = response_obj.model_dump() if hasattr(response_obj, "model_dump") else str(response_obj)
            st.success("Matching historical runbooks retrieved!")
            st.json(memories_data)

    with col_right:
        st.subheader("⚡ Automated Mitigation Runbook")
        with st.spinner("Synthesizing step-by-step mitigation plan..."):
            prompt = f"RECALLED MEMORY:\n{memories_data}\n\nINCIDENT:\n{error_input}\nProvide root cause and step-by-step shell runbook."
            response = groq_client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2
            )
            st.markdown(response.choices[0].message.content)

```

Displaying the raw memory objects alongside the generated mitigation plan allows engineers to audit the retrieved context before applying infrastructure commands.

---

## Key Engineering Takeaways

1. **Persistent Memory Outperforms Context Stuffing:** Dumping complete engineering wikis or ticketing databases into LLM context introduces hallucinations, slows inference, and inflates costs. Semantic memory indexing delivers targeted context at lower latency.
2. **Negative Constraints Are Critical in SRE:** In site reliability, knowing what **not** to execute is as critical as knowing the fix. Storing operational boundaries in memory prevents models from defaulting to disruptive recovery actions.
3. **Decoupled Architecture Improves Durability:** Separating the persistent memory bank (Hindsight) from the inference engine (Groq) ensures that operational memory survives model upgrades and infrastructure transitions.

---

## Source Code & Getting Started

The implementation, seed datasets, and runbook definitions are open source on GitHub:  
👉 **[https://github.com/ManasaGonnu/response-agent-bank](https://github.com/ManasaGonnu/response-agent-bank)**


### Running Locally

```powershell
# 1. Clone the repository
git clone https://github.com/ManasaGonnu/response-agent-bank.git
cd response-agent-bank

# 2. Set up virtual environment and install dependencies
python -m venv venv
.\venv\Scripts\Activate
pip install python-dotenv requests groq streamlit hindsight-client

# 3. Ingest historical runbooks into Hindsight
python seed_memory.py

# 4. Launch the interactive dashboard
streamlit run app.py

```
