"""Example application hosting the same review components through the public library.

Usage: uv run python examples/embedded_review.py STORE EXPLORATION_ID
Starts an authenticated loopback server, prints a private URL, opens no browser.
Owns presentation only: Ctrl-C closes this host, not the exploration or its runner.
"""

import argparse
import hmac
import json
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files

from possibly import Possibly, PossiblyError

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Embedded Possibly review</title>
<style>body{font:16px/1.5 system-ui;margin:0;background:#f5f3eb;color:#24322d}
header{padding:20px 4vw;background:#20394a;color:white}header h1{margin:0;font-size:22px}
main{max-width:1500px;margin:auto;padding:24px 4vw}#notice,#saved{padding:8px 4vw;display:block}
:root{--bg:#f5f3eb;--panel:#fffef9;--text:#24322d;--muted:#5b685d;--line:#d7dcd0;--accent:#294f3d;--on-accent:#fff;--soft:#e9eee3}
</style></head><body><header><h1>Application design review</h1><p>A host-owned application surface, powered by Possibly.</p></header>
<div id="notice" role="status"></div><small id="saved" aria-live="polite"></small><main id="review"></main>
<script type="module">
import {mountReview} from '/review.js';
const key='embedded-token-'+location.host,token=location.hash.slice(1)||sessionStorage.getItem(key)||'';
sessionStorage.setItem(key,token);history.replaceState(null,'',location.pathname);
async function api(path,data){const response=await fetch(path,{method:'POST',headers:{'Authorization':'Bearer '+token,'Content-Type':'application/json'},body:JSON.stringify(data)});
 const result=await response.json();if(!response.ok)throw Error(result.error?.message||'Host request failed');return result}
const reviewerId=sessionStorage.getItem('embedded-reviewer')||crypto.randomUUID();sessionStorage.setItem('embedded-reviewer',reviewerId);
const review=mountReview(document.querySelector('#review'),{
 reviewerId,loadSurface:view=>api('/surface',{view,reviewer_id:reviewerId}),sendAction:data=>api('/action',data),
 loadArtifact:revision_id=>api('/artifact',{revision_id}),loadThumbnail:revision_id=>api('/thumbnail',{revision_id}),
 onNotice:text=>document.querySelector('#notice').textContent=text,onSaveStatus:text=>document.querySelector('#saved').textContent=text
});
window.addEventListener('pagehide',()=>review.dispose());
</script></body></html>"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("store")
    parser.add_argument("exploration_id")
    args = parser.parse_args()
    p = Possibly(args.store, caller="example-host")
    eid = args.exploration_id
    p.get_exploration(eid)  # Validate before starting a service.
    token = secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def send(self, value, status=200, content_type="application/json"):
            body = (value if isinstance(value, str) else json.dumps(value)).encode()
            self.send_response(status)
            for key, value in {
                "Content-Type": content_type,
                "Content-Length": str(len(body)),
                "Cache-Control": "no-store",
                "Referrer-Policy": "no-referrer",
                "X-Content-Type-Options": "nosniff",
            }.items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/":
                return self.send(PAGE, content_type="text/html")
            if self.path == "/review.js":
                return self.send(
                    files("possibly").joinpath("static/review.js").read_text(), content_type="text/javascript"
                )
            return self.send({"error": {"message": "Not found"}}, 404)

        def do_POST(self):
            if not hmac.compare_digest(self.headers.get("Authorization", ""), "Bearer " + token):
                return self.send({"error": {"message": "Unauthorized"}}, 401)
            if self.headers.get("Origin") not in {None, f"http://127.0.0.1:{self.server.server_port}"}:
                return self.send({"error": {"message": "Invalid origin"}}, 403)
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size < 100_000:
                    raise ValueError("Invalid body")
                data = json.loads(self.rfile.read(size))
                if self.path == "/surface":
                    result = p.review_surface(eid, **data)
                elif self.path == "/action":
                    result = p.review_action(eid, **data)
                elif self.path == "/artifact":
                    result = {"html": p.read_artifact(eid, data["revision_id"])}
                elif self.path == "/thumbnail":
                    result = {"thumbnail": p.get_revision(eid, data["revision_id"]).get("thumbnail")}
                else:
                    return self.send({"error": {"message": "Not found"}}, 404)
                self.send(result)
            except PossiblyError as exc:
                self.send(exc.to_dict(), 409)
            except (ValueError, KeyError, TypeError):
                self.send({"error": {"message": "Invalid request"}}, 400)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    print(f"Private review URL: http://127.0.0.1:{server.server_port}/#{token}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
