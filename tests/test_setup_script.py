import os, subprocess, sys, textwrap

def test_setup_script_flow():
    code = textwrap.dedent('''
        import sys, httpx, runpy
        sys.argv = ["setup_throwaway.py"]
        def handler(req):
            p = req.url.path
            if p == "/user": return httpx.Response(200, json={"login": "me"})
            if p == "/user/repos": return httpx.Response(201, json={"html_url": "https://github.com/me/x"})
            if p == "/repos/me/autodev-triage-sandbox/issues":
                assert "Traceback" in req.content.decode()
                return httpx.Response(201, json={"html_url": "https://github.com/me/x/issues/1", "number": 1})
            return httpx.Response(404)
        _orig = httpx.Client
        httpx.Client = lambda **k: _orig(transport=httpx.MockTransport(handler), **k)
        runpy.run_path("scripts/setup_throwaway.py", run_name="__main__")
    ''')
    env = {**os.environ, "GITHUB_TOKEN": "fake", "PYTHONPATH": "scripts"}
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    assert "post_test.py --repo me/autodev-triage-sandbox --issue 1" in r.stdout
