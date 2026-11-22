"""No extra web framework required: python web_demo.py

Local educational demo only. Binds 127.0.0.1; not intended for public hosting.
"""
from __future__ import annotations
import json, os, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from portfolio_agent import CoordinatorAgent
from portfolio_agent.retrieval import LocalKnowledgeBase

ROOT=Path(__file__).resolve().parent
LOCK=threading.RLock()
STATE={"kb": LocalKnowledgeBase(include_new_report=False)}

class Handler(BaseHTTPRequestHandler):
    def json(self, payload, status=200):
        body=json.dumps(payload).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Cache-Control','no-store')
        self.send_header('Content-Length',str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed=urlparse(self.path)
        if parsed.path in ('/','/index.html'):
            body=(ROOT/'assets'/'index.html').read_bytes()
            self.send_response(200)
            self.send_header('Content-Type','text/html; charset=utf-8')
            self.send_header('Cache-Control','no-store')
            self.send_header('Content-Length',str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path=='/api/health':
            return self.json({'status':'ok','demo_only':True})
        if parsed.path=='/api/analysis':
            try:
                q=parse_qs(parsed.query)
                arg=lambda k,d:q.get(k,[d])[0]
                with LOCK: kb=STATE['kb']
                result=CoordinatorAgent(kb=kb).analyze(
                    user_id=arg('user','user_a'), ticker=arg('ticker','NVDA'),
                    requested_amount=float(arg('amount',2000)), unexpected_expense=float(arg('expense',0)), use_ai=arg('mode','offline')=='ai')
                return self.json(result)
            except (ValueError,TypeError,OverflowError) as exc:
                return self.json({'error':str(exc)},400)
        return self.json({'error':'Not found'},404)

    def do_POST(self):
        if self.path=='/api/index-latest':
            with LOCK:
                kb=LocalKnowledgeBase(include_new_report=False)
                d=kb.ingest_newer_nvda_report()
                STATE['kb']=kb
            return self.json({'ok':True,'indexed_id':d['id'],'date':d['date']})
        if self.path=='/api/reset':
            with LOCK: STATE['kb']=LocalKnowledgeBase(include_new_report=False)
            return self.json({'ok':True,'status':'reset to Q1'})
        return self.json({'error':'Not found'},404)

    def log_message(self,format,*args):
        if not self.path.startswith('/api/health'):
            super().log_message(format,*args)

if __name__=='__main__':
    addr=('127.0.0.1',8765)
    print(f'\nLocal Portfolio Agent demo: http://{addr[0]}:{addr[1]}\nPress Ctrl+C to stop.\n')
    ThreadingHTTPServer(addr,Handler).serve_forever()
