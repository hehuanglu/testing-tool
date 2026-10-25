"""Owned vulnerable/fixed technique controls; never product code."""
import html,json,sqlite3,os
from urllib.parse import urlsplit,unquote
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
class Control(BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def do_GET(self):
  path=urlsplit(self.path).path;owned=int(os.environ.get('ZPA_CONTROL_OBJECT_ID','42'))
  if path.startswith('/control/path/'):
   try:selector=int(unquote(path.removeprefix('/control/path/')));status=200 if selector==owned else 404;body={'id':owned,'name':'owned control object'} if status==200 else {'error':'not-found'}
   except ValueError:status=400;body={'error':'invalid-numeric-selector'}
  else:status=404;body={'error':'outside fixture'}
  data=json.dumps(body).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
 def do_POST(self):
  n=int(self.headers.get('Content-Length','0'));raw=self.rfile.read(min(n,16384));status=200
  try:value=json.loads(raw)['input']
  except Exception:value='invalid'
  db=sqlite3.connect(':memory:');db.executescript("CREATE TABLE users(name TEXT); INSERT INTO users VALUES ('marker');")
  try:
   if self.path=='/control/vulnerable':
    try:rows=db.execute("SELECT name FROM users WHERE name = '"+str(value)+"'").fetchall();body={'echo':str(value),'rows':rows}
    except sqlite3.Error as exc:status=500;body={'echo':str(value),'error':'SQLite error: '+str(exc)}
   elif self.path=='/control/fixed':
    rows=db.execute('SELECT name FROM users WHERE name = ?',(str(value),)).fetchall();body={'echo':html.escape(str(value),quote=True),'rows':rows}
   else:status=404;body={'error':'outside fixture'}
  finally:db.close()
  data=json.dumps(body).encode();self.send_response(status);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
if __name__=='__main__':ThreadingHTTPServer(('127.0.0.1',18080),Control).serve_forever()
