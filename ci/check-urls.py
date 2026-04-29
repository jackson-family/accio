"""Check every external URL referenced in the Markdown content.

Writes a Markdown report listing any URL that isn't a clean 200. Designed
to run locally or in GitHub Actions: when `GITHUB_ACTIONS=true` it also
emits a job summary and `::error` annotations for each failing URL.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import os
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict

REF_LINK = re.compile(r"^\[[^]]+]:\s+(https?://\S+)\s*$")

DEFAULT_TIMEOUT = 15.0
DEFAULT_WORKERS = 16
DEFAULT_RETRIES = 2
FAIL_POLICIES = {"any", "non-redirect", "server-only", "never"}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)
BROWSER_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,"
    "image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Treat redirects as terminal responses instead of following them."""

    def redirect_request(self, req, fp, code, msg, headers, newurl) -> None:
        return None


OPENER = urllib.request.build_opener(NoRedirect)


def extract_urls(root: pathlib.Path) -> dict[str, list[tuple[str, int]]]:
    urls: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for md in sorted(root.rglob("*.md")):
        with md.open(encoding="utf-8") as f:
            for lineno, line in enumerate(f, start=1):
                m = REF_LINK.match(line)
                if m:
                    urls[m.group(1)].append((str(md), lineno))
    return urls


def _open(url: str, method: str, timeout: float):
    req = urllib.request.Request(url, method=method, headers=BROWSER_HEADERS)  # noqa: S310
    return OPENER.open(req, timeout=timeout)


def _check_once(url: str, timeout: float) -> tuple[int | None, str]:
    try:
        try:
            resp = _open(url, "HEAD", timeout)
        except urllib.error.HTTPError as e:
            if e.code in (403, 405, 501):
                resp = _open(url, "GET", timeout)
            else:
                raise
        with resp:
            status = resp.status
            if 300 <= status < 400:
                return status, resp.headers.get("Location", "") or ""
            return status, ""
    except urllib.error.HTTPError as e:
        if 300 <= e.code < 400:
            location = e.headers.get("Location", "") if e.headers else ""
            return e.code, location or ""
        return e.code, ""
    except urllib.error.URLError as e:
        return None, f"URLError: {e.reason}"
    except TimeoutError:
        return None, "timeout"
    except (ConnectionError, OSError) as e:
        return None, f"{type(e).__name__}: {e}"


def check(url: str, timeout: float, retries: int) -> tuple[str, int | None, str]:
    """Return (url, status_code_or_None, detail), retrying transient failures."""
    status: int | None = None
    detail = ""
    for attempt in range(retries + 1):
        status, detail = _check_once(url, timeout)
        transient = (
            status is None
            or (status is not None and 500 <= status < 600)
            or status == 429
        )
        if not transient or attempt == retries:
            return url, status, detail
        time.sleep(2**attempt)
    return url, status, detail


def category_for(status: int | None) -> str:
    if status is None:
        return "Network failure"
    if 300 <= status < 400:
        return "Redirect"
    if 400 <= status < 500:
        return "Client error"
    if 500 <= status < 600:
        return "Server error"
    return f"Unexpected status {status}"


def describe(status: int | None, detail: str) -> str:
    if status is None:
        return detail
    if 300 <= status < 400 and detail:
        return f"{status} -> `{detail}`"
    return str(status)


def should_fail(policy: str, status: int | None) -> bool:
    if policy == "never":
        return False
    if status == 200:
        return False
    if policy == "any":
        return True
    if policy == "non-redirect":
        return not (status is not None and 300 <= status < 400)
    if policy == "server-only":
        return status is None or (status is not None and status >= 500)
    return True


def build_report(
    urls: dict[str, list[tuple[str, int]]],
    results: list[tuple[str, int | None, str]],
) -> str:
    problems = [(u, s, d) for u, s, d in results if s != 200]
    total_refs = sum(len(v) for v in urls.values())

    lines = [
        "# URL check report",
        "",
        f"- Distinct URLs checked: **{len(urls)}**",
        f"- Total references in content: **{total_refs}**",
        f"- URLs needing investigation: **{len(problems)}**",
        "",
    ]

    if not problems:
        lines.append("All URLs returned `200 OK`.")
        return "\n".join(lines) + "\n"

    grouped: dict[str, list[tuple[str, int | None, str]]] = defaultdict(list)
    for url, status, detail in problems:
        grouped[category_for(status)].append((url, status, detail))

    category_order = ["Redirect", "Client error", "Server error", "Network failure"]
    for cat in category_order + sorted(set(grouped) - set(category_order)):
        if cat not in grouped:
            continue
        lines.append(f"## {cat} ({len(grouped[cat])})")
        lines.append("")
        for url, status, detail in sorted(grouped[cat]):
            lines.extend(
                [
                    f"### {describe(status, detail)}",
                    "",
                    f"- URL: <{url}>",
                    "- References:",
                ]
            )
            for file, lineno in urls[url]:
                lines.append(f"    - `{file}:{lineno}`")
            lines.append("")

    return "\n".join(lines)


def _gha_escape(value: str) -> str:
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def emit_gha_annotations(
    urls: dict[str, list[tuple[str, int]]],
    results: list[tuple[str, int | None, str]],
    policy: str,
) -> None:
    for url, status, detail in results:
        if not should_fail(policy, status):
            continue
        message = f"{describe(status, detail)}: {url}"
        for file, lineno in urls[url]:
            print(
                f"::error file={_gha_escape(file)},line={lineno},"
                f"title=Broken URL::{_gha_escape(message)}"
            )


def append_gha_summary(report: str) -> None:
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return
    with open(summary_path, "a", encoding="utf-8") as f:
        f.write(report)
        if not report.endswith("\n"):
            f.write("\n")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--content", type=pathlib.Path, default=pathlib.Path("content"))
    p.add_argument("--report", type=pathlib.Path, default=pathlib.Path("url-report.md"))
    p.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    p.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    p.add_argument("--retries", type=int, default=DEFAULT_RETRIES)
    p.add_argument(
        "--fail-on",
        choices=sorted(FAIL_POLICIES),
        default="non-redirect",
        help="Which problems cause a non-zero exit (default: non-redirect).",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    in_ci = os.environ.get("GITHUB_ACTIONS") == "true"

    urls = extract_urls(args.content)
    total_refs = sum(len(v) for v in urls.values())
    print(f"Found {len(urls)} distinct URLs across {total_refs} references.")

    results: list[tuple[str, int | None, str]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {
            ex.submit(check, url, args.timeout, args.retries): url for url in urls
        }
        for i, fut in enumerate(concurrent.futures.as_completed(futures), start=1):
            url, status, detail = fut.result()
            results.append((url, status, detail))
            marker = "ok  " if status == 200 else "FAIL"
            line = f"[{i:4d}/{len(urls)}] {marker} {url}  {describe(status, detail)}"
            print(line, flush=True)

    report = build_report(urls, results)
    args.report.write_text(report, encoding="utf-8")

    failing = [(u, s, d) for u, s, d in results if should_fail(args.fail_on, s)]
    non_200 = sum(1 for _, s, _ in results if s != 200)
    print(
        f"\nReport written to {args.report} "
        f"({non_200} non-200, {len(failing)} failing under policy '{args.fail_on}')."
    )

    if in_ci:
        append_gha_summary(report)
        emit_gha_annotations(urls, results, args.fail_on)

    return 1 if failing else 0


if __name__ == "__main__":
    sys.exit(main())
