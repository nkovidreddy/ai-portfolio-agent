# Recording guide

**Opening:** My portfolio intelligence agent helps individual investors monitor company developments and evaluate investment options based on their own financial situation. To demonstrate reliably without exposing sensitive data, I use actual historical company earnings and sample investor profiles.

**Architecture:** Four logical agents work through a central coordinator. Research retrieves evidence, Decision compares three alternatives, and Review applies financial safety checks. User records and financial calculations stay local. Public documents can be reused across user analyses. The prototype uses Python orchestration; a production version would use durable state, authenticated users and independent workers.

**RAG:** The knowledge base indexes curated sections from official investor announcements. The NVIDIA replay uses May 25 and August 24, 2022. Top-three retrieval is ticker-scoped and includes the latest indexed report. Local TF-IDF works without credentials. The optional live API mode provides dense semantic retrieval and an actual language model to analyze the evidence and quote supporting passages. The decision and review rules remain deterministic.

**Demo (offline):** Reset to Q1. Select Profile A, NVIDIA, $2,000, no expense. Show source: 46% annual revenue growth and the EPS caveat. Capacity is $6,000 after commitments and reserve. Show full amount/half amount/wait candidates. Profile B produces zero capacity using the same evidence. Return to A and index Q2: growth slows to 3%, and revenue declined 19% sequentially; the policy changes to wait/review. Reset Q1 and enter a $5,000 expense: capacity drops to $1,000; the full allocation is pruned and review is required.

**Live AI (only if actually successful):** Select Live AI mode and Run analysis. Point to the retrieval mode and model status, and show cited observations. The model can tighten the policy when it identifies reason for caution, but cannot override financial constraints. Its result can differ from offline. If the API fails, point out the transparent offline fallback instead of claiming an actual model ran.

**Evaluation:** Show actual passing tests and GitHub README. No test demonstrates future returns. No trades are executed. Data is historical, not current. A production system will need automated data refresh, validated metrics, security, oversight, and legal/compliance review.
