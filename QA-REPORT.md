# QA Report — CypherPulse — 2026-03-18

## Summary

| Metric | Count |
|--------|-------|
| **Total findings** | 66 |
| Critical | 2 |
| High | 19 |
| Medium | 29 |
| Low | 16 |
| **Auto-fixed** | 15 issues in 3 commits |
| **For review** | 47 issues |

---

## Auto-Fixed Issues ✅

The following issues were automatically fixed and committed:

- **[Critical]** `scripts/analyze_public_account.py` — Fixed bare except: clause to except ValueError: — prevents swallowing KeyboardInterrupt/SystemExit
- **[High]** `cypherpulse/collector.py` — Fixed connection leak in scan_tweets() — replaced manual conn.close() with get_db_context() context manager
- **[High]** `cypherpulse/collector.py` — Fixed connection leak in collect_snapshots() — replaced manual conn.close() with get_db_context() context manager
- **[High]** `scripts/benchmark_words.py` — Fixed connection leak — wrapped sqlite3 query in try/finally to guarantee conn.close()
- **[High]** `web/index.html` — Fixed XSS in renderPerformanceTable — replaced innerHTML template literal with DOM createElement/textContent for post_type
- **[High]** `web/index.html` — Fixed XSS in decay legend — replaced innerHTML with DOM nodes for post_type
- **[High]** `web/index.html` — Fixed XSS in bar chart render — applied escapeHtml() to axisLabel and post_type t in innerHTML/title attributes
- **[High]** `web/index.html` — Fixed XSS in renderTrendsChart — applied escapeHtml() to type and date in SVG innerHTML
- **[High]** `web/index.html` — Added escapeHtml() utility function for safe HTML encoding of API-returned values
- **[High]** `web/index.html` — Added tablet breakpoint @media (max-width: 768px) for better medium-screen layout
- **[High]** `install.sh` — Fixed sed injection: replaced sed substitution with python3 env-file writer + API key character validation
- **[High]** `install.sh` — Added curl|bash truncation sentinel (_INSTALL_STARTED and INSTALL_COMPLETE markers)
- **[High]** `install.ps1` — Added SHA256 hash verification for Python installer EXE download
- **[High]** `install.ps1` — Added $LASTEXITCODE checks after git clone and git pull
- **[High]** `install.ps1` — Added $LASTEXITCODE checks after pip install --upgrade pip, install -r requirements.txt, install -e .

---

## ⚠️ Critical Issues [ACTION REQUIRED]

### [QUALITY] `cypherpulse/db.py + cypherpulse/api.py:467`

**Issue:** Entire tokenization and PMI/IDF scoring pipeline is copy-pasted between get_word_bubbles() (db.py:467-720) and _score_tweets() (api.py:390-580). Both functions share identical logic for STOPWORDS, text cleaning, ordered_tokens extraction, unigram/bigram/trigram accumulation, and _build_word/bigram/trigram_results() inner functions. Any bug fix or improvement must be applied in two places.

**Fix:** Extract a shared tokenizer module (e.g., cypherpulse/tokenizer.py) with: STOPWORDS constant, tokenize_tweet() function, and build_ngram_scores() function. Both get_word_bubbles() and _score_tweets() call this shared module.

---

## ⚠️ High Priority Issues [ACTION REQUIRED]

### [QUALITY] `cypherpulse/db.py:467`

**Issue:** get_word_bubbles() is 253 lines long with nesting depth of 10. The function handles DB querying, text preprocessing, stopword filtering, hashtag extraction, URL stripping, unigram/bigram/trigram accumulation, PMI calculation, IDF weighting, confidence scoring, and result filtering — all in one body. Contains 3 large inner functions that together are longer than many entire modules.

**Fix:** Split into: tokenize_tweet(text) -> tokens, accumulate_ngrams(rows) -> (word_data, bigram_data, trigram_data, unigram_for_pmi), and scoring helpers. get_word_bubbles() becomes an orchestrator of 3-4 focused helpers, each < 50 lines.

---

### [QUALITY] `cypherpulse/api.py:292`

**Issue:** fetch_handle_tweets() (98 lines) has convoluted, self-contradicting logic. The docstring claims it walks cursors then fires pages in parallel, but the implementation actually fetches tweet payloads sequentially while walking. The final parallel-fire block (lines 360-369) filters out already-consumed cursors, making it dead code in all normal cases. The variable  accumulates cursor strings but the corresponding tweets are fetched during the walk loop — creating a disconnect between cursors collected and pages actually remaining.

**Fix:** Simplify to a straightforward sequential pagination loop (the cursor chain API requires sequential traversal anyway). Remove the misleading parallel-fire dead code path. If true parallelism is needed, architect clearly: pre-collect all cursors in one pass then fire, but acknowledge you cannot get cursors without fetching pages.

---

## 🔶 Medium Priority Issues [FOR REVIEW]

**[SECURITY]** `cypherpulse/api.py:258`

- **Issue:** Hardcoded absolute server path to secrets file exposed as default: `_TWITTERAPI_SECRET_PATH = Path(os.getenv('TWITTERAPI_SECRET_PATH', '/root/.openclaw/secrets/twitterapi-io.json'))`. This path is server-specific and leaks internal server structure if error messages are exposed. The path is logged in error messages on key load failure.
- **Suggestion:** Remove the hardcoded fallback path or make it configurable without a default that reveals server layout. At minimum, ensure error messages don't expose the path to API consumers.

**[SECURITY]** `scripts/benchmark_external.py:55`

- **Issue:** Hardcoded absolute path to secrets file: `Path('/root/.openclaw/secrets/twitterapi-io.json')`. This is a server-specific path embedded in a script distributed as part of the project. If this script is shared/open-sourced, it reveals server directory structure.
- **Suggestion:** Use environment variable lookup first: `os.getenv('TWITTERAPI_IO_KEY')` or a relative path / configurable path. Follow the pattern used in `api.py` with `TWITTERAPI_SECRET_PATH` env var.

**[SECURITY]** `scripts/analyze_public_account.py:111`

- **Issue:** Hardcoded absolute path to secrets file: `Path('/root/.openclaw/secrets/twitterapi-io.json')`. Same issue as benchmark_external.py — server-specific path in a distributable script.
- **Suggestion:** Prefer environment variable (`TWITTERAPI_IO_KEY` or `TWITTER_API_KEY`) as primary, with the secrets file as a documented optional fallback using a configurable path.

**[SECURITY]** `cypherpulse/api.py:621`

- **Issue:** Unbounded POST body on `/api/benchmark/rescore`: accepts `List[Dict[str, Any]]` with no size limit. A client could send tens of thousands of large tweet objects, causing CPU exhaustion during tokenization and scoring (O(n) text processing per tweet). No rate limiting or payload size cap exists.
- **Suggestion:** Add a maximum payload size limit (e.g. 5000 tweets), and consider adding rate limiting middleware (e.g. `slowapi`) to benchmark endpoints. FastAPI's default body size limit is 1MB but should be explicitly set.

**[SECURITY]** `cypherpulse/api.py:57`

- **Issue:** CORS allows credentials (`allow_credentials=True`) with configurable origins from environment. If `ALLOWED_ORIGINS` is misconfigured to include `*` or overly broad domains, combined with `allow_credentials=True`, it could allow cross-site requests to read API data. FastAPI/Starlette should reject `*` with credentials, but the combination is a footgun.
- **Suggestion:** Document that `ALLOWED_ORIGINS=*` is incompatible with `allow_credentials=True`. Consider defaulting to `allow_credentials=False` since the API uses no authentication and session cookies are irrelevant.

**[QUALITY]** `cypherpulse/db.py:498`

- **Issue:** STOPWORDS set is defined inside get_word_bubbles() function body (lines 498-519) as a local variable, reconstructed on every call. The same set exists at module level in api.py as _STOPWORDS. Neither is shared. Defining a large set constant inside a function is inefficient and obscures the fact that this is shared/reusable configuration.
- **Suggestion:** Define STOPWORDS once as a module-level constant in a shared location (e.g., tokenizer.py or at top of db.py). Import in api.py instead of redefining it.

**[QUALITY]** `cypherpulse/db.py:495`

- **Issue:**  and  are placed inside the get_word_bubbles() function body instead of at module level. This defers import resolution to call time and obscures dependencies. Python caches imports so there is no correctness issue, but it misleads readers about module dependencies and violates PEP 8 (imports should be at top of file).
- **Suggestion:** Move  and  to the top of db.py alongside the other imports.

**[QUALITY]** `cypherpulse/db.py + cypherpulse/api.py + cypherpulse/collector.py:11`

- **Issue:** logging.basicConfig(level=logging.INFO) is called at module level in three separate library modules (db.py:11, api.py:52, collector.py:12). Library code should never call basicConfig() — it configures the root logger globally and can interfere with the application's (or user's) logging setup. This is a well-known Python antipattern.
- **Suggestion:** Remove all basicConfig() calls from library modules. Add a NullHandler: . Let the application entry point (cli.py or the user) configure logging.

**[QUALITY]** `cypherpulse/api.py:390`

- **Issue:** _score_tweets() is 190 lines long and contains the same three inner function definitions (_build_word_results, _build_bigram_results, _build_trigram_results) as get_word_bubbles() in db.py. This is a god function that is also a copy-paste duplicate. It handles engagement proxy computation, tokenization, accumulation, PMI/IDF scoring, and result building for all three ngram modes.
- **Suggestion:** After extracting shared tokenizer module (see Critical finding), _score_tweets() should reduce to ~30 lines: build engagement map, call tokenize_tweets(), call build_ngram_scores() with engagement proxy, return filtered results.

**[QUALITY]** `cypherpulse/collector.py:234`

- **Issue:** Magic number 280 used for text[:280] tweet truncation (collector.py:234) and magic number 500 used in LIMIT 500 query (collector.py:337). These constants have no names. 280 is the Twitter character limit; 500 is an arbitrary scan batch size. Both should be named constants.
- **Suggestion:** Define TWEET_MAX_CHARS = 280 and COLLECT_TWEET_LIMIT = 500 at module level with comments explaining their purpose.

**[PYTHON]** `cypherpulse/db.py:495`

- **Issue:** 'import re' and 'import math' placed inside the get_word_bubbles() function body, violating PEP 8 (E402). These are standard library modules with no circular import risk.
- **Suggestion:** Move both imports to the top of db.py with the other stdlib imports.

**[PYTHON]** `cypherpulse/api.py:304`

- **Issue:** 'import asyncio as _asyncio' inside the fetch_handle_tweets() function body. PEP 8 requires imports at module top level. The underscore prefix (private convention) suggests an attempt to hide a module-level import, but the correct approach is a top-level import.
- **Suggestion:** Move 'import asyncio' to the top of api.py. The _asyncio alias is unnecessary; use 'import asyncio' and reference it as asyncio throughout.

**[PYTHON]** `cypherpulse/db.py:66`

- **Issue:** Path comparison uses string startswith() instead of the idiomatic Path.is_relative_to() (Python 3.9+). The pattern 'str(path).startswith(str(home))' is fragile — a path like /root2/foo would incorrectly pass if home is /root.
- **Suggestion:** Use 'path.is_relative_to(home) or path.is_relative_to(cwd)' for correct path containment checks. Since project requires Python >=3.8, guard with a version check or use 'try: path.relative_to(home)' pattern for 3.8 compat.

**[PYTHON]** `scripts/analyze_public_account.py:15`

- **Issue:** Functions fetch_tweets(), analyze(), and print_report() are missing type hints in their signatures. The main codebase (collector.py, db.py, cli.py, api.py) uses type hints consistently throughout.
- **Suggestion:** Add return type annotations: fetch_tweets() -> list[dict], analyze() -> dict, print_report() -> None. Also add the return type to main() -> None.

**[FRONTEND]** `web/index.html:647`

- **Issue:** Accessibility: The benchmark handle input (#benchmarkHandle) has no aria-label or associated <label> element. The '@' span before it is a visual hint only, not programmatically linked.
- **Suggestion:** Add aria-label='Twitter handle for benchmark comparison' to the input element, or wrap with a proper <label> element.

**[FRONTEND]** `web/index.html:533`

- **Issue:** Accessibility: Info icon tooltips use click-toggle (onclick="this.classList.toggle('open')") which is not keyboard-accessible. Screen reader users and keyboard-only users cannot access the tooltip content.
- **Suggestion:** Add tabindex='0' to .info-icon elements, handle both click and keydown (Enter/Space) events, and use aria-expanded + aria-describedby pattern to properly expose tooltip content.

**[FRONTEND]** `web/index.html:764`

- **Issue:** UX/Accessibility: Using alert() for form validation feedback ('Please select both dates', 'From date must be before To date'). alert() blocks the browser, is inaccessible to screen readers in context, and is jarring UX.
- **Suggestion:** Replace alert() calls with inline error messages using aria-live regions. Display error text near the date inputs so screen readers announce it automatically.

**[FRONTEND]** `web/index.html:920`

- **Issue:** UX/Accessibility: Using alert() for download/copy error states ('No data to download yet', 'No data to copy yet'). Same issue as above.
- **Suggestion:** Replace alert() calls with status messages displayed inline near the buttons, using aria-live='polite' announcements.

**[FRONTEND]** `web/index.html:1067`

- **Issue:** SVG charts missing role and aria attributes. Generated SVG charts (word bubble, heatmap, decay, trends, bar charts) have no role='img' or aria-label on the <svg> element, making them invisible to screen readers.
- **Suggestion:** Add role='img' and aria-label='[descriptive label]' (or <title> element as first child) to each generated <svg> element. Container divs have aria-label but the actual SVG elements do not.

**[FRONTEND]** `web/index.html:948`

- **Issue:** Use of deprecated document.execCommand('copy') as clipboard fallback. execCommand is deprecated and may be removed in future browsers.
- **Suggestion:** Provide a user-visible fallback message (e.g., 'Press Ctrl+C to copy') when navigator.clipboard is unavailable, rather than relying on the deprecated execCommand API.

**[FRONTEND]** `web/index.html:506`

- **Issue:** All CSS is in a single <style> block in the HTML file (inline styles for the page). For a dashboard of this complexity, this makes the file very large and unmaintainable. The web/index.html file is over 1,700 lines.
- **Suggestion:** Extract CSS into a separate dashboard.css file and JS into dashboard.js. This enables browser caching, improves maintainability, and separates concerns.

**[FRONTEND]** `web/index.html:1`

- **Issue:** No Content Security Policy (CSP) meta tag. The dashboard loads content dynamically from its own API but has no CSP to restrict script execution or data sources.
- **Suggestion:** Add <meta http-equiv='Content-Security-Policy' content="default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self';"> — or better, set CSP headers at the server level.

**[INSTALLER]** `install.sh:60`

- **Issue:** Homebrew installer executed without user consent warning: '/bin/bash -c $(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)' runs arbitrary remote code. No prompt or warning is shown before executing.
- **Suggestion:** Add a user warning before Homebrew install: warn 'About to download and execute the Homebrew installer from GitHub.' and ask 'Continue? [y/N]:' to give user a chance to abort.

**[INSTALLER]** `install.sh:228`

- **Issue:** Cron job appended without removing duplicates. Re-running the installer adds another identical cron entry each time, growing the crontab unboundedly.
- **Suggestion:** Remove existing cypherpulse cron entries before adding the new one: (crontab -l 2>/dev/null | grep -v 'cypherpulse'; echo "$FULL_CRON") | crontab -

**[INSTALLER]** `install.sh:43`

- **Issue:** INSTALL_DIR accepts arbitrary user input without sanitizing shell metacharacters. When embedded in the CRON_CMD string (line ~220), a path containing semicolons or command substitution characters could inject commands into the crontab.
- **Suggestion:** Validate INSTALL_DIR after reading: reject paths containing ; ` $ ( ) characters. Or use printf '%q' when embedding INSTALL_DIR in cron command strings.

**[INSTALLER]** `install.ps1:163`

- **Issue:** .env file containing the API key is written with default filesystem permissions. On shared Windows systems, other local users can read the credentials.
- **Suggestion:** After writing the .env file, restrict ACL to current user only using Set-Acl with an explicit DACL that removes inherited permissions and grants only $env:USERNAME read access.

**[INSTALLER]** `install.ps1:87`

- **Issue:** ZIP fallback download (when git not found) has no integrity check. Downloaded archive is extracted immediately without hash verification. -ErrorAction SilentlyContinue on cleanup also masks failures.
- **Suggestion:** Add SHA256 verification for the ZIP before extraction. Remove -ErrorAction SilentlyContinue from cleanup — allow cleanup failures to surface as warnings.

**[INSTALLER]** `install.sh:100`

- **Issue:** trap for TMP_CLONE cleanup is registered inside the 'else' branch only. Errors before reaching this branch (e.g. during Python/git install) have no cleanup trap. Partial INSTALL_DIR state is never cleaned up on failure.
- **Suggestion:** Register a global error trap at script top: trap 'cleanup_on_error' ERR. Define cleanup_on_error() to remove partial state. This covers all failure paths, not just the clone path.

## 🔵 Low Priority Issues [FOR REVIEW]

**[SECURITY]** `cypherpulse/db.py:127`

- **Issue:** No input validation on `from_date`/`to_date` date strings passed to SQL. While they are used as parameterized query values (not concatenated), SQLite's `date()` function will silently ignore invalid formats. A malformed date like `'not-a-date'` won't error but will return incorrect/empty results with no user feedback.
- **Suggestion:** Validate date format with a regex or `datetime.strptime` before passing to DB functions: `re.match(r'^\d{4}-\d{2}-\d{2}$', date_str)`. Raise HTTPException 400 for invalid dates in the API layer.

**[SECURITY]** `cypherpulse/api.py:586`

- **Issue:** The `/api/benchmark` endpoint allows `max_tweets` up to 5000 with no authentication or rate limiting. Each call triggers multiple paginated HTTP requests to twitterapi.io, potentially exhausting the paid API quota. A single unauthenticated caller could drain the API budget.
- **Suggestion:** Add rate limiting to the `/api/benchmark` endpoint (e.g. per-IP using `slowapi`), or reduce the default/max for `max_tweets`. Since this is a local dashboard, documenting that it should not be exposed publicly is a minimum.

**[SECURITY]** `cypherpulse/db.py:79`

- **Issue:** Path traversal protection in `_validate_db_path` checks for `..` in `path.parts`, but `Path.resolve()` already resolves traversal — so checking `..` in resolved parts is redundant and could give false security. The real protection is the `startswith(home)` check, which works correctly but could fail if symlinks are involved.
- **Suggestion:** The existing check is functionally safe but misleadingly documented. Simplify to just the `startswith` check on the resolved path. Add a note that symlinks within home directory are permitted.

**[QUALITY]** `cypherpulse/api.py:315`

- **Issue:** asyncio imported inside fetch_handle_tweets() as . This defers the import and the unusual alias (_asyncio with underscore) is only used for asyncio.gather(). At line 292 the function already uses httpx which requires an async context, so asyncio is a known dependency.
- **Suggestion:** Move  to module-level imports at the top of api.py. Use the standard  name.

**[QUALITY]** `cypherpulse/api.py:315`

- **Issue:** fetch_page() inner function (api.py:315-325) uses a bare  that silently swallows all errors including network failures, JSON parse errors, and timeouts. The outer function catches a broad exception too. A response that fails silently returns {} which propagates as missing data with no diagnostic.
- **Suggestion:** Log the exception at debug/warning level inside fetch_page: . This preserves graceful degradation while maintaining observability.

**[PYTHON]** `cypherpulse/db.py:588`

- **Issue:** 'seen_bigrams: set = set()' and 'seen_trigrams: set = set()' use bare 'set' as type annotation. This is vague — the actual content is strings.
- **Suggestion:** Use 'seen_bigrams: set[str] = set()' for clarity and to enable proper type checker analysis.

**[PYTHON]** `setup.py:7`

- **Issue:** get_version() function missing return type hint (-> str). Minor inconsistency with the typed codebase.
- **Suggestion:** Add return type: 'def get_version() -> str:'

**[PYTHON]** `cypherpulse/db.py:498`

- **Issue:** STOPWORDS set is duplicated across 4 locations: db.py (get_word_bubbles inner scope), api.py (module level as _STOPWORDS), scripts/benchmark_external.py, and scripts/benchmark_words.py. This is a DRY violation — changes to stopwords must be made in 4 places.
- **Suggestion:** Extract STOPWORDS to a shared module (e.g., cypherpulse/constants.py) and import it wherever needed.

**[FRONTEND]** `docs/index.html:304`

- **Issue:** navigator.platform is deprecated. Used for OS detection in displayInstallCommand(). Modern browsers are phasing out this API.
- **Suggestion:** Use navigator.userAgentData.platform (with feature detection fallback) instead of navigator.platform. Example: const platform = navigator.userAgentData?.platform?.toLowerCase() || navigator.userAgent.toLowerCase();

**[FRONTEND]** `docs/index.html:467`

- **Issue:** Use of deprecated document.execCommand('copy') fallback for clipboard operations. Same issue as web/index.html.
- **Suggestion:** Use the same fallback pattern: show a 'Press Ctrl+C to copy' message when navigator.clipboard is unavailable.

**[FRONTEND]** `docs/index.html:494`

- **Issue:** window.onload used instead of DOMContentLoaded or defer attribute. window.onload fires after all resources (images, stylesheets) load, which is slower than DOMContentLoaded.
- **Suggestion:** Replace window.onload = function() {...} with document.addEventListener('DOMContentLoaded', function() {...}) for faster initialization, or add defer attribute to the script tag.

**[FRONTEND]** `web/index.html:1`

- **Issue:** Missing <meta name='description'> and Open Graph meta tags. The dashboard has no description for SEO or link-sharing previews.
- **Suggestion:** Add <meta name='description' content='CypherPulse - X/Twitter Analytics Dashboard'> and basic OG tags (og:title, og:description) in the <head>.

**[FRONTEND]** `web/index.html:636`

- **Issue:** The onchange handler on #wordBubbleMinTweets uses inline event handlers mixing JS directly in HTML attributes, with complex multi-expression logic.
- **Suggestion:** Move event handlers from HTML attributes to addEventListener calls in the JavaScript section for better separation of concerns and maintainability.

**[INSTALLER]** `install.sh:1`

- **Issue:** OS detection via $OSTYPE is bash-specific and empty in some environments (minimal containers, sh invocation). Script uses #!/bin/bash shebang (correct) but $OSTYPE may still be unset in non-interactive bash.
- **Suggestion:** Add fallback: 'if [ -z "$OSTYPE" ]; then case $(uname -s) in Linux*) OSTYPE=linux-gnu;; Darwin*) OSTYPE=darwin;; esac; fi'

**[INSTALLER]** `install.ps1:1`

- **Issue:** Script header says 'Run as Administrator' but does not verify admin privileges at startup. Some operations (winget with InstallAllUsers=1, system Python install) silently fail without admin rights, giving confusing errors later.
- **Suggestion:** Add admin check near top: 'if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { warn "Not running as Administrator. Some steps may fail." }'

**[INSTALLER]** `install.sh:75`

- **Issue:** sudo used without checking if it is available. In Docker containers or minimal Linux environments, sudo may not be installed, causing cryptic 'command not found' errors instead of a clear message.
- **Suggestion:** Check at the start of Linux package installs: 'if ! command -v sudo >/dev/null 2>&1; then die "sudo not found. Run as root or install sudo first."; fi'

---

## By Dimension

### Security (12 findings)

- **High** ✅: `web/index.html:1339` — XSS via unescaped `post_type` in innerHTML: `tr.innerHTML = '<td><strong>${row.post_type}</strong></td>...'`. The `post_...
- **High** ✅: `web/index.html:1602` — XSS via unescaped `post_type` in innerHTML for decay legend: `item.innerHTML = '<span ...></span> ${row.post_type} (n=${...
- **High** ✅: `web/index.html:1486` — XSS in hourly/daily bar chart render: `row.innerHTML` is built with `segments` which includes `t` (post_type) in the `ti...
- **Medium** ✅: `install.sh:189` — Potential sed injection via API key: `sed -i.bak "s#^TWITTER_API_KEY=.*#TWITTER_API_KEY=$API_KEY#"`. The `#` character i...
- **Medium**: `cypherpulse/api.py:258` — Hardcoded absolute server path to secrets file exposed as default: `_TWITTERAPI_SECRET_PATH = Path(os.getenv('TWITTERAPI...
- **Medium**: `scripts/benchmark_external.py:55` — Hardcoded absolute path to secrets file: `Path('/root/.openclaw/secrets/twitterapi-io.json')`. This is a server-specific...
- **Medium**: `scripts/analyze_public_account.py:111` — Hardcoded absolute path to secrets file: `Path('/root/.openclaw/secrets/twitterapi-io.json')`. Same issue as benchmark_e...
- **Medium**: `cypherpulse/api.py:621` — Unbounded POST body on `/api/benchmark/rescore`: accepts `List[Dict[str, Any]]` with no size limit. A client could send ...
- **Medium**: `cypherpulse/api.py:57` — CORS allows credentials (`allow_credentials=True`) with configurable origins from environment. If `ALLOWED_ORIGINS` is m...
- **Low**: `cypherpulse/db.py:127` — No input validation on `from_date`/`to_date` date strings passed to SQL. While they are used as parameterized query valu...
- **Low**: `cypherpulse/api.py:586` — The `/api/benchmark` endpoint allows `max_tweets` up to 5000 with no authentication or rate limiting. Each call triggers...
- **Low**: `cypherpulse/db.py:79` — Path traversal protection in `_validate_db_path` checks for `..` in `path.parts`, but `Path.resolve()` already resolves ...

### Code Quality (11 findings)

- **Critical**: `cypherpulse/db.py + cypherpulse/api.py:467` — Entire tokenization and PMI/IDF scoring pipeline is copy-pasted between get_word_bubbles() (db.py:467-720) and _score_tw...
- **High**: `cypherpulse/db.py:467` — get_word_bubbles() is 253 lines long with nesting depth of 10. The function handles DB querying, text preprocessing, sto...
- **High** ✅: `cypherpulse/collector.py:218` — In scan_tweets() and collect_snapshots(), conn.close() is called at the end of a try block but NOT in a finally block. I...
- **High**: `cypherpulse/api.py:292` — fetch_handle_tweets() (98 lines) has convoluted, self-contradicting logic. The docstring claims it walks cursors then fi...
- **Medium**: `cypherpulse/db.py:498` — STOPWORDS set is defined inside get_word_bubbles() function body (lines 498-519) as a local variable, reconstructed on e...
- **Medium**: `cypherpulse/db.py:495` —  and  are placed inside the get_word_bubbles() function body instead of at module level. This defers import resolution t...
- **Medium**: `cypherpulse/db.py + cypherpulse/api.py + cypherpulse/collector.py:11` — logging.basicConfig(level=logging.INFO) is called at module level in three separate library modules (db.py:11, api.py:52...
- **Medium**: `cypherpulse/api.py:390` — _score_tweets() is 190 lines long and contains the same three inner function definitions (_build_word_results, _build_bi...
- **Medium**: `cypherpulse/collector.py:234` — Magic number 280 used for text[:280] tweet truncation (collector.py:234) and magic number 500 used in LIMIT 500 query (c...
- **Low**: `cypherpulse/api.py:315` — asyncio imported inside fetch_handle_tweets() as . This defers the import and the unusual alias (_asyncio with underscor...
- **Low**: `cypherpulse/api.py:315` — fetch_page() inner function (api.py:315-325) uses a bare  that silently swallows all errors including network failures, ...

### Python Best Practices (11 findings)

- **Critical** ✅: `scripts/analyze_public_account.py:47` — Bare except: clause swallows ALL exceptions including KeyboardInterrupt and SystemExit. Any parse failure in the datetim...
- **High** ✅: `cypherpulse/collector.py:217` — scan_tweets() manually calls conn.close() inside a try/except block that only catches sqlite3.Error. If any other except...
- **High** ✅: `cypherpulse/collector.py:329` — collect_snapshots() has the same connection leak pattern: conn.close() is inside a try block that only catches sqlite3.E...
- **High** ✅: `scripts/benchmark_words.py:149` — sqlite3.connect() used without a context manager and no exception handling around the query. If conn.execute() or fetcha...
- **Medium**: `cypherpulse/db.py:495` — 'import re' and 'import math' placed inside the get_word_bubbles() function body, violating PEP 8 (E402). These are stan...
- **Medium**: `cypherpulse/api.py:304` — 'import asyncio as _asyncio' inside the fetch_handle_tweets() function body. PEP 8 requires imports at module top level....
- **Medium**: `cypherpulse/db.py:66` — Path comparison uses string startswith() instead of the idiomatic Path.is_relative_to() (Python 3.9+). The pattern 'str(...
- **Medium**: `scripts/analyze_public_account.py:15` — Functions fetch_tweets(), analyze(), and print_report() are missing type hints in their signatures. The main codebase (c...
- **Low**: `cypherpulse/db.py:588` — 'seen_bigrams: set = set()' and 'seen_trigrams: set = set()' use bare 'set' as type annotation. This is vague — the actu...
- **Low**: `setup.py:7` — get_version() function missing return type hint (-> str). Minor inconsistency with the typed codebase.
- **Low**: `cypherpulse/db.py:498` — STOPWORDS set is duplicated across 4 locations: db.py (get_word_bubbles inner scope), api.py (module level as _STOPWORDS...

### Frontend (18 findings)

- **High** ✅: `web/index.html:1338` — XSS risk: API data (row.post_type, row.posts, row.avg_likes, etc.) interpolated directly into innerHTML via template lit...
- **High** ✅: `web/index.html:1412` — XSS risk: API-sourced values (type, val, date, shortDate) interpolated into SVG innerHTML in renderTrendsChart(). Post t...
- **High** ✅: `web/index.html:1602` — XSS risk: row.post_type from API is interpolated directly into innerHTML in the decay legend render (item.innerHTML = `....
- **High** ✅: `web/index.html:1486` — XSS risk: axisLabel (derived from API data via labelKey) interpolated into innerHTML in renderBarChart(). The day_name a...
- **High** ✅: `web/index.html:461` — Insufficient mobile responsive design: Only breakpoints at 400px and 350px are defined. No tablet breakpoints (768px) or...
- **Medium**: `web/index.html:647` — Accessibility: The benchmark handle input (#benchmarkHandle) has no aria-label or associated <label> element. The '@' sp...
- **Medium**: `web/index.html:533` — Accessibility: Info icon tooltips use click-toggle (onclick="this.classList.toggle('open')") which is not keyboard-acces...
- **Medium**: `web/index.html:764` — UX/Accessibility: Using alert() for form validation feedback ('Please select both dates', 'From date must be before To d...
- **Medium**: `web/index.html:920` — UX/Accessibility: Using alert() for download/copy error states ('No data to download yet', 'No data to copy yet'). Same ...
- **Medium**: `web/index.html:1067` — SVG charts missing role and aria attributes. Generated SVG charts (word bubble, heatmap, decay, trends, bar charts) have...
- **Medium**: `web/index.html:948` — Use of deprecated document.execCommand('copy') as clipboard fallback. execCommand is deprecated and may be removed in fu...
- **Medium**: `web/index.html:506` — All CSS is in a single <style> block in the HTML file (inline styles for the page). For a dashboard of this complexity, ...
- **Medium**: `web/index.html:1` — No Content Security Policy (CSP) meta tag. The dashboard loads content dynamically from its own API but has no CSP to re...
- **Low**: `docs/index.html:304` — navigator.platform is deprecated. Used for OS detection in displayInstallCommand(). Modern browsers are phasing out this...
- **Low**: `docs/index.html:467` — Use of deprecated document.execCommand('copy') fallback for clipboard operations. Same issue as web/index.html.
- **Low**: `docs/index.html:494` — window.onload used instead of DOMContentLoaded or defer attribute. window.onload fires after all resources (images, styl...
- **Low**: `web/index.html:1` — Missing <meta name='description'> and Open Graph meta tags. The dashboard has no description for SEO or link-sharing pre...
- **Low**: `web/index.html:636` — The onchange handler on #wordBubbleMinTweets uses inline event handlers mixing JS directly in HTML attributes, with comp...

### Installer/Scripts (14 findings)

- **High** ✅: `install.sh:3` — Script designed for curl | bash pipe execution but set -euo pipefail plus stdin consumption via /dev/tty is fragile. A t...
- **High** ✅: `install.sh:189` — sed injection risk via API key: sed uses '#' as delimiter but API keys can legitimately contain '#' characters. A key wi...
- **High** ✅: `install.ps1:68` — Python installer EXE downloaded from python.org and executed immediately without integrity verification. A MITM or compr...
- **High** ✅: `install.ps1:92` — git clone and git pull exit codes not checked. In PowerShell, native executables do NOT throw terminating errors on non-...
- **High** ✅: `install.ps1:119` — pip install calls (upgrade pip, install -r requirements.txt, install -e .) do not check $LASTEXITCODE. Native executable...
- **Medium**: `install.sh:60` — Homebrew installer executed without user consent warning: '/bin/bash -c $(curl -fsSL https://raw.githubusercontent.com/H...
- **Medium**: `install.sh:228` — Cron job appended without removing duplicates. Re-running the installer adds another identical cron entry each time, gro...
- **Medium**: `install.sh:43` — INSTALL_DIR accepts arbitrary user input without sanitizing shell metacharacters. When embedded in the CRON_CMD string (...
- **Medium**: `install.ps1:163` — .env file containing the API key is written with default filesystem permissions. On shared Windows systems, other local ...
- **Medium**: `install.ps1:87` — ZIP fallback download (when git not found) has no integrity check. Downloaded archive is extracted immediately without h...
- **Medium**: `install.sh:100` — trap for TMP_CLONE cleanup is registered inside the 'else' branch only. Errors before reaching this branch (e.g. during ...
- **Low**: `install.sh:1` — OS detection via $OSTYPE is bash-specific and empty in some environments (minimal containers, sh invocation). Script use...
- **Low**: `install.ps1:1` — Script header says 'Run as Administrator' but does not verify admin privileges at startup. Some operations (winget with ...
- **Low**: `install.sh:75` — sudo used without checking if it is available. In Docker containers or minimal Linux environments, sudo may not be insta...

---

## Commits

- `c88fbf8`: Auto-fix batch
- `df52d4c`: Auto-fix batch
- `eaa989f`: Auto-fix batch
- *(next)*: QA Report for 2026-03-18

---
*Generated by Tibor (AI QA) on 2026-03-18*
