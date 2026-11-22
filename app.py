"""Optional Streamlit dashboard: pip install -r requirements.txt; streamlit run app.py."""
import streamlit as st
from portfolio_agent import CoordinatorAgent
from portfolio_agent.retrieval import LocalKnowledgeBase

st.set_page_config(page_title="Portfolio Intelligence — Capstone",page_icon="📊",layout="wide")
st.title("Portfolio Intelligence Agent")
st.caption("CMU capstone prototype · 4 logical agents · local vector retrieval · public historical earnings + sample profiles")
if 'kb' not in st.session_state:
    st.session_state.kb = LocalKnowledgeBase(include_new_report=False)

with st.sidebar:
    st.header("Demo controls")
    user=st.selectbox("Investor profile",["user_a","user_b"],format_func=lambda x: "User A" if x=="user_a" else "User B")
    ticker=st.selectbox("Demo company",["NVDA","MSFT"])
    amount=st.number_input("Requested investment ($)",min_value=100,max_value=50000,value=2000,step=100)
    unexpected=st.number_input("Unexpected upcoming expense ($)",min_value=0,max_value=50000,value=0,step=500)
    st.divider()
    if st.button("Index newer NVDA report",type="primary",use_container_width=True):
        doc=st.session_state.kb.ingest_newer_nvda_report()
        st.success(f"Indexed {doc['id']} / {doc['date']}")
    if st.button("Reset knowledge base",use_container_width=True):
        st.session_state.kb=LocalKnowledgeBase(include_new_report=False)
        st.success("Reset to previous report")

agent=CoordinatorAgent(kb=st.session_state.kb)
result=agent.analyze(user,ticker,float(amount),float(unexpected))
c1,c2,c3=st.columns(3)
c1.metric("Decision",result['recommendation'])
c2.metric("Amount to consider",f"${result['consider_amount']:,.0f}")
c3.metric("Cash capacity (modeled)",f"${result['financials']['investment_capacity']:,.0f}")
st.info(result['explanation'])
st.markdown("### Tree of Thought — compared options")
st.dataframe(result['financials']['options'],use_container_width=True,hide_index=True)
left,right=st.columns([1.2,1])
with left:
    st.markdown("### RAG evidence")
    st.caption(f"Most recent indexed report: {result['research']['latest_date']} · Evidence tone: {result['research']['signal']}")
    for doc in result['research']['sources']:
        with st.expander(f"{doc['title']} — {doc['date']}",expanded=True):
            st.write(doc['excerpt'])
            st.caption("Public source • " + doc['source'])
with right:
    st.markdown("### Review and guardrails")
    st.write("Review passed:",result['review']['passed'])
    st.write("Human review recommended:",result['review']['human_review_required'])
    st.write("Issues:",result['review']['issues'] or "None")
    st.markdown("### Agent flow")
    st.code("Coordinator → Research + user data → Decision (3 branches → top 2) → Review → response",language=None)
st.warning(result['disclaimer'])
