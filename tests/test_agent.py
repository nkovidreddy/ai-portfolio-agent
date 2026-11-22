import pytest
from portfolio_agent import CoordinatorAgent
from portfolio_agent.retrieval import LocalKnowledgeBase


def test_personalization_users_same_evidence_different_outcomes():
    agent = CoordinatorAgent(kb=LocalKnowledgeBase(include_new_report=False))
    a = agent.analyze('user_a')
    b = agent.analyze('user_b')
    assert a['research']['latest_date'] == b['research']['latest_date']
    assert a['consider_amount'] == 2000
    assert b['consider_amount'] == 0
    assert b['financials']['investment_capacity'] == 0


def test_new_report_changes_research_and_recommendation():
    kb=LocalKnowledgeBase(include_new_report=False)
    agent=CoordinatorAgent(kb=kb)
    before=agent.analyze('user_a')
    kb.ingest_newer_nvda_report()
    after=agent.analyze('user_a')
    assert before['research']['latest_date']=='2022-05-25'
    assert after['research']['latest_date']=='2022-08-24'
    assert before['consider_amount'] == 2000
    assert after['consider_amount'] == 0
    assert after['research']['signal'] == 'negative'


def test_unexpected_expense_blocks_excess_allocation():
    agent=CoordinatorAgent(kb=LocalKnowledgeBase(include_new_report=False))
    a=agent.analyze('user_a',unexpected_expense=5000)
    assert a['financials']['investment_capacity']==1000
    assert a['consider_amount']<=1000


def test_invalid_amount_rejected():
    agent=CoordinatorAgent()
    with pytest.raises(ValueError):agent.analyze('user_a',requested_amount=-20)


def test_no_cross_user_profile_leakage():
    agent=CoordinatorAgent(kb=LocalKnowledgeBase(include_new_report=False))
    agent.analyze('user_a',unexpected_expense=3000)
    b=agent.analyze('user_b')
    assert b['financials']['investment_capacity']==0


def test_deduplicated_ingestion():
    kb=LocalKnowledgeBase(include_new_report=False)
    kb.ingest_newer_nvda_report()
    kb.ingest_newer_nvda_report()
    assert len([d for d in kb.documents if d['id']=='nvda-q2'])==1


def test_live_ai_adapter_can_only_tighten_policy(monkeypatch):
    from portfolio_agent import ai
    kb=LocalKnowledgeBase(include_new_report=False)
    monkeypatch.setattr(ai,'dense_retrieve',lambda kb,t,q,k:kb.retrieve(t,q,k))
    def model(sources,date):
        src=next(s for s in sources if s['id']=='nvda-q1')
        return ai.validate_analysis({'stance':'caution','observations':[{'source_id':src['id'],'quote':'16% below the prior year','interpretation':'EPS declined.'}]},sources)
    monkeypatch.setattr(ai,'analyze_evidence',model)
    result=CoordinatorAgent(kb=kb).analyze('user_a',use_ai=True)
    assert result['research']['baseline_signal']=='positive'
    assert result['consider_amount']==0
    assert result['review']['human_review_required']


def test_api_failure_fallback(monkeypatch):
    from portfolio_agent import ai
    def fail(*args):raise RuntimeError('offline')
    monkeypatch.setattr(ai,'dense_retrieve',fail)
    monkeypatch.setattr(ai,'analyze_evidence',fail)
    result=CoordinatorAgent(kb=LocalKnowledgeBase(include_new_report=False)).analyze('user_a',use_ai=True)
    assert result['consider_amount']==2000
    assert 'fallback' in result['research']['ai_status']
    assert 'fallback' in result['research']['retrieval_mode']


def test_invalid_quote_rejected():
    from portfolio_agent.ai import validate_analysis
    with pytest.raises(ValueError):
        validate_analysis({'stance':'support','observations':[{'source_id':'x','quote':'invented earnings number','interpretation':'invalid'}]},[{'id':'x','text':'Different text from source'}])


def test_nonfinite_inputs_rejected():
    agent=CoordinatorAgent()
    for amount in (float('nan'),float('inf')):
        with pytest.raises(ValueError):agent.analyze('user_a',requested_amount=amount)


def test_latest_report_included_and_source_links():
    result=CoordinatorAgent().analyze('user_a')
    assert any(d['id']=='nvda-q2' for d in result['research']['sources'])
    assert all(d['source'].startswith('https://') for d in result['research']['sources'])
