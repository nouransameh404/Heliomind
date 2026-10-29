"""Run actual service processes and exercise UI JavaScript against them.
The temporary HTTP proxy below substitutes only for nginx in this test.
Install JS dependency separately: npm install --no-save jsdom@26.1.0
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

ROOT=Path(__file__).resolve().parents[1]
PORTS={'forecast':18101,'anomaly':18102,'sizing':18103,'gateway':18104}
class Proxy(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def handle_request(self):
        if self.path.startswith('/api/'):
            path='http://127.0.0.1:18104/'+self.path[5:]
            body=self.rfile.read(int(self.headers.get('Content-Length',0))) if self.command=='POST' else None
            req=urllib.request.Request(path,data=body,headers={'Content-Type':'application/json'},method=self.command)
            try:response=urllib.request.urlopen(req,timeout=40)
            except urllib.error.HTTPError as exc: response=exc
            with response:
                content=response.read();self.send_response(response.status)
                self.send_header('Content-Type',response.headers.get('Content-Type','application/json'))
                self.end_headers();self.wfile.write(content)
        else:
            path=(ROOT/'web'/self.path.split('?')[0].lstrip('/')).resolve()
            if self.path=='/':path=ROOT/'web/index.html'
            if not path.is_relative_to((ROOT/'web').resolve()) or not path.is_file():
                self.send_error(404);return
            content=path.read_bytes()
            mime={'.html':'text/html','.js':'text/javascript','.css':'text/css','.json':'application/json'}.get(path.suffix,'application/octet-stream')
            self.send_response(200);self.send_header('Content-Type',mime);self.end_headers();self.wfile.write(content)
    do_GET=handle_request
    do_POST=handle_request

def wait(port):
    deadline=time.monotonic()+40
    while time.monotonic()<deadline:
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/health',timeout=1) as response:
                if response.status==200:return
        except Exception:time.sleep(.2)
    raise RuntimeError(f'Service on {port} did not start')

if __name__=='__main__':
    processes=[];logs=[];server=None
    try:
        for name,port in PORTS.items():
            env=dict(os.environ,OMP_NUM_THREADS='1')
            if name=='gateway':
                env.update({key.upper()+'_URL':f'http://127.0.0.1:{value}' for key,value in PORTS.items() if key!='gateway'})
            log=tempfile.TemporaryFile(mode='w+');logs.append(log)
            processes.append(subprocess.Popen([sys.executable,'-m','uvicorn',name+'.main:app','--host','127.0.0.1','--port',str(port)],cwd=ROOT,env=env,stdout=log,stderr=log))
        for port in PORTS.values():wait(port)
        with urllib.request.urlopen('http://127.0.0.1:18104/services') as response:
            assert json.load(response)=={'forecast':'ok','anomaly':'ok','sizing':'ok'}
        server=ThreadingHTTPServer(('127.0.0.1',18100),Proxy)
        Thread(target=server.serve_forever,daemon=True).start()
        subprocess.run(['node',str(ROOT/'tests/browser_flow.cjs')],env=dict(os.environ,HELIOMIND_TEST_URL='http://127.0.0.1:18100'),check=True)
        print('PASS: four independent service processes, gateway HTTP routing and full DOM interactions.')
    finally:
        if server:server.shutdown();server.server_close()
        for process in processes:process.terminate()
        for process in processes:
            try:process.wait(timeout=10)
            except subprocess.TimeoutExpired:process.kill();process.wait()
        for log in logs:
            if any(process.returncode not in (0,-15) for process in processes):
                log.seek(0);print(log.read()[-2500:])
            log.close()
