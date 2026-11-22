"""Command-line demo: before/after RAG, user personalization, safety stop."""
import json
from portfolio_agent import CoordinatorAgent
from portfolio_agent.retrieval import LocalKnowledgeBase


def main():
    kb = LocalKnowledgeBase(include_new_report=False)
    agent = CoordinatorAgent(kb=kb)
    cases = [
        ("1. Before newer report — User A", "user_a", 0),
        ("2. Before newer report — User B", "user_b", 0),
    ]
    results = {}
    for label, user, expense in cases:
        result = agent.analyze(user, unexpected_expense=expense)
        results[label] = result
        print(f"\n{label}\n  {result['recommendation']}: ${result['consider_amount']:,.0f}; "
              f"capacity ${result['financials']['investment_capacity']:,.0f}; "
              f"source {result['research']['latest_date']}")
    doc = kb.ingest_newer_nvda_report()
    print(f"\n3. RAG update indexed: {doc['title']} ({doc['date']})")
    for label, user, expense in [("4. After new report — User A", "user_a", 0),
                                 ("5. After new report — User B", "user_b", 0),
                                 ("6. Unexpected $5,000 expense — User A", "user_a", 5000)]:
        if expense:
            agent=CoordinatorAgent(kb=LocalKnowledgeBase(include_new_report=False))
        result = agent.analyze(user, unexpected_expense=expense)
        results[label] = result
        print(f"\n{label}\n  {result['recommendation']}: ${result['consider_amount']:,.0f}; "
              f"capacity ${result['financials']['investment_capacity']:,.0f}; "
              f"source {result['research']['latest_date']}")
    from pathlib import Path
    out=Path(__file__).parent/"outputs"/"demo_results.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nDetailed trace saved to {out}")

if __name__ == '__main__':main()
