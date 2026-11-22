"""Four logical agents and deterministic risk controls.

No brokerage integration, payments, bank integration, or autonomous execution.
Investor profiles are sample data; company evidence is historical public information. The agent recommends further research, not trades.
"""
from __future__ import annotations
import copy, json, re, math, time
from . import ai
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from .retrieval import LocalKnowledgeBase, ROOT

@dataclass
class Candidate:
    label: str
    amount: float
    score: int
    feasible: bool
    rationale: str

class ResearchAgent:
    """Retrieves company evidence and derives a simple, inspectable financial signal.

    This is deliberately rule-based for the offline demo. A production research
    agent would validate structured facts extracted from filings with tools.
    """
    def __init__(self, kb: LocalKnowledgeBase): self.kb = kb

    @staticmethod
    def financial_signal(text: str) -> tuple[str, dict]:
        growth = re.search(r"revenue growth of\s*(\d+(?:\.\d+)?)%", text, re.I)
        guidance = re.search(r"(?:guidance to|projected)\s*(\d+(?:\.\d+)?)%", text, re.I)
        revenue_pct = float(growth.group(1)) if growth else None
        guidance_pct = float(guidance.group(1)) if guidance else None
        weakening = bool(re.search(r"reduced|weakened|slowing|slowdown", text, re.I))
        if weakening and (revenue_pct is None or revenue_pct < 12):
            signal='negative'
        elif revenue_pct is not None and revenue_pct >= 15 and not weakening:
            signal='positive'
        else:
            signal='neutral'
        return signal, {'revenue_growth_pct':revenue_pct,'forward_guidance_pct':guidance_pct,
                        'weakening_language':weakening}

    def run(self, ticker: str, user_question: str, use_ai=False) -> dict:
        latest = self.kb.latest_report(ticker)
        if not latest: return {"status":"missing", "sources":[], "latest":None, "signal":"unknown", "metrics":{}}
        query = user_question + " growth earnings revenue guidance management risk"
        mode = 'TF-IDF (offline)'
        ai_status = 'Not requested'
        ai_result = None
        if use_ai:
            try:
                retrieved = ai.dense_retrieve(self.kb, ticker, query, 3)
                mode = 'OpenAI dense semantic embeddings'
            except Exception:
                retrieved = self.kb.retrieve(ticker, query, 3)
                mode = 'TF-IDF (embedding API fallback)'
        else:
            retrieved = self.kb.retrieve(ticker, query, 3)
        # Latest indexed report is mandatory context even if lexical similarity is low.
        if latest["id"] not in {d["id"] for d in retrieved}:
            retrieved = [latest] + retrieved[:2]
        signal,metrics=self.financial_signal(latest['text'])
        baseline = signal
        if use_ai:
            try:
                ai_result = ai.analyze_evidence(retrieved, latest['date'])
                ai_status = 'Live model response; cited quotations checked'
                # LLM can only make the baseline more conservative, never relax policy.
                if ai_result['stance'] == 'caution' and signal == 'positive': signal = 'negative'
            except Exception:
                ai_status = 'LLM unavailable or evidence validation failed; deterministic fallback'
        return {"status":"ok", "sources":retrieved, "latest":latest, "signal":signal, "metrics":metrics,
                "baseline_signal":baseline,"retrieval_mode":mode,"ai_status":ai_status,"ai_analysis":ai_result}

class DecisionAgent:
    def run(self, profile: dict, research: dict, ticker: str, amount: float, unexpected_expense: float = 0) -> dict:
        cash = float(profile["cash_balance"])
        reserve = float(profile["emergency_reserve"])
        expenses = float(profile["upcoming_essential_expenses"])
        debts = float(profile["upcoming_debt_payments"])
        capacity = max(0., cash-reserve-expenses-debts-max(0., unexpected_expense))
        portfolio = sum(float(v) for v in profile["holdings"].values())
        existing = float(profile["holdings"].get(ticker, 0))
        limit = float(profile["max_position_fraction"])
        signal = research["signal"]
        # Bounded Tree of Thought: generate 3 branches, score, and retain top 2.
        options = [("Requested amount", amount), ("Smaller amount", round(amount/2, 2)), ("Wait / review", 0.)]
        candidates = []
        for label, x in options:
            concentration = (existing+x)/(portfolio+x) if portfolio+x else 0.
            feasible = x <= capacity and concentration <= limit + 1e-9
            if profile["risk_tolerance"] == "low" and x > 0 and signal != "positive": feasible = False
            if profile["investment_horizon"] == "short" and x > 0: feasible = False
            if signal in ("negative", "unknown") and x > 0: feasible = False
            # Scores encode policy trade-offs, not a prediction of stock returns.
            score = (70 if x == 0 else 80 if x == amount else 72)
            if signal == "positive" and x > 0: score += 10
            if signal == "negative" and x == 0: score += 25
            if x == 0 and signal == "positive" and capacity >= amount: score -= 20
            if not feasible: score = 0
            if x == 0: feasible = True
            notes = []
            if x > capacity: notes.append("cash would fall below expenses / emergency reserve")
            if concentration > limit and x > 0: notes.append("position concentration limit exceeded")
            if signal == "negative" and x > 0: notes.append("newer earnings evidence indicates declining outlook")
            if signal == "unknown" and x > 0: notes.append("no verified company report")
            if profile["investment_horizon"] == "short" and x > 0: notes.append("short investment horizon")
            if profile["risk_tolerance"] == "low" and x > 0 and signal != "positive": notes.append("low risk tolerance")
            candidates.append(Candidate(label, x, min(100, score), feasible, "; ".join(notes) or "passes modeled conditions"))
        finalists = sorted(candidates, key=lambda c: c.score, reverse=True)[:2]
        selected = finalists[0]
        return {"investment_capacity":capacity, "current_position_value":existing,
                "current_portfolio_value":portfolio,"options":[asdict(c) for c in candidates],
                "finalists":[asdict(c) for c in finalists], "selected":asdict(selected),
                "signal":signal, "unexpected_expense":unexpected_expense, "requested_amount":amount}

class ReviewAgent:
    def run(self, profile: dict, research: dict, decision: dict, ticker: str) -> dict:
        reasons = []
        if research["status"] != "ok": reasons.append("Missing company research")
        if decision["selected"]["amount"] > decision["investment_capacity"]:
            reasons.append("Investment capacity check failed")
        x = decision["selected"]["amount"]
        holdings = decision["current_portfolio_value"]
        pos = decision["current_position_value"]
        if (holdings+x)>0 and (pos+x)/(holdings+x)>float(profile["max_position_fraction"])+1e-9:
            reasons.append("Concentration limit check failed")
        if research["signal"] == "negative" and x>0: reasons.append("Negative latest filing")
        if profile["investment_horizon"] == "short" and x>0: reasons.append("Short horizon")
        if not research["sources"]: reasons.append("No source evidence")
        if reasons:
            decision["selected"] = {"label":"Wait / review","amount":0.0,"score":0,"feasible":True,
                                    "rationale":"Review blocked an unsupported allocation"}
        return {"passed":not reasons,"issues":reasons,"human_review_required":bool(reasons) or research["signal"] != "positive" or decision["investment_capacity"] < decision["requested_amount"]}

class CoordinatorAgent:
    def __init__(self, users_path: Path | None = None, kb: LocalKnowledgeBase | None = None):
        self.users = json.loads((users_path or ROOT/"data"/"users.json").read_text(encoding="utf-8"))
        self.kb = kb or LocalKnowledgeBase()
        self.research = ResearchAgent(self.kb)
        self.decision = DecisionAgent()
        self.review = ReviewAgent()

    def analyze(self, user_id: str, ticker: str = "NVDA", requested_amount: float = 2000,
                unexpected_expense: float = 0, use_ai: bool = False) -> dict[str, Any]:
        started=time.perf_counter()
        if user_id not in self.users: raise ValueError("Unknown sample investor profile")
        if not math.isfinite(requested_amount) or requested_amount <= 0 or requested_amount > 1000000: raise ValueError("Amount must be > 0 and <= $1,000,000")
        if not math.isfinite(unexpected_expense) or unexpected_expense < 0: raise ValueError("Unexpected expense must be non-negative")
        ticker = ticker.strip().upper()
        if ticker not in {d["ticker"] for d in self.kb.documents}:
            raise ValueError("Ticker not indexed in this offline demo")
        profile = copy.deepcopy(self.users[user_id])
        question = f"Analyze {ticker} historical company performance, revenue, earnings and risks."
        finding = self.research.run(ticker, question, use_ai=use_ai)
        result = self.decision.run(profile, finding, ticker, requested_amount, unexpected_expense)
        review = self.review.run(profile, finding, result, ticker)
        if use_ai and finding.get("ai_analysis") is None:
            review["human_review_required"] = True
            review["issues"].append("Live AI unavailable; offline historical result requires review")
        selected = result["selected"]
        recommendation = ("WAIT / REVIEW" if selected["amount"] == 0 else "CONSIDER FOR FURTHER REVIEW")
        latest = finding["latest"]
        evidence = [] if not latest else [{"title":d["title"],"date":d["date"],"id":d["id"],
                 "source":d["source"],"excerpt":d["text"],"retrieval_score":d.get("retrieval_score")} for d in finding["sources"]]
        explanation = (
            f"{profile['display_name']}: modeled investment capacity is ${result['investment_capacity']:,.0f} "
            f"after reserves, upcoming expenses, debt and any unexpected expense. "
            f"The latest indexed {ticker} report ({latest['date'] if latest else 'missing'}) "
            f"produces a {finding['signal']} historical research signal. "
            f"Decision: {recommendation.lower()}, with ${selected['amount']:,.0f} for further consideration. "
            f"{selected['rationale'].capitalize()}. The user must make the final decision."
        )
        return {"user_id":user_id,"user_name":profile["display_name"],"ticker":ticker,
                "requested_amount":requested_amount,"recommendation":recommendation,
                "consider_amount":selected["amount"],"financials":result,
                "research":{"signal":finding["signal"],"latest_date":latest["date"] if latest else None,
                            "sources":evidence,"derived_metrics":finding["metrics"],"baseline_signal":finding.get("baseline_signal"),"retrieval_mode":finding.get("retrieval_mode"),"ai_status":finding.get("ai_status"),"ai_analysis":finding.get("ai_analysis")}, "review":review,"explanation":explanation,
                "elapsed_ms":round((time.perf_counter()-started)*1000),"disclaimer":"Historical replay using public earnings summaries and sample investor profiles. Not current market analysis, financial advice or an instruction to trade."}
