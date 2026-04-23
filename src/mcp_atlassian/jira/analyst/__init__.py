"""Jira DC Analyst extensions for mcp-atlassian.

Read-only deep-inspection toolset for Jira Data Center admins. Adds tools for
ScriptRunner, JMWE, Structure/Gantt, Insight/Assets, Automation for Jira,
workflow/scheme configuration, audit and system logs.

Backed by a ScriptRunner custom REST endpoint (``admin_analyst.groovy``)
installed on the target Jira instance, plus direct calls to plugin REST APIs
where available.
"""

from .client import AnalystClient, AnalystError

__all__ = ["AnalystClient", "AnalystError"]
