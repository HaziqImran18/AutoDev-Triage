"""12 benchmark issues with known ground truth.
10 real-world bugs (root cause known) + 2 negative controls where the correct behaviour is to say
'not enough information' instead of inventing a cause.
type: "bug" | "insufficient_info". Keywords: 'a|b' means either word counts."""

ISSUES = [
{
"id": "keyerror-user", "type": "bug", "labels": ["bug"],
"title": "KeyError: 'user' in fetch_user for some user ids",
"body": """`fetch_user` works for id 1 but crashes for id 9999.

```python
def fetch_user(uid):
    resp = requests.get(f"https://api.example.com/users/{uid}", timeout=5)
    return resp.json()["user"]["name"]
```

```
Traceback (most recent call last):
  File "app.py", line 12, in <module>
    print(fetch_user(9999))
  File "app.py", line 6, in fetch_user
    return resp.json()["user"]["name"]
KeyError: 'user'
```
Environment: Python 3.11, requests 2.31.0""",
"root_cause": "The API returns an error JSON (e.g. 404 / no 'user' key) for a nonexistent user and the code indexes the response without checking the HTTP status or key existence.",
"fix": "Check resp.status_code / call raise_for_status() and use .get() or handle the missing key.",
"keywords": ["status|404|error response|error payload", "raise_for_status|.get(|check", "key"],
},
{
"id": "distutils-312", "type": "bug", "labels": ["bug"],
"title": "ModuleNotFoundError: No module named 'distutils' after upgrading to Python 3.12",
"body": """My install script worked on Python 3.10 but fails on 3.12.

```
Traceback (most recent call last):
  File "setup.py", line 1, in <module>
    from distutils.core import setup
ModuleNotFoundError: No module named 'distutils'
```
Environment: fresh venv, Python 3.12.1, Ubuntu 22.04""",
"root_cause": "The distutils module was removed from the standard library in Python 3.12 (PEP 632).",
"fix": "Install setuptools (which provides a distutils shim) or migrate setup.py to setuptools.",
"keywords": ["3.12", "removed|deprecated|PEP 632", "setuptools"],
},
{
"id": "numpy-float", "type": "bug", "labels": ["bug"],
"title": "AttributeError: module 'numpy' has no attribute 'float'",
"body": """Code that ran fine for a year now crashes after `pip install -U numpy`.

```
Traceback (most recent call last):
  File "metrics.py", line 18, in normalize
    arr = np.zeros(n, dtype=np.float)
  File "/venv/lib/python3.11/site-packages/numpy/__init__.py", line 305, in __getattr__
    raise AttributeError(__former_attrs__[attr])
AttributeError: module 'numpy' has no attribute 'float'.
`np.float` was a deprecated alias for the builtin `float`.
```
Environment: numpy 1.26.4 (was 1.21 before)""",
"root_cause": "np.float was a deprecated alias for the builtin float and was removed in NumPy 1.24.",
"fix": "Replace np.float with the builtin float or np.float64.",
"keywords": ["1.24", "removed|deprecated|alias", "float64|builtin"],
},
{
"id": "pydantic-basesettings", "type": "bug", "labels": ["bug"],
"title": "PydanticImportError: BaseSettings has been moved to the pydantic-settings package",
"body": """Upgraded dependencies and the app no longer starts.

```
Traceback (most recent call last):
  File "config.py", line 3, in <module>
    from pydantic import BaseSettings
  File "/venv/lib/python3.11/site-packages/pydantic/__init__.py", line 405, in __getattr__
    return _getattr_migration(attr_name)
pydantic.errors.PydanticImportError: `BaseSettings` has been moved to the `pydantic-settings` package.
```
Environment: pydantic 2.5.0, Python 3.11""",
"root_cause": "Pydantic v2 moved BaseSettings out of pydantic into the separate pydantic-settings package.",
"fix": "pip install pydantic-settings and import BaseSettings from pydantic_settings.",
"keywords": ["v2|version 2|2.0|2.5", "pydantic-settings|pydantic_settings", "install"],
},
{
"id": "flask-app-context", "type": "bug", "labels": ["bug"],
"title": "RuntimeError: Working outside of application context when running init_db.py",
"body": """Running my DB init script directly fails.

```python
db = SQLAlchemy(app)
db.create_all()
```

```
Traceback (most recent call last):
  File "init_db.py", line 9, in <module>
    db.create_all()
  File "/venv/lib/python3.11/site-packages/flask_sqlalchemy/extension.py", line 900, in create_all
    self._call_for_binds(bind_key, "create_all")
  File "/venv/lib/python3.11/site-packages/flask_sqlalchemy/extension.py", line 687, in engines
    app = current_app._get_current_object()
RuntimeError: Working outside of application context.
```
Environment: Flask 3.0, Flask-SQLAlchemy 3.1 (worked on 2.5)""",
"root_cause": "Flask-SQLAlchemy 3.x requires an active Flask application context for db.create_all().",
"fix": "Wrap the call in `with app.app_context():`.",
"keywords": ["app_context", "context", "3.0|3.1|version 3|3.x"],
},
{
"id": "asyncio-running-loop", "type": "bug", "labels": ["bug"],
"title": "RuntimeError: asyncio.run() cannot be called from a running event loop (JupyterLab)",
"body": """Works as a script, fails in a notebook cell.

```
Traceback (most recent call last):
  File "<ipython-input-4-8e1b2c>", line 6, in <module>
    results = asyncio.run(main())
  File "/usr/lib/python3.11/asyncio/runners.py", line 190, in run
    raise RuntimeError(
RuntimeError: asyncio.run() cannot be called from a running event loop
```
Environment: JupyterLab 4, Python 3.11""",
"root_cause": "Jupyter already runs an event loop, so asyncio.run() cannot start a nested one.",
"fix": "Use `await main()` at top level in the notebook, or apply nest_asyncio.",
"keywords": ["already running|running event loop|existing event loop", "await", "nest_asyncio|jupyter|ipython"],
},
{
"id": "node-fetch-esm", "type": "bug", "labels": ["bug"],
"title": "Error [ERR_REQUIRE_ESM]: require() of ES Module node-fetch not supported",
"body": """Server crashes on startup after I installed node-fetch.

```
Error [ERR_REQUIRE_ESM]: require() of ES Module /app/node_modules/node-fetch/src/index.js from /app/server.js not supported.
Instead change the require of index.js in /app/server.js to a dynamic import() which is available in all CommonJS modules.
    at Object.<anonymous> (/app/server.js:2:15)
    at Module._compile (node:internal/modules/cjs/loader:1256:14) {
  code: 'ERR_REQUIRE_ESM'
}
```
Environment: Node 18, node-fetch 3.3.2, CommonJS project""",
"root_cause": "node-fetch v3 is ESM-only and cannot be loaded with require() from a CommonJS module.",
"fix": "Use dynamic import(), convert the project to ESM, downgrade to node-fetch@2, or use Node 18's built-in fetch.",
"keywords": ["esm|es module", "node-fetch@2|dynamic import|built-in fetch|global fetch", "v3|version 3|3.x|3.3"],
},
{
"id": "openai-429-quota", "type": "bug", "labels": ["bug"],
"title": "openai.RateLimitError 429 even though I send only one request per minute",
"body": """I am nowhere near any rate limit but every call fails.

```
Traceback (most recent call last):
  File "chat.py", line 14, in ask
    resp = client.chat.completions.create(model="gpt-4o-mini", messages=msgs)
  File "/venv/lib/python3.11/site-packages/openai/_base_client.py", line 1010, in _request
    raise self._make_status_error_from_response(err.response) from None
openai.RateLimitError: Error code: 429 - {'error': {'message': 'You exceeded your current quota, please check your plan and billing details.', 'type': 'insufficient_quota', 'param': None, 'code': 'insufficient_quota'}}
```
Adding retries with backoff did not help.""",
"root_cause": "This 429 is insufficient_quota (no remaining credit / billing not set up), not request-rate throttling, so retrying cannot fix it.",
"fix": "Add credits or fix the billing/plan on the OpenAI account.",
"keywords": ["quota", "billing|credits|payment|plan", "429"],
},
{
"id": "sqlite-locked", "type": "bug", "labels": ["bug"],
"title": "sqlite3.OperationalError: database is locked with background workers",
"body": """Intermittent crash when 4 worker threads save results into the same SQLite file.

```
Traceback (most recent call last):
  File "worker.py", line 31, in save_result
    conn.execute("INSERT INTO results VALUES (?, ?)", (job_id, payload))
sqlite3.OperationalError: database is locked
```
Environment: Python 3.11, sqlite3 default settings, 4 threads""",
"root_cause": "SQLite allows only one writer at a time; concurrent writes from multiple threads lock the database and time out.",
"fix": "Serialize writes (single writer/queue), enable WAL mode, increase the connection timeout, or move to a client-server database.",
"keywords": ["concurrent|one writer|single writer|multiple writers|multiple threads", "WAL|timeout|queue|serialize"],
},
{
"id": "pandas-dup-index", "type": "bug", "labels": ["bug"],
"title": "ValueError: cannot reindex on an axis with duplicate labels in build_totals",
"body": """Crashes after I started loading one CSV per day.

```python
df = pd.concat([pd.read_csv(f) for f in daily_files])
df["total"] = df["qty"] * prices["price"]
```

```
Traceback (most recent call last):
  File "etl.py", line 22, in build_totals
    df["total"] = df["qty"] * prices["price"]
  File "/venv/lib/python3.11/site-packages/pandas/core/ops/common.py", line 76, in new_method
    return method(self, other)
ValueError: cannot reindex on an axis with duplicate labels
```
Environment: pandas 2.1, Python 3.11""",
"root_cause": "pd.concat without ignore_index kept each file's 0..n index, producing duplicate index labels; arithmetic aligns on index and fails with duplicates.",
"fix": "Use pd.concat(..., ignore_index=True) or reset_index(drop=True) before the operation.",
"keywords": ["duplicate", "concat", "reset_index|ignore_index"],
},
{
"id": "control-feature-retry", "type": "insufficient_info", "labels": ["enhancement"],
"title": "Add retry logic to fetch_user",
"body": """It would be nice if `fetch_user` retried up to 3 times on network failure before giving up.""",
"root_cause": "This is a feature request, not a bug. There is no error, so no root cause exists.",
"fix": "Nothing is broken; a correct report says it is a feature request / insufficient evidence of a defect.",
"keywords": [],
},
{
"id": "control-vague-slow", "type": "insufficient_info", "labels": ["question"],
"title": "App feels slow sometimes",
"body": """Sometimes the app is slow. Not sure when. Please fix.""",
"root_cause": "Not enough information to determine any cause (no error, environment, steps or measurements).",
"fix": "A correct report asks for details (logs, profiling, steps, environment) instead of guessing a cause.",
"keywords": [],
},
{
"id": "heldout-json-datetime", "type": "bug", "split": "heldout", "labels": ["bug"],
"title": "TypeError: Object of type datetime is not JSON serializable when returning an order",
"body": """The orders endpoint crashes since I added the created_at field.

```python
payload = {"id": order.id, "created": order.created_at}
return json.dumps(payload)
```

```
Traceback (most recent call last):
  File "api.py", line 27, in get_order
    return json.dumps(payload)
  File "/usr/lib/python3.11/json/__init__.py", line 231, in dumps
    return _default_encoder.encode(obj)
  File "/usr/lib/python3.11/json/encoder.py", line 180, in default
    raise TypeError(f'Object of type {o.__class__.__name__} '
TypeError: Object of type datetime is not JSON serializable
```
Environment: Python 3.11""",
"root_cause": "The json module cannot serialize datetime objects by default.",
"fix": "Convert the datetime to a string (isoformat), or pass default=str / a custom JSON encoder.",
"keywords": ["datetime", "serializ", "isoformat|default=|encoder|str"],
},
{
"id": "heldout-unicode-decode", "type": "bug", "split": "heldout", "labels": ["bug"],
"title": "UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff in position 0 reading export.csv",
"body": """The CSV was exported from Excel ("Unicode Text") and my loader fails immediately.

```
Traceback (most recent call last):
  File "load.py", line 5, in <module>
    rows = open("export.csv").read()
  File "/usr/lib/python3.11/codecs.py", line 322, in decode
    (result, consumed) = self._buffer_decode(data, self.errors, 'strict')
UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff in position 0: invalid start byte
```
Environment: Python 3.11, file created on Windows""",
"root_cause": "The file is not UTF-8: a leading 0xFF byte is a UTF-16 byte order mark (BOM), so the file is UTF-16 encoded.",
"fix": "Open the file with encoding='utf-16' (or detect the encoding) instead of the default UTF-8.",
"keywords": ["utf-16|utf16", "bom|byte order mark", "encoding"],
},
{
"id": "heldout-control-error-messages", "type": "insufficient_info", "split": "heldout", "labels": ["enhancement"],
"title": "Improve error messages in the CLI",
"body": """The CLI errors are hard to read for new users. It would help to add colours and a short hint on how to fix common mistakes.""",
"root_cause": "This is a feature request, not a bug. There is no failure, so no root cause exists.",
"fix": "Nothing is broken; a correct report says it is a feature request / insufficient evidence of a defect.",
"keywords": [],
},
{
"id": "heldout-control-safari", "type": "insufficient_info", "split": "heldout", "labels": ["question"],
"title": "Login button does nothing on Safari",
"body": """On Safari the login button doesn't respond when clicked. Chrome works fine. It started after last week's release.""",
"root_cause": "Not determinable: no console output, error text, browser version or reproduction steps are given.",
"fix": "A correct report asks for console errors, Safari version and steps instead of guessing a cause.",
"keywords": [],
},
{
"id": "heldout-connection-reset", "type": "insufficient_info", "split": "heldout", "labels": ["bug"],
"title": "ConnectionResetError: [Errno 104] Connection reset by peer on random requests",
"body": """About 1 in 200 requests to our partner API fails like this. The rest succeed.

```
Traceback (most recent call last):
  File "sync.py", line 41, in pull_orders
    data = session.get(url, timeout=10).json()
  File "/venv/lib/python3.11/site-packages/requests/sessions.py", line 602, in get
    return self.request("GET", url, **kwargs)
  File "/venv/lib/python3.11/site-packages/urllib3/connectionpool.py", line 793, in urlopen
    response = self._make_request(
ConnectionResetError: [Errno 104] Connection reset by peer
```
Environment: Python 3.11, requests 2.31, runs in a Kubernetes pod.""",
"root_cause": "Not determinable from the issue. A reset can come from the server, a proxy/load-balancer idle timeout, NAT/firewall or reused keep-alive connections; no logs, timings or pattern are given.",
"fix": "A correct report says the cause cannot be determined, lists possible causes only as hypotheses, and asks for server/proxy logs, timings and whether failures hit reused connections.",
"keywords": [],
},
]

ORIGINAL = [i for i in ISSUES if i.get("split", "original") == "original"]
HELDOUT = [i for i in ISSUES if i.get("split") == "heldout"]