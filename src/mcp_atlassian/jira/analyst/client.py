"""HTTP helper for the Jira DC Analyst toolset.

Wraps the authenticated ``requests.Session`` already configured on a
``JiraFetcher`` by mcp-atlassian and exposes two convenience calls:

* :meth:`AnalystClient.sr_action` — hits a ScriptRunner custom REST endpoint
  (``admin_analyst.groovy``) with an ``action`` parameter.
* :meth:`AnalystClient.rest_get` / :meth:`AnalystClient.rest_post` — direct
  calls against arbitrary Jira REST paths (used by plugin APIs such as
  ScriptRunner REST, Automation for Jira, Structure-Gantt, auditing).

Auth/SSL/proxy are inherited from the fetcher — no extra configuration is
needed beyond pointing ``JIRA_ANALYST_SR_PATH`` at the deployed endpoint
(defaults to ``/rest/scriptrunner/latest/custom/adminAnalyst``).
"""

from __future__ import annotations

import logging
import os
from typing import Any

import requests

from mcp_atlassian.jira import JiraFetcher

logger = logging.getLogger("mcp-atlassian.jira.analyst")

DEFAULT_SR_ENDPOINT_PATH = "/rest/scriptrunner/latest/custom/adminAnalyst"
DEFAULT_TIMEOUT = 60.0


class AnalystError(Exception):
    """Wraps non-2xx responses from the analyst endpoint or Jira REST API."""

    def __init__(
        self,
        message: str,
        status: int | None = None,
        body: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.body = body


def _sr_endpoint_path() -> str:
    """Return the SR analyst endpoint path, overridable via env var."""
    return os.getenv("JIRA_ANALYST_SR_PATH", DEFAULT_SR_ENDPOINT_PATH)


class AnalystClient:
    """Thin wrapper around a JiraFetcher's authenticated session."""

    def __init__(self, fetcher: JiraFetcher) -> None:
        self._fetcher = fetcher
        self._session: requests.Session = fetcher.jira._session
        self._base_url: str = fetcher.config.url.rstrip("/")
        try:
            timeout = float(
                os.getenv("JIRA_ANALYST_TIMEOUT", str(fetcher.config.timeout or DEFAULT_TIMEOUT))
            )
        except (TypeError, ValueError):
            timeout = DEFAULT_TIMEOUT
        self._timeout = timeout

    def _raise_for_status(self, resp: requests.Response, where: str) -> None:
        if resp.ok:
            return
        body_preview = (resp.text or "")[:500]
        logger.warning(
            "HTTP %s from %s (%s): %s",
            resp.status_code,
            where,
            resp.request.url if resp.request else "unknown",
            body_preview,
        )
        raise AnalystError(
            f"{where} returned HTTP {resp.status_code}",
            status=resp.status_code,
            body=body_preview,
        )

    def sr_action(self, action: str, **params: Any) -> Any:
        """Call ``admin_analyst.groovy`` with ``?action=<name>&...``."""
        url = f"{self._base_url}{_sr_endpoint_path()}"
        query: dict[str, str] = {"action": action}
        for key, value in params.items():
            if value is None or value == "":
                continue
            query[key] = str(value)
        logger.debug("SR call action=%s keys=%s", action, list(query.keys()))
        try:
            resp = self._session.get(
                url,
                params=query,
                headers={"Accept": "application/json"},
                timeout=self._timeout,
            )
        except requests.RequestException as exc:
            raise AnalystError(f"transport error calling {action}: {exc}") from exc
        self._raise_for_status(resp, f"SR action={action}")
        return resp.json()

    def rest_get(self, path: str, **params: Any) -> Any:
        """GET a Jira REST path relative to the instance base URL."""
        url = f"{self._base_url}{path}"
        query = {k: str(v) for k, v in params.items() if v is not None and v != ""}
        logger.debug("REST GET %s", path)
        try:
            resp = self._session.get(
                url,
                params=query,
                headers={"Accept": "application/json"},
                timeout=self._timeout,
            )
        except requests.RequestException as exc:
            raise AnalystError(f"transport error on GET {path}: {exc}") from exc
        self._raise_for_status(resp, f"REST GET {path}")
        return resp.json()

    def rest_post(self, path: str, json_body: dict[str, Any]) -> Any:
        """POST a JSON body to a Jira REST path."""
        url = f"{self._base_url}{path}"
        logger.debug("REST POST %s", path)
        try:
            resp = self._session.post(
                url,
                json=json_body,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                timeout=self._timeout,
            )
        except requests.RequestException as exc:
            raise AnalystError(f"transport error on POST {path}: {exc}") from exc
        self._raise_for_status(resp, f"REST POST {path}")
        return resp.json() if resp.content else {}
