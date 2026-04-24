"""Jira DC Analyst toolset registrations.

Adds ~60 read-only tools to the ``jira_mcp`` FastMCP instance for deep admin
inspection of a Jira Data Center deployment — workflows, screens, schemes,
ScriptRunner/JMWE/Structure/Insight/A4J plugins, audit & system logs.

All tools are backed by either:
  * a ScriptRunner custom REST endpoint (``admin_analyst.groovy``) that must
    be installed on the target instance at ``JIRA_ANALYST_SR_PATH``
    (default ``/rest/scriptrunner/latest/custom/adminAnalyst``); or
  * direct plugin REST paths when they expose richer data than the analyst
    endpoint can (SR listener scripts, Automation for Jira, Structure-Gantt,
    Jira auditing).

Ported from https://github.com/aforbco/jira-analyst-mcp — see the README for
the Groovy source and installation steps.
"""

import base64
import json
import logging
from typing import Annotated, Any

from fastmcp import Context
from mcp.types import ImageContent, TextContent
from pydantic import Field

from mcp_atlassian.jira.analyst.client import AnalystClient, AnalystError
from mcp_atlassian.servers.dependencies import get_jira_fetcher
from mcp_atlassian.utils.media import is_image_attachment

logger = logging.getLogger("mcp-atlassian.servers.jira_analyst")


MAX_AQL_LENGTH = 2000

# Attachment-inspection limits (ported from jira-analyst-mcp).
# Image size cap for inline delivery as MCP ImageContent — Claude vision
# naturally handles png/jpeg/gif/webp up to a few MB; going beyond that
# is wasteful since the model downsamples server-side anyway.
_MAX_IMAGE_BYTES = 5 * 1024 * 1024
_MAX_TEXT_DOWNLOAD_BYTES = 1_000_000  # hard cap on a single text file download
_MAX_TEXT_CHARS = 50_000  # after decode, truncate for the LLM
_MAX_BINARY_BASE64_BYTES = 200_000  # only inline small binaries as base64
_VISIBLE_IMAGE_MIMES = frozenset(
    {"image/png", "image/jpeg", "image/gif", "image/webp"}
)
_TEXT_MIME_PREFIXES = (
    "text/",
    "application/json",
    "application/xml",
    "application/javascript",
    "application/csv",
    "application/x-yaml",
    "application/sql",
)
_TEXT_EXTENSIONS = (
    ".txt",
    ".csv",
    ".json",
    ".xml",
    ".yml",
    ".yaml",
    ".md",
    ".log",
    ".sql",
    ".groovy",
    ".py",
    ".js",
    ".ts",
    ".java",
    ".kt",
    ".sh",
)


def _looks_like_text(mime: str, filename: str) -> bool:
    if mime and mime.startswith(_TEXT_MIME_PREFIXES):
        return True
    return filename.lower().endswith(_TEXT_EXTENSIONS)


def _fmt(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def _err(msg: str, **extra: Any) -> str:
    payload: dict[str, Any] = {"error": msg}
    payload.update(extra)
    return _fmt(payload)


async def _get_client(ctx: Context) -> AnalystClient:
    fetcher = await get_jira_fetcher(ctx)
    return AnalystClient(fetcher)


def register_analyst_tools(jira_mcp: Any) -> None:  # noqa: C901 — thin wrappers
    """Attach Jira DC analyst tools to the provided FastMCP instance."""

    # =====================================================================
    # Admin configuration (workflows, screens, schemes, users, groups, etc.)
    # =====================================================================

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_admin"},
        annotations={"title": "List Workflows", "readOnlyHint": True},
    )
    async def list_workflows(
        ctx: Context,
        search: Annotated[
            str,
            Field(description="Case-insensitive substring filter on workflow name."),
        ] = "",
    ) -> str:
        """List all Jira workflows with step counts and last-updated dates."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("list_workflows", search=search))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_admin"},
        annotations={"title": "Get Workflow", "readOnlyHint": True},
    )
    async def get_workflow(
        ctx: Context,
        workflow_name: Annotated[str, Field(description="Workflow name.")],
    ) -> str:
        """Get workflow structure — steps with linked statuses, global actions, transitions."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("get_workflow", name=workflow_name))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_admin"},
        annotations={"title": "Get Workflow Transition", "readOnlyHint": True},
    )
    async def get_workflow_transition(
        ctx: Context,
        workflow_name: Annotated[str, Field(description="Workflow name.")],
        transition_id: Annotated[
            str,
            Field(description="Numeric transition action id (e.g. '1' for Create Issue)."),
        ],
    ) -> str:
        """Conditions tree, validators, pre/post-functions with class names and parameters."""
        client = await _get_client(ctx)
        return _fmt(
            client.sr_action(
                "get_workflow_transition",
                name=workflow_name,
                transitionId=transition_id,
            )
        )

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_admin"},
        annotations={"title": "Get Workflow XML", "readOnlyHint": True},
    )
    async def get_workflow_xml(
        ctx: Context,
        workflow_name: Annotated[str, Field(description="Workflow name.")],
    ) -> str:
        """Raw OSWorkflow XML — for deep inspection, migration, or diffing."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("get_workflow_xml", name=workflow_name))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_admin"},
        annotations={"title": "List Screens", "readOnlyHint": True},
    )
    async def list_screens(
        ctx: Context,
        search: Annotated[str, Field(description="Substring filter on screen name.")] = "",
    ) -> str:
        """List all field screens — id, name, description, tab count."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("list_screens", search=search))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_admin"},
        annotations={"title": "Get Screen", "readOnlyHint": True},
    )
    async def get_screen(
        ctx: Context,
        screen_id: Annotated[str, Field(description="Numeric screen id.")],
    ) -> str:
        """Screen tabs with their fields (id, name, position)."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("get_screen", id=screen_id))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_admin"},
        annotations={"title": "List Screen Schemes", "readOnlyHint": True},
    )
    async def list_screen_schemes(
        ctx: Context,
        search: Annotated[str, Field(description="Substring filter on name.")] = "",
    ) -> str:
        """Maps operations (Create/Edit/View) to screens."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("list_screen_schemes", search=search))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_admin"},
        annotations={"title": "List Issue Type Screen Schemes", "readOnlyHint": True},
    )
    async def list_issue_type_screen_schemes(
        ctx: Context,
        search: Annotated[str, Field(description="Substring filter on name.")] = "",
    ) -> str:
        """Maps issue types to screen schemes."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("list_issue_type_screen_schemes", search=search))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_admin"},
        annotations={"title": "List Permission Schemes", "readOnlyHint": True},
    )
    async def list_permission_schemes(ctx: Context,
        random_string: Annotated[
            str,
            Field(description="Reserved — included to keep a non-empty tool schema for OpenAI-gateway compatibility."),
        ] = "",
    ) -> str:
        """List all permission schemes with associated project keys."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("list_permission_schemes"))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_admin"},
        annotations={"title": "Get Permission Scheme", "readOnlyHint": True},
    )
    async def get_permission_scheme(
        ctx: Context,
        scheme_id: Annotated[str, Field(description="Permission scheme id.")],
    ) -> str:
        """All permission grants (permission key, grant type, grant value)."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("get_permission_scheme", id=scheme_id))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_admin"},
        annotations={"title": "List Notification Schemes", "readOnlyHint": True},
    )
    async def list_notification_schemes(ctx: Context,
        random_string: Annotated[
            str,
            Field(description="Reserved — included to keep a non-empty tool schema for OpenAI-gateway compatibility."),
        ] = "",
    ) -> str:
        """List all notification schemes with associated project keys."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("list_notification_schemes"))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_admin"},
        annotations={"title": "Get Notification Scheme", "readOnlyHint": True},
    )
    async def get_notification_scheme(
        ctx: Context,
        scheme_id: Annotated[str, Field(description="Notification scheme id.")],
    ) -> str:
        """All event-to-recipient mappings for the scheme."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("get_notification_scheme", id=scheme_id))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_admin"},
        annotations={"title": "List Workflow Schemes", "readOnlyHint": True},
    )
    async def list_workflow_schemes(ctx: Context,
        random_string: Annotated[
            str,
            Field(description="Reserved — included to keep a non-empty tool schema for OpenAI-gateway compatibility."),
        ] = "",
    ) -> str:
        """List all workflow schemes with associated project keys."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("list_workflow_schemes"))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_admin"},
        annotations={"title": "Get Workflow Scheme", "readOnlyHint": True},
    )
    async def get_workflow_scheme(
        ctx: Context,
        scheme_id: Annotated[str, Field(description="Workflow scheme id.")],
    ) -> str:
        """Default workflow and issue type → workflow mappings."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("get_workflow_scheme", id=scheme_id))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_admin"},
        annotations={"title": "Get Project Admin Config", "readOnlyHint": True},
    )
    async def get_project_config(
        ctx: Context,
        project_key: Annotated[str, Field(description="Project key (e.g. 'HR').")],
    ) -> str:
        """Full project admin view — all assigned schemes, roles with members, components, versions."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("get_project_config", key=project_key))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_admin"},
        annotations={"title": "List Projects (Admin View)", "readOnlyHint": True},
    )
    async def list_projects(
        ctx: Context,
        search: Annotated[str, Field(description="Substring filter on key or name.")] = "",
    ) -> str:
        """Projects with key, name, lead, category, assigned permission/workflow schemes."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("list_projects", search=search))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_admin"},
        annotations={"title": "List Groups", "readOnlyHint": True},
    )
    async def list_groups(
        ctx: Context,
        search: Annotated[str, Field(description="Substring filter on group name.")] = "",
    ) -> str:
        """List all groups with member counts."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("list_groups", search=search))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_admin"},
        annotations={"title": "Get Group Members", "readOnlyHint": True},
    )
    async def get_group_members(
        ctx: Context,
        group_name: Annotated[str, Field(description="Exact group name.")],
    ) -> str:
        """Group members — username, display name, email, active flag."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("get_group_members", group=group_name))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_admin"},
        annotations={"title": "List Project Roles", "readOnlyHint": True},
    )
    async def list_project_roles(ctx: Context,
        random_string: Annotated[
            str,
            Field(description="Reserved — included to keep a non-empty tool schema for OpenAI-gateway compatibility."),
        ] = "",
    ) -> str:
        """All project roles — id, name, description."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("list_project_roles"))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_admin"},
        annotations={"title": "Get Project Role Members", "readOnlyHint": True},
    )
    async def get_project_role_members(
        ctx: Context,
        project_key: Annotated[str, Field(description="Project key.")],
        role_id: Annotated[str, Field(description="Role id.")],
    ) -> str:
        """Users and groups assigned to a role in the given project."""
        client = await _get_client(ctx)
        return _fmt(
            client.sr_action(
                "get_project_role_members", project=project_key, roleId=role_id
            )
        )

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_admin"},
        annotations={"title": "Get User (Admin View)", "readOnlyHint": True},
    )
    async def get_user(
        ctx: Context,
        username: Annotated[str, Field(description="Username (preferred for DC).")] = "",
        key: Annotated[str, Field(description="User key.")] = "",
    ) -> str:
        """Display name, email, active, groups, application roles (Software/JSM/Core)."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("get_user", username=username, key=key))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_admin"},
        annotations={"title": "List Application Roles", "readOnlyHint": True},
    )
    async def list_application_roles(ctx: Context,
        random_string: Annotated[
            str,
            Field(description="Reserved — included to keep a non-empty tool schema for OpenAI-gateway compatibility."),
        ] = "",
    ) -> str:
        """License tiers with seat usage — critical for capacity audits."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("list_application_roles"))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_admin"},
        annotations={"title": "List Issue Types", "readOnlyHint": True},
    )
    async def list_issue_types(ctx: Context,
        random_string: Annotated[
            str,
            Field(description="Reserved — included to keep a non-empty tool schema for OpenAI-gateway compatibility."),
        ] = "",
    ) -> str:
        """All issue types — id, name, description, isSubtask, icon."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("list_issue_types"))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_admin"},
        annotations={"title": "List Issue Type Schemes", "readOnlyHint": True},
    )
    async def list_issue_type_schemes(
        ctx: Context,
        search: Annotated[str, Field(description="Substring filter on name.")] = "",
    ) -> str:
        """Default issue type, mapped types, associated projects."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("list_issue_type_schemes", search=search))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_admin"},
        annotations={"title": "List Reference Data", "readOnlyHint": True},
    )
    async def list_reference_data(ctx: Context,
        random_string: Annotated[
            str,
            Field(description="Reserved — included to keep a non-empty tool schema for OpenAI-gateway compatibility."),
        ] = "",
    ) -> str:
        """All statuses (with categories), priorities, resolutions."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("list_reference_data"))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_admin"},
        annotations={"title": "List Field Configurations", "readOnlyHint": True},
    )
    async def list_field_configurations(
        ctx: Context,
        search: Annotated[str, Field(description="Substring filter on name.")] = "",
    ) -> str:
        """Field configurations — id, name, isDefault, field count."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("list_field_configurations", search=search))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_admin"},
        annotations={"title": "Get Field Configuration", "readOnlyHint": True},
    )
    async def get_field_configuration(
        ctx: Context,
        config_id: Annotated[
            str,
            Field(description="Config id, or 'default' for the default configuration."),
        ],
    ) -> str:
        """Per-field settings: hidden, required, renderer, description override."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("get_field_configuration", id=config_id))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_admin"},
        annotations={"title": "List Field Configuration Schemes", "readOnlyHint": True},
    )
    async def list_field_config_schemes(
        ctx: Context,
        search: Annotated[str, Field(description="Substring filter on name.")] = "",
    ) -> str:
        """Field-config schemes with associated projects."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("list_field_config_schemes", search=search))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_admin"},
        annotations={"title": "Get Field Configuration Scheme", "readOnlyHint": True},
    )
    async def get_field_config_scheme(
        ctx: Context,
        scheme_id: Annotated[str, Field(description="Field config scheme id.")],
    ) -> str:
        """Issue type → field configuration mappings."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("get_field_config_scheme", id=scheme_id))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_admin"},
        annotations={"title": "List Issue Link Types", "readOnlyHint": True},
    )
    async def list_issue_link_types(ctx: Context,
        random_string: Annotated[
            str,
            Field(description="Reserved — included to keep a non-empty tool schema for OpenAI-gateway compatibility."),
        ] = "",
    ) -> str:
        """All link types — name, inward/outward descriptions."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("list_issue_link_types"))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_admin"},
        annotations={"title": "List Issue Security Schemes", "readOnlyHint": True},
    )
    async def list_issue_security_schemes(ctx: Context,
        random_string: Annotated[
            str,
            Field(description="Reserved — included to keep a non-empty tool schema for OpenAI-gateway compatibility."),
        ] = "",
    ) -> str:
        """All issue security schemes with associated project keys."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("list_issue_security_schemes"))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_admin"},
        annotations={"title": "Get Issue Security Scheme", "readOnlyHint": True},
    )
    async def get_issue_security_scheme(
        ctx: Context,
        scheme_id: Annotated[str, Field(description="Issue security scheme id.")],
    ) -> str:
        """All security levels with their access grants (users, groups, roles)."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("get_issue_security_scheme", id=scheme_id))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_admin"},
        annotations={"title": "Get Server Info", "readOnlyHint": True},
    )
    async def get_server_info(ctx: Context,
        random_string: Annotated[
            str,
            Field(description="Reserved — included to keep a non-empty tool schema for OpenAI-gateway compatibility."),
        ] = "",
    ) -> str:
        """Jira version, build number, base URL, title."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("get_server_info"))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_admin"},
        annotations={"title": "Get Application Properties", "readOnlyHint": True},
    )
    async def get_application_properties(
        ctx: Context,
        search: Annotated[str, Field(description="Filter by key or value substring.")] = "",
    ) -> str:
        """Global settings: time tracking, attachment limits, voting, watching, subtasks."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("get_application_properties", search=search))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_admin"},
        annotations={"title": "List Project Categories", "readOnlyHint": True},
    )
    async def list_project_categories(ctx: Context,
        random_string: Annotated[
            str,
            Field(description="Reserved — included to keep a non-empty tool schema for OpenAI-gateway compatibility."),
        ] = "",
    ) -> str:
        """Project categories — used to group projects."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("list_project_categories"))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_admin"},
        annotations={"title": "List Event Types", "readOnlyHint": True},
    )
    async def list_event_types(ctx: Context,
        random_string: Annotated[
            str,
            Field(description="Reserved — included to keep a non-empty tool schema for OpenAI-gateway compatibility."),
        ] = "",
    ) -> str:
        """All event types — maps event IDs in notification schemes to human-readable names."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("list_event_types"))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_admin"},
        annotations={"title": "List Global Permissions", "readOnlyHint": True},
    )
    async def list_global_permissions(ctx: Context,
        random_string: Annotated[
            str,
            Field(description="Reserved — included to keep a non-empty tool schema for OpenAI-gateway compatibility."),
        ] = "",
    ) -> str:
        """Who has SYSTEM_ADMIN, ADMINISTER, USE, BULK_CHANGE, etc."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("list_global_permissions"))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_admin"},
        annotations={"title": "List Shared Filters", "readOnlyHint": True},
    )
    async def list_shared_filters(
        ctx: Context,
        search: Annotated[str, Field(description="Substring filter on name.")] = "",
    ) -> str:
        """All shared filters — name, JQL, owner, favourite count."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("list_shared_filters", search=search))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_admin"},
        annotations={"title": "List Dashboards", "readOnlyHint": True},
    )
    async def list_dashboards(
        ctx: Context,
        search: Annotated[str, Field(description="Substring filter on name.")] = "",
    ) -> str:
        """All shared dashboards — name, owner, favourite count, system default."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("list_dashboards", search=search))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_admin"},
        annotations={"title": "Get Cluster Info", "readOnlyHint": True},
    )
    async def get_cluster_info(ctx: Context,
        random_string: Annotated[
            str,
            Field(description="Reserved — included to keep a non-empty tool schema for OpenAI-gateway compatibility."),
        ] = "",
    ) -> str:
        """DC cluster: is clustered, node count, each node ID/state/IP, current node flag."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("get_cluster_info"))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_admin"},
        annotations={"title": "List Priority Schemes", "readOnlyHint": True},
    )
    async def list_priority_schemes(ctx: Context,
        random_string: Annotated[
            str,
            Field(description="Reserved — included to keep a non-empty tool schema for OpenAI-gateway compatibility."),
        ] = "",
    ) -> str:
        """Priority schemes (Jira 10.x). Error hint if not available."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("list_priority_schemes"))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_admin"},
        annotations={"title": "Get Custom Field Admin", "readOnlyHint": True},
    )
    async def get_custom_field(
        ctx: Context,
        field_id: Annotated[
            str,
            Field(description="Custom field id, e.g. 'customfield_10100'."),
        ],
    ) -> str:
        """Custom field with ALL contexts and project/issue-type scope."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("get_custom_field", id=field_id))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_admin"},
        annotations={"title": "List Custom Field Types", "readOnlyHint": True},
    )
    async def list_custom_field_types(ctx: Context,
        random_string: Annotated[
            str,
            Field(description="Reserved — included to keep a non-empty tool schema for OpenAI-gateway compatibility."),
        ] = "",
    ) -> str:
        """Available custom field types — essential for building admin ТЗ."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("list_custom_field_types"))

    # =====================================================================
    # Insight / Assets (CMDB)
    # =====================================================================

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_assets"},
        annotations={"title": "List Asset Schemas", "readOnlyHint": True},
    )
    async def list_object_schemas(ctx: Context,
        random_string: Annotated[
            str,
            Field(description="Reserved — included to keep a non-empty tool schema for OpenAI-gateway compatibility."),
        ] = "",
    ) -> str:
        """All Insight/Assets object schemas."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("list_object_schemas"))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_assets"},
        annotations={"title": "Get Asset Schema", "readOnlyHint": True},
    )
    async def get_object_schema(
        ctx: Context,
        schema_id: Annotated[str, Field(description="Numeric schema id.")],
    ) -> str:
        """Schema metadata + object-type hierarchy."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("get_object_schema", id=schema_id))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_assets"},
        annotations={"title": "List Asset Object Types", "readOnlyHint": True},
    )
    async def list_object_types(
        ctx: Context,
        schema_id: Annotated[str, Field(description="Schema id.")],
    ) -> str:
        """Object types in the schema — name, parent, object count, abstract flag."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("list_object_types", schemaId=schema_id))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_assets"},
        annotations={"title": "Get Object Type Attributes", "readOnlyHint": True},
    )
    async def get_object_type_attributes(
        ctx: Context,
        object_type_id: Annotated[str, Field(description="Object type id.")],
    ) -> str:
        """All attributes — data type, required, cardinality, reference type for links."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("get_object_type_attributes", id=object_type_id))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_assets"},
        annotations={"title": "AQL Search", "readOnlyHint": True},
    )
    async def aql_search(
        ctx: Context,
        aql: Annotated[
            str,
            Field(
                description=(
                    "AQL expression, e.g. 'objectType = Server', 'Name like \"prod\"', 'Status = Active'."
                )
            ),
        ],
        schema: Annotated[
            str, Field(description="Optional schema id/key to limit scope.")
        ] = "",
        max_results: Annotated[
            str, Field(description="Max results (1..50). Default 25.")
        ] = "25",
    ) -> str:
        """Search Assets objects using AQL. Returns object key, label, type."""
        if not aql.strip():
            return _err("aql is required")
        if len(aql) > MAX_AQL_LENGTH:
            return _err(f"aql too long: {len(aql)} > {MAX_AQL_LENGTH}")
        try:
            mr = max(1, min(int(max_results), 50))
        except (TypeError, ValueError):
            mr = 25
        client = await _get_client(ctx)
        return _fmt(
            client.sr_action("aql_search", schema=schema, aql=aql, maxResults=str(mr))
        )

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_assets"},
        annotations={"title": "Get Asset Object", "readOnlyHint": True},
    )
    async def get_asset_object(
        ctx: Context,
        object_id: Annotated[str, Field(description="Numeric object id.")],
    ) -> str:
        """All attributes with values, referenced objects, object type, timestamps."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("get_asset_object", id=object_id))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_assets"},
        annotations={"title": "List Reference Types", "readOnlyHint": True},
    )
    async def list_reference_types(
        ctx: Context,
        schema_id: Annotated[str, Field(description="Schema id.")],
    ) -> str:
        """Relationship kinds between objects (Dependency, Installed on, Uses, …)."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("list_reference_types", schemaId=schema_id))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_assets"},
        annotations={"title": "List Asset Status Types", "readOnlyHint": True},
    )
    async def list_status_types(
        ctx: Context,
        schema_id: Annotated[str, Field(description="Schema id.")],
    ) -> str:
        """Object lifecycle states (Active, Inactive, Pending) with categories."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("list_status_types", schemaId=schema_id))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_assets"},
        annotations={"title": "List Asset Import Configs", "readOnlyHint": True},
    )
    async def list_import_configs(
        ctx: Context,
        schema_id: Annotated[str, Field(description="Schema id.")],
    ) -> str:
        """LDAP/CSV/DB syncs with cron schedules and last execution — where CMDB data comes from."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("list_import_configs", schemaId=schema_id))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_assets"},
        annotations={"title": "Get Asset Connected Tickets", "readOnlyHint": True},
    )
    async def get_object_connected_tickets(
        ctx: Context,
        object_id: Annotated[str, Field(description="Asset object id.")],
    ) -> str:
        """Jira issues connected to an Assets object — CMDB ↔ issue relationships."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("get_object_connected_tickets", id=object_id))

    # =====================================================================
    # ScriptRunner
    # =====================================================================

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_scriptrunner"},
        annotations={"title": "List ScriptRunner Listeners", "readOnlyHint": True},
    )
    async def list_sr_listeners(
        ctx: Context,
        project: Annotated[
            str,
            Field(description="Optional project key filter (e.g. 'HR')."),
        ] = "",
    ) -> str:
        """Listeners with events, script file, enabled state, projects, inline scripts."""
        client = await _get_client(ctx)
        try:
            data = client.rest_get("/rest/scriptrunner-jira/latest/listeners")
            if isinstance(data, list):
                if project:
                    p = project.upper()
                    data = [
                        listener
                        for listener in data
                        if p in [pk.upper() for pk in (listener.get("projects") or [])]
                        or p in (listener.get("FIELD_NOTES", "") or "").upper()
                        or p in (listener.get("notes", "") or "").upper()
                        or not listener.get("projects")
                    ]
                return _fmt(data)
        except AnalystError as exc:
            logger.info("SR REST listeners unavailable (%s); falling back to Groovy", exc)
        return _fmt(client.sr_action("list_sr_listeners", project=project))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_scriptrunner"},
        annotations={"title": "Get ScriptRunner Listener", "readOnlyHint": True},
    )
    async def get_sr_listener(
        ctx: Context,
        listener_id: Annotated[str, Field(description="Listener id/uuid.")],
    ) -> str:
        """FULL Groovy script + event bindings for a single listener."""
        client = await _get_client(ctx)
        try:
            all_listeners = client.rest_get("/rest/scriptrunner-jira/latest/listeners")
            if isinstance(all_listeners, list):
                for listener in all_listeners:
                    lid = listener.get("id") or listener.get("uuid") or ""
                    if str(lid) == listener_id:
                        return _fmt(listener)
            return _err(f"Listener {listener_id} not found")
        except AnalystError as exc:
            logger.info(
                "SR REST listener fetch failed for id=%s (%s); falling back",
                listener_id,
                exc,
            )
        return _fmt(client.sr_action("get_sr_listener", id=listener_id))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_scriptrunner"},
        annotations={"title": "List ScriptRunner Behaviours", "readOnlyHint": True},
    )
    async def list_sr_behaviours(
        ctx: Context,
        project: Annotated[str, Field(description="Optional project key filter.")] = "",
    ) -> str:
        """Form behaviours — id, name, disabled, field count (no scripts)."""
        client = await _get_client(ctx)
        data = client.sr_action("list_sr_behaviours", project=project)
        if project and isinstance(data, list) and len(data) > 50:
            p = project.upper()
            data = [
                b
                for b in data
                if p in (b.get("name", "") or "").upper()
                or p in (b.get("guideWorkflow", "") or "").upper()
            ]
        return _fmt(data)

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_scriptrunner"},
        annotations={"title": "Get ScriptRunner Behaviour", "readOnlyHint": True},
    )
    async def get_sr_behaviour(
        ctx: Context,
        behaviour_id: Annotated[str, Field(description="Behaviour id.")],
    ) -> str:
        """FULL Groovy per field — server-side validation, initialisers, conditions."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("get_sr_behaviour", id=behaviour_id))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_scriptrunner"},
        annotations={"title": "List ScriptRunner Scripted Fields", "readOnlyHint": True},
    )
    async def list_sr_script_fields(
        ctx: Context,
        project: Annotated[str, Field(description="Optional project key filter.")] = "",
    ) -> str:
        """Scripted fields — field name, template, hasInlineScript, scriptFile path."""
        client = await _get_client(ctx)
        data = client.sr_action("list_sr_script_fields", project=project)
        try:
            sr_fields = client.rest_get("/rest/scriptrunner-jira/latest/scriptfields")
            if isinstance(sr_fields, list) and isinstance(data, list):
                sr_map: dict[str, dict[str, Any]] = {}
                for sf in sr_fields:
                    cf_id = sf.get("customFieldId") or sf.get("fieldId") or ""
                    if cf_id:
                        sr_map[str(cf_id)] = sf
                for item in data:
                    field_id = item.get("id", "")
                    sr_config = sr_map.get(field_id)
                    if sr_config:
                        sfos = (
                            sr_config.get("scriptFileOrScript")
                            or sr_config.get("FIELD_SCRIPT_FILE_OR_SCRIPT")
                            or {}
                        )
                        if isinstance(sfos, dict):
                            if sfos.get("script"):
                                item["hasInlineScript"] = True
                            if sfos.get("scriptFile"):
                                item["scriptFile"] = sfos["scriptFile"]
                        item["template"] = sr_config.get("template", "")
                        item["cacheable"] = sr_config.get("cacheable", "")
        except AnalystError as exc:
            logger.info("SR scriptfields enrichment failed (%s); returning base", exc)
        return _fmt(data)

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_scriptrunner"},
        annotations={"title": "Get ScriptRunner Scripted Field", "readOnlyHint": True},
    )
    async def get_sr_script_field(
        ctx: Context,
        field_id: Annotated[
            str,
            Field(
                description=(
                    "Field id — 'customfield_10123', bare numeric '10123', or field name."
                )
            ),
        ],
    ) -> str:
        """FULL Groovy, template type, caching config, preview issue."""
        client = await _get_client(ctx)
        try:
            all_fields = client.rest_get("/rest/scriptrunner-jira/latest/scriptfields")
            if isinstance(all_fields, list):
                cf_num = field_id.replace("customfield_", "")
                for field in all_fields:
                    cf_id = str(field.get("customFieldId", ""))
                    if cf_id in (cf_num, field_id) or field.get("name") == field_id:
                        return _fmt(field)
            return _err(f"Scripted field {field_id} not found in SR config")
        except AnalystError as exc:
            logger.info(
                "SR REST scriptfield fetch failed for id=%s (%s); falling back",
                field_id,
                exc,
            )
        return _fmt(client.sr_action("get_sr_script_field", id=field_id))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_scriptrunner"},
        annotations={"title": "List ScriptRunner Fragments", "readOnlyHint": True},
    )
    async def list_sr_fragments(ctx: Context,
        random_string: Annotated[
            str,
            Field(description="Reserved — included to keep a non-empty tool schema for OpenAI-gateway compatibility."),
        ] = "",
    ) -> str:
        """Web items, panels, sections, and show/hide conditions injected into the UI."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("list_sr_fragments"))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_scriptrunner"},
        annotations={"title": "List ScriptRunner Jobs", "readOnlyHint": True},
    )
    async def list_sr_jobs(
        ctx: Context,
        project: Annotated[str, Field(description="Optional project key filter.")] = "",
    ) -> str:
        """Scheduled jobs — name, cron, last run, script file, enabled state."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("list_sr_jobs", project=project))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_scriptrunner"},
        annotations={"title": "List ScriptRunner REST Endpoints", "readOnlyHint": True},
    )
    async def list_sr_endpoints(ctx: Context,
        random_string: Annotated[
            str,
            Field(description="Reserved — included to keep a non-empty tool schema for OpenAI-gateway compatibility."),
        ] = "",
    ) -> str:
        """Custom REST endpoints found under JIRA_HOME/scripts — name, method, preview."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("list_sr_endpoints"))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_scriptrunner"},
        annotations={"title": "List ScriptRunner Escalations", "readOnlyHint": True},
    )
    async def list_sr_escalation_services(
        ctx: Context,
        project: Annotated[str, Field(description="Optional project key filter.")] = "",
    ) -> str:
        """JQL-based scheduled rules that auto-transition or modify issues."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("list_sr_escalation_services", project=project))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_scriptrunner"},
        annotations={"title": "Get ScriptRunner Escalation", "readOnlyHint": True},
    )
    async def get_sr_escalation_service(
        ctx: Context,
        service_id: Annotated[str, Field(description="Escalation service id.")],
    ) -> str:
        """Full JQL, cron schedule, transition/script actions, enabled state."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("get_sr_escalation_service", id=service_id))

    # =====================================================================
    # JMWE
    # =====================================================================

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_jmwe"},
        annotations={"title": "List JMWE Event Actions", "readOnlyHint": True},
    )
    async def list_jmwe_event_actions(
        ctx: Context,
        project: Annotated[str, Field(description="Optional project key filter.")] = "",
    ) -> str:
        """JMWE event-based actions — trigger event, project scope, JQL, condition, post-functions."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("list_jmwe_event_actions", project=project))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_jmwe"},
        annotations={"title": "Get JMWE Event Action", "readOnlyHint": True},
    )
    async def get_jmwe_event_action(
        ctx: Context,
        action_id: Annotated[str, Field(description="Event action UUID.")],
    ) -> str:
        """Full config — trigger, scope, JQL, Groovy condition, post-functions with classes + JSON."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("get_jmwe_event_action", id=action_id))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_jmwe"},
        annotations={"title": "List JMWE Shared Actions", "readOnlyHint": True},
    )
    async def list_jmwe_shared_actions(
        ctx: Context,
        type: Annotated[
            str,
            Field(
                description="Filter: 'post-function', 'condition', or 'validator' (substring)."
            ),
        ] = "",
    ) -> str:
        """Reusable post-functions, conditions, validators referenced from workflow transitions."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("list_jmwe_shared_actions", type=type))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_jmwe"},
        annotations={"title": "Get JMWE Shared Action", "readOnlyHint": True},
    )
    async def get_jmwe_shared_action(
        ctx: Context,
        action_id: Annotated[str, Field(description="Shared action id.")],
    ) -> str:
        """All getters from the AO entity — config JSON, inline Groovy, run-as user."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("get_jmwe_shared_action", id=action_id))

    # =====================================================================
    # Structure (ALM Works) + Gantt
    # =====================================================================

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_structure"},
        annotations={"title": "List Structures", "readOnlyHint": True},
    )
    async def list_structures(
        ctx: Context,
        search: Annotated[str, Field(description="Substring filter on name.")] = "",
    ) -> str:
        """Structure plugin hierarchies — id, name, description, owner, archived state."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("list_structures", search=search))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_structure"},
        annotations={"title": "Get Structure", "readOnlyHint": True},
    )
    async def get_structure(
        ctx: Context,
        structure_id: Annotated[str, Field(description="Structure id.")],
    ) -> str:
        """Name, description, owner, row count, generator configuration."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("get_structure", id=structure_id))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_structure"},
        annotations={"title": "List Structure Views", "readOnlyHint": True},
    )
    async def list_structure_views(
        ctx: Context,
        search: Annotated[str, Field(description="Substring filter on name.")] = "",
    ) -> str:
        """Structure views — id, name, owner, shared, column count."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("list_structure_views", search=search))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_structure"},
        annotations={"title": "Get Structure View", "readOnlyHint": True},
    )
    async def get_structure_view(
        ctx: Context,
        view_id: Annotated[str, Field(description="View id.")],
    ) -> str:
        """FULL column config — types, parameters, resolved field names, display modes."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("get_structure_view", id=view_id))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_structure"},
        annotations={"title": "Get Gantt Config", "readOnlyHint": True},
    )
    async def get_gantt_config(
        ctx: Context,
        structure_id: Annotated[str, Field(description="Structure id.")],
    ) -> str:
        """Gantt config — date fields, progress, dependencies, calendar, leveling, baseline."""
        client = await _get_client(ctx)
        try:
            return _fmt(
                client.rest_get(f"/rest/structure-gantt/1.0/configuration/{structure_id}")
            )
        except AnalystError as exc:
            return _err(
                f"Cannot read Gantt config for structure {structure_id}",
                detail=str(exc),
            )

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_structure"},
        annotations={"title": "Get Gantt Schedule", "readOnlyHint": True},
    )
    async def get_gantt_schedule(
        ctx: Context,
        structure_id: Annotated[str, Field(description="Structure id.")],
    ) -> str:
        """Calculated dates, critical path, dependencies, baselines."""
        client = await _get_client(ctx)
        try:
            return _fmt(client.rest_get(f"/rest/structure-gantt/1.0/schedule/{structure_id}"))
        except AnalystError as exc:
            return _err(
                f"Cannot read Gantt schedule for structure {structure_id}",
                detail=str(exc),
            )

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_structure"},
        annotations={"title": "Get Gantt Calendar", "readOnlyHint": True},
    )
    async def get_gantt_calendar(
        ctx: Context,
        structure_id: Annotated[str, Field(description="Structure id.")],
    ) -> str:
        """Working days, holidays, work hours."""
        client = await _get_client(ctx)
        try:
            return _fmt(client.rest_get(f"/rest/structure-gantt/1.0/calendar/{structure_id}"))
        except AnalystError as exc:
            return _err(
                f"Cannot read Gantt calendar for structure {structure_id}",
                detail=str(exc),
            )

    # =====================================================================
    # Audit + System logs
    # =====================================================================

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_logs"},
        annotations={"title": "Get Audit Log", "readOnlyHint": True},
    )
    async def get_audit_log(
        ctx: Context,
        limit: Annotated[int, Field(description="Max records (1..1000).")] = 50,
        offset: Annotated[int, Field(description="Pagination offset.")] = 0,
        from_date: Annotated[
            str, Field(description="ISO date, e.g. '2026-03-01'.")
        ] = "",
        to_date: Annotated[str, Field(description="ISO date.")] = "",
        search: Annotated[str, Field(description="Free-text filter.")] = "",
    ) -> str:
        """Admin audit events — permission changes, scheme edits, user management."""
        client = await _get_client(ctx)
        params: dict[str, Any] = {
            "limit": min(max(limit, 1), 1000),
            "offset": max(offset, 0),
        }
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date
        if search:
            params["searchString"] = search
        return _fmt(client.rest_get("/rest/auditing/1.0/events", **params))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_logs"},
        annotations={"title": "Get System Log", "readOnlyHint": True},
    )
    async def get_system_log(
        ctx: Context,
        lines: Annotated[int, Field(description="Tail size (1..500).")] = 100,
        search: Annotated[
            str, Field(description="Substring filter, e.g. 'ERROR', 'OutOfMemory', 'HR-'.")
        ] = "",
    ) -> str:
        """Tail of atlassian-jira.log for debugging plugin errors and startup issues."""
        client = await _get_client(ctx)
        lines = max(1, min(int(lines), 500))
        return _fmt(client.sr_action("get_system_log", lines=str(lines), search=search))

    # =====================================================================
    # Automation for Jira (A4J)
    # =====================================================================

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_automation"},
        annotations={"title": "List A4J Rules", "readOnlyHint": True},
    )
    async def list_a4j_rules(
        ctx: Context,
        project: Annotated[
            str,
            Field(description="Project key. A4J may require project scope."),
        ] = "",
    ) -> str:
        """List Automation for Jira rules — id, name, state, description."""
        client = await _get_client(ctx)
        if project:
            return _fmt(
                client.rest_get(f"/rest/cb-automation/latest/project/{project}/rule")
            )
        try:
            return _fmt(client.rest_get("/rest/cb-automation/latest/rule"))
        except AnalystError as exc:
            logger.info("A4J global rules endpoint failed (%s)", exc)
            return _err("project parameter required for A4J rules")

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_automation"},
        annotations={"title": "Get A4J Rule", "readOnlyHint": True},
    )
    async def get_a4j_rule(
        ctx: Context,
        rule_id: Annotated[str, Field(description="A4J rule id.")],
        project: Annotated[str, Field(description="Project key (optional).")] = "",
    ) -> str:
        """Full trigger / conditions / actions config for an A4J rule."""
        if not rule_id:
            return _err("rule_id is required")
        client = await _get_client(ctx)
        path = (
            f"/rest/cb-automation/latest/project/{project}/rule/{rule_id}"
            if project
            else f"/rest/cb-automation/latest/rule/{rule_id}"
        )
        return _fmt(client.rest_get(path))

    # =====================================================================
    # Integrations surface — plugins, webhooks, applinks, dark features
    # =====================================================================

    # UPM requires an explicit vendor-specific Accept header or returns HTML.
    # https://developer.atlassian.com/platform/marketplace/registering-apps/
    _UPM_ACCEPT_LIST = "application/vnd.atl.plugins.installed+json"
    _UPM_ACCEPT_PLUGIN = "application/vnd.atl.plugins.plugin+json"

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_integrations"},
        annotations={"title": "List Installed Plugins (UPM)", "readOnlyHint": True},
    )
    async def list_plugins(ctx: Context,
        random_string: Annotated[
            str,
            Field(description="Reserved — included to keep a non-empty tool schema for OpenAI-gateway compatibility."),
        ] = "",
    ) -> str:
        """Installed plugins via Universal Plugin Manager (SYS_ADMIN required)."""
        client = await _get_client(ctx)
        try:
            return _fmt(
                client.rest_get("/rest/plugins/1.0/", accept=_UPM_ACCEPT_LIST)
            )
        except AnalystError as exc:
            return _err(f"list_plugins failed: {exc}", status=exc.status)

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_integrations"},
        annotations={"title": "Get Plugin (UPM)", "readOnlyHint": True},
    )
    async def get_plugin(
        ctx: Context,
        plugin_key: Annotated[
            str,
            Field(
                description=(
                    "Plugin key, e.g. 'com.atlassian.jira.plugins.jira-importers-plugin'."
                )
            ),
        ],
    ) -> str:
        """Single plugin details — UPM ``/rest/plugins/1.0/{key}-key``."""
        client = await _get_client(ctx)
        try:
            return _fmt(
                client.rest_get(
                    f"/rest/plugins/1.0/{plugin_key}-key",
                    accept=_UPM_ACCEPT_PLUGIN,
                )
            )
        except AnalystError as exc:
            return _err(f"get_plugin failed: {exc}", status=exc.status)

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_integrations"},
        annotations={"title": "Get Plugin Modules (UPM)", "readOnlyHint": True},
    )
    async def get_plugin_modules(
        ctx: Context,
        plugin_key: Annotated[str, Field(description="Plugin key.")],
    ) -> str:
        """Enabled/disabled modules for a plugin (completeKey, type, name)."""
        client = await _get_client(ctx)
        try:
            return _fmt(
                client.rest_get(
                    f"/rest/plugins/1.0/{plugin_key}-key/modules",
                    accept=_UPM_ACCEPT_PLUGIN,
                )
            )
        except AnalystError as exc:
            return _err(f"get_plugin_modules failed: {exc}", status=exc.status)

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_integrations"},
        annotations={"title": "List Webhooks", "readOnlyHint": True},
    )
    async def list_webhooks(ctx: Context,
        random_string: Annotated[
            str,
            Field(description="Reserved — included to keep a non-empty tool schema for OpenAI-gateway compatibility."),
        ] = "",
    ) -> str:
        """List instance webhooks.

        Jira ≤ 9.x exposes them at ``/rest/webhooks/1.0/webhook``; Jira ≥ 10.x
        moved the endpoint to ``/rest/jira-webhook/1.0/webhooks``. We try the
        modern path first and fall back to the legacy one, so the tool works
        across supported DC versions. Jira Administrators permission required.
        """
        client = await _get_client(ctx)
        paths = ("/rest/jira-webhook/1.0/webhooks", "/rest/webhooks/1.0/webhook")
        last_err: AnalystError | None = None
        for path in paths:
            try:
                return _fmt(client.rest_get(path))
            except AnalystError as exc:
                last_err = exc
                if exc.status in (404, 405):
                    continue
                return _err(
                    f"list_webhooks failed on {path}: {exc}", status=exc.status
                )
        return _err(
            "list_webhooks: neither the v10+ nor the legacy webhook endpoint "
            "responded on this instance",
            status=last_err.status if last_err else None,
        )

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_integrations"},
        annotations={"title": "List Application Links", "readOnlyHint": True},
    )
    async def list_application_links(ctx: Context,
        random_string: Annotated[
            str,
            Field(description="Reserved — included to keep a non-empty tool schema for OpenAI-gateway compatibility."),
        ] = "",
    ) -> str:
        """Application links to Confluence/Bitbucket/other (admin-only).

        Uses ``/rest/applinks/3.0/applicationlink`` and forces
        ``Accept: application/json`` — the applinks service prefers XML
        by default and will return XML if the client doesn't request JSON.
        """
        client = await _get_client(ctx)
        try:
            return _fmt(
                client.rest_get(
                    "/rest/applinks/3.0/applicationlink",
                    accept="application/json",
                )
            )
        except AnalystError as exc:
            return _err(
                f"list_application_links failed: {exc}", status=exc.status
            )

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_integrations"},
        annotations={"title": "List Dark Features (best-effort)", "readOnlyHint": True},
    )
    async def list_dark_features(ctx: Context,
        random_string: Annotated[
            str,
            Field(description="Reserved — included to keep a non-empty tool schema for OpenAI-gateway compatibility."),
        ] = "",
    ) -> str:
        """Dark-features toggles via ``/rest/internal/1.0/darkFeatures``.

        This is an **internal/private** Atlassian API — the closest thing
        DC exposes for a feature-flags overview. It's read-only and stable
        enough for audits, but Atlassian may change it without notice.
        """
        client = await _get_client(ctx)
        try:
            return _fmt(client.rest_get("/rest/internal/1.0/darkFeatures"))
        except AnalystError as exc:
            return _err(
                "list_dark_features failed — /rest/internal/1.0/darkFeatures "
                "is a private API and may be unavailable on this instance",
                status=exc.status,
                detail=str(exc),
            )

    # =====================================================================
    # Admin additions — my permissions, reindex
    # =====================================================================

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_admin"},
        annotations={"title": "My Permissions", "readOnlyHint": True},
    )
    async def my_permissions(
        ctx: Context,
        project_key: Annotated[
            str,
            Field(
                description=(
                    "Project key to scope the check. Use together with "
                    "issue_key for per-issue permission decisions."
                )
            ),
        ] = "",
        issue_key: Annotated[
            str,
            Field(description="Issue key for per-issue permission scoping."),
        ] = "",
        permissions: Annotated[
            str,
            Field(
                description=(
                    "Optional comma-separated permission keys to filter, "
                    "e.g. 'EDIT_ISSUES,DELETE_ISSUES'."
                )
            ),
        ] = "",
    ) -> str:
        """Check which permissions the authenticated user has on a project or issue.

        Answers "can user X do Y on project Z" without manually cross-referencing
        permission schemes + roles + groups. Backed by
        ``GET /rest/api/2/mypermissions``. DC returns the full list if
        ``permissions`` is omitted; we pass it through for forward-compat with
        Cloud where it's mandatory.
        """
        params: dict[str, Any] = {}
        if project_key:
            params["projectKey"] = project_key
        if issue_key:
            params["issueKey"] = issue_key
        if permissions:
            params["permissions"] = permissions
        client = await _get_client(ctx)
        try:
            return _fmt(client.rest_get("/rest/api/2/mypermissions", **params))
        except AnalystError as exc:
            return _err(f"my_permissions failed: {exc}", status=exc.status)

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_admin"},
        annotations={"title": "Reindex Status", "readOnlyHint": True},
    )
    async def get_reindex_status(ctx: Context,
        random_string: Annotated[
            str,
            Field(description="Reserved — included to keep a non-empty tool schema for OpenAI-gateway compatibility."),
        ] = "",
    ) -> str:
        """Get the current or last Jira reindex progress — is indexing running, stuck, or done.

        Diagnostic for "search results are stale" or "custom fields not
        showing up". Backed by ``GET /rest/api/2/reindex``.

        Returns a ``no_reindex_recorded`` sentinel instead of a raw 404 when
        the instance has never reindexed, so callers can tell "never
        reindexed" from "permission denied".
        """
        client = await _get_client(ctx)
        try:
            return _fmt(client.rest_get("/rest/api/2/reindex"))
        except AnalystError as exc:
            if exc.status == 404:
                return _fmt(
                    {
                        "status": "no_reindex_recorded",
                        "note": (
                            "/rest/api/2/reindex returned 404 — this instance "
                            "has no stored reindex progress (likely never "
                            "reindexed, or progress was cleared)."
                        ),
                    }
                )
            return _err(f"get_reindex_status failed: {exc}", status=exc.status)

    # =====================================================================
    # Issue deep-inspection — votes, remote links, attachment content
    # =====================================================================

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_issue_inspect"},
        annotations={"title": "Get Issue Votes", "readOnlyHint": True},
    )
    async def get_issue_votes(
        ctx: Context,
        issue_key: Annotated[str, Field(description="Issue key, e.g. 'HR-123'.")],
    ) -> str:
        """Total votes and (where visible) voter list for an issue.

        ``voters`` is populated only when the caller has the *View Voters
        and Watchers* project permission — an empty array does not imply
        no voters.
        """
        client = await _get_client(ctx)
        try:
            return _fmt(client.rest_get(f"/rest/api/2/issue/{issue_key}/votes"))
        except AnalystError as exc:
            return _err(f"get_issue_votes failed: {exc}", status=exc.status)

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_issue_inspect"},
        annotations={"title": "Get Issue Remote Links", "readOnlyHint": True},
    )
    async def get_issue_remotelinks(
        ctx: Context,
        issue_key: Annotated[str, Field(description="Issue key.")],
        global_id: Annotated[
            str,
            Field(
                description="Optional global-id filter (matches a single link)."
            ),
        ] = "",
    ) -> str:
        """External links attached to an issue — ``/rest/api/2/issue/{key}/remotelink``."""
        client = await _get_client(ctx)
        params: dict[str, Any] = {}
        if global_id:
            params["globalId"] = global_id
        try:
            return _fmt(
                client.rest_get(
                    f"/rest/api/2/issue/{issue_key}/remotelink", **params
                )
            )
        except AnalystError as exc:
            return _err(
                f"get_issue_remotelinks failed: {exc}", status=exc.status
            )

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_issue_inspect"},
        annotations={"title": "Get Attachment Content", "readOnlyHint": True},
    )
    async def get_attachment_content(
        ctx: Context,
        attachment_id: Annotated[
            str, Field(description="Numeric attachment id (from list_attachments).")
        ],
    ) -> list[TextContent | ImageContent]:
        """Download an attachment and return it inline for analysis.

        Behaviour by MIME type:

        * **Image** (png/jpeg/gif/webp) up to 5 MB → MCP ImageContent that
          Claude can see natively (screenshots, diagrams, image logs).
        * **Text** (text/*, json, xml, csv, yaml, sql, md, common source
          extensions) → inlined UTF-8 text, truncated at 50 000 characters.
        * **Other binary** up to 200 KB → base64 blob inside a TextContent
          for programmatic use.
        * **Too large** → metadata + download URL so the caller can stream
          the file out-of-band.
        """
        client = await _get_client(ctx)
        try:
            meta = client.rest_get(f"/rest/api/2/attachment/{attachment_id}")
        except AnalystError as exc:
            return [
                TextContent(
                    type="text",
                    text=_err(
                        f"get_attachment_content metadata failed: {exc}",
                        status=exc.status,
                    ),
                )
            ]
        filename: str = meta.get("filename", "") or ""
        size: int = int(meta.get("size") or 0)
        mime: str = (meta.get("mimeType") or "").lower()
        content_url: str = meta.get("content") or ""
        is_image, resolved_mime = is_image_attachment(mime, filename)
        visible_mime = resolved_mime in _VISIBLE_IMAGE_MIMES

        if is_image and size > _MAX_IMAGE_BYTES:
            return [
                TextContent(
                    type="text",
                    text=_fmt(
                        {
                            "id": attachment_id,
                            "filename": filename,
                            "size": size,
                            "mimeType": resolved_mime,
                            "warning": (
                                f"Image too large ({size} > {_MAX_IMAGE_BYTES}). "
                                "Use get_attachment_thumbnail or the URL below."
                            ),
                            "contentUrl": content_url,
                        }
                    ),
                )
            ]
        if not is_image and size > _MAX_TEXT_DOWNLOAD_BYTES:
            return [
                TextContent(
                    type="text",
                    text=_fmt(
                        {
                            "id": attachment_id,
                            "filename": filename,
                            "size": size,
                            "mimeType": resolved_mime,
                            "warning": (
                                f"File too large ({size} > "
                                f"{_MAX_TEXT_DOWNLOAD_BYTES}). Use the URL."
                            ),
                            "contentUrl": content_url,
                        }
                    ),
                )
            ]

        try:
            data = client.fetch_bytes(
                content_url,
                max_bytes=_MAX_IMAGE_BYTES if is_image else _MAX_TEXT_DOWNLOAD_BYTES,
            )
        except AnalystError as exc:
            return [
                TextContent(
                    type="text",
                    text=_err(
                        f"attachment download failed: {exc}",
                        status=exc.status,
                        id=attachment_id,
                        filename=filename,
                    ),
                )
            ]

        if is_image and visible_mime:
            return [
                TextContent(
                    type="text",
                    text=_fmt(
                        {
                            "id": attachment_id,
                            "filename": filename,
                            "size": size,
                            "mimeType": resolved_mime,
                        }
                    ),
                ),
                ImageContent(
                    type="image",
                    data=base64.b64encode(data).decode("ascii"),
                    mimeType=resolved_mime,
                ),
            ]
        if is_image:
            return [
                TextContent(
                    type="text",
                    text=_fmt(
                        {
                            "id": attachment_id,
                            "filename": filename,
                            "size": size,
                            "mimeType": resolved_mime,
                            "hint": (
                                f"MIME {resolved_mime} is not natively rendered; "
                                "returning base64."
                            ),
                            "contentBase64": base64.b64encode(data).decode("ascii"),
                        }
                    ),
                )
            ]

        if _looks_like_text(resolved_mime, filename):
            try:
                text = data.decode("utf-8", errors="replace")
            except Exception:  # noqa: BLE001 — last-ditch fallback
                text = None
            if text is not None:
                return [
                    TextContent(
                        type="text",
                        text=_fmt(
                            {
                                "id": attachment_id,
                                "filename": filename,
                                "mimeType": resolved_mime,
                                "content": text[:_MAX_TEXT_CHARS],
                                "truncated": len(text) > _MAX_TEXT_CHARS,
                                "originalLength": len(text),
                            }
                        ),
                    )
                ]

        if size <= _MAX_BINARY_BASE64_BYTES:
            return [
                TextContent(
                    type="text",
                    text=_fmt(
                        {
                            "id": attachment_id,
                            "filename": filename,
                            "size": size,
                            "mimeType": resolved_mime,
                            "contentBase64": base64.b64encode(data).decode("ascii"),
                        }
                    ),
                )
            ]
        return [
            TextContent(
                type="text",
                text=_fmt(
                    {
                        "id": attachment_id,
                        "filename": filename,
                        "size": size,
                        "mimeType": resolved_mime,
                        "hint": "Binary too large for inline base64. Use URL.",
                        "contentUrl": content_url,
                    }
                ),
            )
        ]

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_issue_inspect"},
        annotations={"title": "Get Attachment Thumbnail", "readOnlyHint": True},
    )
    async def get_attachment_thumbnail(
        ctx: Context,
        attachment_id: Annotated[str, Field(description="Numeric attachment id.")],
    ) -> list[TextContent | ImageContent]:
        """Fetch the server-generated thumbnail for an image attachment.

        Cheaper than :func:`get_attachment_content` for large images — useful
        when scanning many attachments to find the right one. Falls back to a
        text-only metadata response when the server didn't generate a
        thumbnail (non-image, or generation failed).
        """
        client = await _get_client(ctx)
        try:
            meta = client.rest_get(f"/rest/api/2/attachment/{attachment_id}")
        except AnalystError as exc:
            return [
                TextContent(
                    type="text",
                    text=_err(
                        f"get_attachment_thumbnail metadata failed: {exc}",
                        status=exc.status,
                    ),
                )
            ]
        thumb_url = meta.get("thumbnail")
        if not thumb_url:
            return [
                TextContent(
                    type="text",
                    text=_fmt(
                        {
                            "id": attachment_id,
                            "filename": meta.get("filename"),
                            "mimeType": meta.get("mimeType"),
                            "error": (
                                "no thumbnail available (non-image, or server "
                                "did not generate one)."
                            ),
                        }
                    ),
                )
            ]
        try:
            data = client.fetch_bytes(thumb_url, max_bytes=_MAX_IMAGE_BYTES)
        except AnalystError as exc:
            return [
                TextContent(
                    type="text",
                    text=_err(
                        f"thumbnail download failed: {exc}",
                        status=exc.status,
                    ),
                )
            ]
        return [
            TextContent(
                type="text",
                text=_fmt(
                    {
                        "id": attachment_id,
                        "filename": meta.get("filename"),
                        "mimeType": meta.get("mimeType"),
                        "thumbnail": True,
                    }
                ),
            ),
            ImageContent(
                type="image",
                data=base64.b64encode(data).decode("ascii"),
                mimeType="image/png",
            ),
        ]

    # =====================================================================
    # DVCS + Git Integration inspection
    #
    # Three REST surfaces feed the "Git info panel" on a Jira issue:
    #
    #   1. Native Jira DVCS — ``/rest/bitbucket/1.0/`` (legacy name despite
    #      supporting GitHub/GitLab too). Owns the "DVCS accounts" admin
    #      page. Paginated singular noun (``organization``, not the plural
    #      form sometimes seen in community posts).
    #   2. BigBrassBand "Git Integration for Jira" — ``/rest/gitplugin/1.0/``
    #      (Marketplace app id 4984). NOT ``jgitplugin`` — that is a
    #      different, older, unrelated plugin.
    #   3. ``/rest/dev-status/1.0/`` — the API that actually renders the
    #      dev panel on the issue view, aggregating data from whichever
    #      provider plugin feeds it. Its ``applicationType`` is
    #      case-sensitive — ``stash`` for Bitbucket Server, ``GitHub``
    #      for github.com, ``githube`` for Enterprise, ``gitlab`` for
    #      GitLab via DVCS. The ``/summary`` endpoint returns the exact
    #      provider keys ("byInstanceType") that should then be passed
    #      to ``/detail``, so we drive the loop dynamically instead of
    #      hard-coding.
    # =====================================================================

    # ---- native DVCS ---------------------------------------------------

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_dvcs"},
        annotations={"title": "List DVCS Organizations", "readOnlyHint": True},
    )
    async def list_dvcs_organizations(
        ctx: Context,
        page: Annotated[int, Field(description="1-based page number.")] = 1,
        page_size: Annotated[
            int, Field(description="Page size (1..100).")
        ] = 50,
    ) -> str:
        """List connected DVCS organizations (GitHub / GitLab / Bitbucket).

        Shows which Git providers are wired to Jira, their type and OAuth key.
        Paginated — pagination is not optional on DC. Backed by
        ``GET /rest/bitbucket/1.0/organization/page``.
        """
        client = await _get_client(ctx)
        try:
            return _fmt(
                client.rest_get(
                    "/rest/bitbucket/1.0/organization/page",
                    pagenum=max(1, int(page)),
                    pagesize=max(1, min(int(page_size), 100)),
                )
            )
        except AnalystError as exc:
            return _err(
                f"list_dvcs_organizations failed: {exc}", status=exc.status
            )

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_dvcs"},
        annotations={"title": "Get DVCS Organization", "readOnlyHint": True},
    )
    async def get_dvcs_organization(
        ctx: Context,
        organization_id: Annotated[str, Field(description="Organization id.")],
    ) -> str:
        """Get full configuration of one DVCS organization.

        Returns name, baseUrl, type, autolinkNewRepos, smartcommitsOnNewRepos,
        defaultGroupsSlugs, principal. Backed by
        ``GET /rest/bitbucket/1.0/organization/{id}``.
        """
        client = await _get_client(ctx)
        try:
            return _fmt(
                client.rest_get(
                    f"/rest/bitbucket/1.0/organization/{organization_id}"
                )
            )
        except AnalystError as exc:
            return _err(
                f"get_dvcs_organization failed: {exc}", status=exc.status
            )

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_dvcs"},
        annotations={"title": "List DVCS Repositories", "readOnlyHint": True},
    )
    async def list_dvcs_repositories(
        ctx: Context,
        organization_id: Annotated[str, Field(description="Organization id.")],
    ) -> str:
        """List repositories synced from a DVCS organization.

        Per-repo: slug, linked, smartcommitsEnabled, lastCommitDate,
        activityLastUpdatedTimestamp. Backed by
        ``GET /rest/bitbucket/1.0/organization/{id}/repository`` (note the
        documented singular ``/repository``).
        """
        client = await _get_client(ctx)
        try:
            return _fmt(
                client.rest_get(
                    f"/rest/bitbucket/1.0/organization/{organization_id}/repository"
                )
            )
        except AnalystError as exc:
            return _err(
                f"list_dvcs_repositories failed: {exc}", status=exc.status
            )

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_dvcs"},
        annotations={"title": "Get DVCS Repository", "readOnlyHint": True},
    )
    async def get_dvcs_repository(
        ctx: Context,
        repository_id: Annotated[str, Field(description="Repository id.")],
    ) -> str:
        """Get one DVCS-linked repository by id — slug, sync settings, activity timestamps.

        Backed by ``GET /rest/bitbucket/1.0/repository/{id}``.
        """
        client = await _get_client(ctx)
        try:
            return _fmt(
                client.rest_get(f"/rest/bitbucket/1.0/repository/{repository_id}")
            )
        except AnalystError as exc:
            return _err(
                f"get_dvcs_repository failed: {exc}", status=exc.status
            )

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_dvcs"},
        annotations={"title": "DVCS Sync Audit", "readOnlyHint": True},
    )
    async def get_dvcs_sync_audit(
        ctx: Context,
        repository_id: Annotated[
            str,
            Field(
                description=(
                    "Repository id to audit. Omit to read the instance-wide "
                    "audit log via ``/audit/repository/all``."
                )
            ),
        ] = "",
    ) -> str:
        """Diagnose why the Git dev panel isn't updating — DVCS sync audit log.

        The canonical "last sync time + error message" endpoint: firstRequestDate,
        lastActivityDate, totalChangesetCount, flightTimeMs and — on failure —
        exception + message + status (``OK`` / ``SYNC_ERROR`` / ``SYNC_WARNING``).
        Backed by ``GET /rest/bitbucket/1.0/audit/repository/{id|all}``.

        A common mistake is to hit ``/repository/{id}/sync`` for status —
        that path is the resync trigger, not a status read.
        """
        client = await _get_client(ctx)
        path = (
            f"/rest/bitbucket/1.0/audit/repository/{repository_id}"
            if repository_id
            else "/rest/bitbucket/1.0/audit/repository/all"
        )
        try:
            return _fmt(client.rest_get(path))
        except AnalystError as exc:
            return _err(
                f"get_dvcs_sync_audit failed: {exc}", status=exc.status
            )

    # ---- BigBrassBand Git Integration for Jira (GIJ) ----------------

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_dvcs"},
        annotations={"title": "GIJ: Issue Commits", "readOnlyHint": True},
    )
    async def list_gij_issue_commits(
        ctx: Context,
        issue_key: Annotated[str, Field(description="Issue key, e.g. 'HR-123'.")],
        show_files: Annotated[
            bool,
            Field(
                description="If true, each commit also lists changed files with change type."
            ),
        ] = False,
    ) -> str:
        """List Git commits linked to a Jira issue via the BigBrassBand plugin.

        Useful for "which commits reference this ticket" — richer than
        dev-status (full SHAs, author emails, messages). Respects issue-view
        permission. Backed by ``GET /rest/gitplugin/1.0/issues/{key}/commits``.
        """
        client = await _get_client(ctx)
        try:
            return _fmt(
                client.rest_get(
                    f"/rest/gitplugin/1.0/issues/{issue_key}/commits",
                    showfiles="true" if show_files else "false",
                )
            )
        except AnalystError as exc:
            return _err(
                f"list_gij_issue_commits failed: {exc}", status=exc.status
            )

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_dvcs"},
        annotations={"title": "GIJ: Issue Branches", "readOnlyHint": True},
    )
    async def list_gij_issue_branches(
        ctx: Context,
        issue_key: Annotated[
            str,
            Field(
                description=(
                    "Issue key. Omit to list ALL indexed branches across the "
                    "instance — large response, prefer a specific issue."
                )
            ),
        ] = "",
    ) -> str:
        """List Git branches linked to a Jira issue via the BigBrassBand plugin.

        Useful when the dev panel misses a feature branch developers are
        working on. Backed by
        ``GET /rest/gitplugin/1.0/issues/branches?key=<issueKey>``.
        """
        client = await _get_client(ctx)
        try:
            params: dict[str, Any] = {}
            if issue_key:
                params["key"] = issue_key
            return _fmt(
                client.rest_get("/rest/gitplugin/1.0/issues/branches", **params)
            )
        except AnalystError as exc:
            return _err(
                f"list_gij_issue_branches failed: {exc}", status=exc.status
            )

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_dvcs"},
        annotations={"title": "GIJ: Commit Reverse Lookup", "readOnlyHint": True},
    )
    async def get_gij_commit_issues(
        ctx: Context,
        commit_sha: Annotated[
            str,
            Field(description="Full or shortened commit SHA as indexed by GIJ."),
        ],
    ) -> str:
        """Find which Jira issues a commit is linked to — reverse commit→issue lookup.

        Answers "why is this commit showing up on ticket X" or "is this commit
        linked anywhere". Backed by
        ``GET /rest/gitplugin/1.0/commit/{sha}/issues``.
        """
        client = await _get_client(ctx)
        try:
            return _fmt(
                client.rest_get(f"/rest/gitplugin/1.0/commit/{commit_sha}/issues")
            )
        except AnalystError as exc:
            return _err(
                f"get_gij_commit_issues failed: {exc}", status=exc.status
            )

    # ---- dev-status (raw panel data) --------------------------------

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_dvcs"},
        annotations={"title": "Dev Panel Summary", "readOnlyHint": True},
    )
    async def get_issue_dev_summary(
        ctx: Context,
        issue_id: Annotated[
            str,
            Field(
                description=(
                    "Numeric issue id (not key). Use the upstream "
                    "``jira_get_issue`` tool to resolve a key to its id first."
                )
            ),
        ],
    ) -> str:
        """Summary of the Git dev panel on an issue — counts of PRs/MRs, branches, commits, repositories.

        Use this FIRST for any Git-panel question. The response also
        contains ``byInstanceType`` keys that are the valid
        ``applicationType`` strings for ``get_issue_dev_detail`` — drive
        the follow-up loop from those keys instead of hard-coding provider
        names. Backed by ``GET /rest/dev-status/1.0/issue/summary?issueId=<id>``.
        """
        if not issue_id.isdigit():
            return _err(
                "issue_id must be a numeric issue id. Resolve a key via "
                "/rest/api/2/issue/{key}?fields=id first."
            )
        client = await _get_client(ctx)
        try:
            return _fmt(
                client.rest_get(
                    "/rest/dev-status/1.0/issue/summary", issueId=issue_id
                )
            )
        except AnalystError as exc:
            return _err(
                f"get_issue_dev_summary failed: {exc}", status=exc.status
            )

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_dvcs"},
        annotations={"title": "Dev Panel Detail", "readOnlyHint": True},
    )
    async def get_issue_dev_detail(
        ctx: Context,
        issue_id: Annotated[str, Field(description="Numeric issue id.")],
        application_type: Annotated[
            str,
            Field(
                description=(
                    "Case-sensitive provider key from ``get_issue_dev_summary`` "
                    "(``stash`` for Bitbucket Server/DC, ``GitHub``, ``githube`` "
                    "for GitHub Enterprise, ``gitlab`` via DVCS, ``bitbucket`` "
                    "for Bitbucket Cloud)."
                )
            ),
        ],
        data_type: Annotated[
            str,
            Field(
                description=(
                    "One of ``repository`` (commits nested under repos), "
                    "``branch`` (branches + linked PRs), or ``pullrequest`` "
                    "(PRs at top level). Singular — not ``pullrequests``."
                )
            ),
        ],
    ) -> str:
        """Get the full Git dev-panel detail for an issue — raw commits / branches / PRs.

        The UI-equivalent payload the issue view renders. Structure:
        ``{detail:[{_instance, repositories[{commits[]}], branches[],
        pullRequests[]}]}``. Backed by ``GET /rest/dev-status/1.0/issue/detail``.
        """
        if not issue_id.isdigit():
            return _err("issue_id must be a numeric issue id.")
        if data_type not in ("repository", "branch", "pullrequest"):
            return _err(
                "data_type must be 'repository', 'branch', or 'pullrequest' (singular)"
            )
        if not application_type:
            return _err("application_type is required (case-sensitive provider key)")
        client = await _get_client(ctx)
        try:
            return _fmt(
                client.rest_get(
                    "/rest/dev-status/1.0/issue/detail",
                    issueId=issue_id,
                    applicationType=application_type,
                    dataType=data_type,
                )
            )
        except AnalystError as exc:
            return _err(
                f"get_issue_dev_detail failed: {exc}", status=exc.status
            )

    # =====================================================================
    # Entity properties — the "JSON blob" storage that many plugins use
    # instead of their own REST (JXL, Jira Automation, ScriptRunner,
    # assorted integrations). Jira's own REST exposes per-scope CRUD, so
    # we get read access to all of them through a tiny surface.
    #
    #   * Project:  GET /rest/api/2/project/{keyOrId}/properties
    #   * Issue:    GET /rest/api/2/issue/{keyOrId}/properties
    #   * User:     GET /rest/api/2/user/properties?username=X  (DC)
    #
    # A GET on the collection path returns the list of property *keys*;
    # a GET on ``/{collection}/{key}`` returns the JSON value.
    # Auth: whatever the user has on the scope (Browse Project / Browse
    # Issue / the user themselves).  See
    # https://developer.atlassian.com/server/jira/platform/entity-properties/
    # =====================================================================

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_properties"},
        annotations={"title": "List Project Properties", "readOnlyHint": True},
    )
    async def list_project_properties(
        ctx: Context,
        project_key: Annotated[str, Field(description="Project key or id.")],
    ) -> str:
        """Keys of all entity properties on a project — the first step when
        discovering plugin-stored configuration (e.g. JXL sheets,
        Automation-for-Jira rules, custom integration state). Vendors don't
        publish their own key names; enumerate here first, then read with
        ``get_project_property``."""
        client = await _get_client(ctx)
        try:
            return _fmt(
                client.rest_get(f"/rest/api/2/project/{project_key}/properties")
            )
        except AnalystError as exc:
            return _err(
                f"list_project_properties failed: {exc}", status=exc.status
            )

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_properties"},
        annotations={"title": "Get Project Property", "readOnlyHint": True},
    )
    async def get_project_property(
        ctx: Context,
        project_key: Annotated[str, Field(description="Project key or id.")],
        property_key: Annotated[
            str, Field(description="Property key (from list_project_properties).")
        ],
    ) -> str:
        """Full JSON value of a single project property. The schema inside
        is vendor-private (JXL, Automation, etc. each define their own)
        and may change between plugin versions — treat as opaque."""
        client = await _get_client(ctx)
        try:
            return _fmt(
                client.rest_get(
                    f"/rest/api/2/project/{project_key}/properties/{property_key}"
                )
            )
        except AnalystError as exc:
            return _err(
                f"get_project_property failed: {exc}", status=exc.status
            )

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_properties"},
        annotations={"title": "List Issue Properties", "readOnlyHint": True},
    )
    async def list_issue_properties(
        ctx: Context,
        issue_key: Annotated[str, Field(description="Issue key or id.")],
    ) -> str:
        """Keys of all entity properties on an issue. Useful for debugging
        per-issue plugin state (e.g. assorted scripting caches, sprint
        metadata written by agile plugins)."""
        client = await _get_client(ctx)
        try:
            return _fmt(
                client.rest_get(f"/rest/api/2/issue/{issue_key}/properties")
            )
        except AnalystError as exc:
            return _err(
                f"list_issue_properties failed: {exc}", status=exc.status
            )

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_properties"},
        annotations={"title": "Get Issue Property", "readOnlyHint": True},
    )
    async def get_issue_property(
        ctx: Context,
        issue_key: Annotated[str, Field(description="Issue key or id.")],
        property_key: Annotated[str, Field(description="Property key.")],
    ) -> str:
        """Full JSON of one issue property."""
        client = await _get_client(ctx)
        try:
            return _fmt(
                client.rest_get(
                    f"/rest/api/2/issue/{issue_key}/properties/{property_key}"
                )
            )
        except AnalystError as exc:
            return _err(
                f"get_issue_property failed: {exc}", status=exc.status
            )

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_properties"},
        annotations={"title": "List User Properties", "readOnlyHint": True},
    )
    async def list_user_properties(
        ctx: Context,
        username: Annotated[
            str,
            Field(
                description=(
                    "DC username. User-properties endpoint is DC-only — "
                    "Cloud uses accountId instead."
                )
            ),
        ],
    ) -> str:
        """Keys of all per-user properties. Some plugins store personal
        preferences there (e.g. JXL may keep private sheets here rather
        than on a project)."""
        if not username:
            return _err("username is required")
        client = await _get_client(ctx)
        try:
            return _fmt(
                client.rest_get(
                    "/rest/api/2/user/properties", username=username
                )
            )
        except AnalystError as exc:
            return _err(
                f"list_user_properties failed: {exc}", status=exc.status
            )

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_properties"},
        annotations={"title": "Get User Property", "readOnlyHint": True},
    )
    async def get_user_property(
        ctx: Context,
        username: Annotated[str, Field(description="DC username.")],
        property_key: Annotated[str, Field(description="Property key.")],
    ) -> str:
        """Full JSON of one user property."""
        if not username:
            return _err("username is required")
        client = await _get_client(ctx)
        try:
            return _fmt(
                client.rest_get(
                    f"/rest/api/2/user/properties/{property_key}",
                    username=username,
                )
            )
        except AnalystError as exc:
            return _err(
                f"get_user_property failed: {exc}", status=exc.status
            )

    # =====================================================================
    # Appfire / SaaSJet "Time to SLA" (Marketplace 1211843) — /rest/sla/1.0/
    #
    # The plugin's namespace is confirmed by Appfire's public DC docs
    # (appfire.atlassian.net/wiki/spaces/TTS/). Exact leaf paths were not
    # available in machine-readable form at the time of porting; the paths
    # below follow the most widely-cited patterns from Appfire/SaaSJet
    # blog posts and support articles. If a call returns 404, fall back
    # to the Postman collection linked from the Appfire docs.
    # =====================================================================

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_sla"},
        annotations={"title": "List SLA Definitions", "readOnlyHint": True},
    )
    async def list_sla_definitions(ctx: Context,
        random_string: Annotated[
            str,
            Field(description="Reserved — included to keep a non-empty tool schema for OpenAI-gateway compatibility."),
        ] = "",
    ) -> str:
        """List all SLA definitions configured by the Time to SLA plugin.

        Each definition: id, name, JQL scope, goals, calendar id. Admin-only
        in most configurations. Backed by ``GET /rest/sla/1.0/slas`` with
        automatic fallback to the older ``/rest/sla/1.0/definitions`` path
        on 404.
        """
        client = await _get_client(ctx)
        try:
            return _fmt(client.rest_get("/rest/sla/1.0/slas"))
        except AnalystError as exc:
            if exc.status == 404:
                try:
                    return _fmt(client.rest_get("/rest/sla/1.0/definitions"))
                except AnalystError as exc2:
                    return _err(
                        "list_sla_definitions failed on both known leaf "
                        "paths (/slas and /definitions)",
                        status=exc2.status,
                        detail=str(exc2),
                    )
            return _err(
                f"list_sla_definitions failed: {exc}", status=exc.status
            )

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_sla"},
        annotations={"title": "List SLA Calendars", "readOnlyHint": True},
    )
    async def list_sla_calendars(ctx: Context,
        random_string: Annotated[
            str,
            Field(description="Reserved — included to keep a non-empty tool schema for OpenAI-gateway compatibility."),
        ] = "",
    ) -> str:
        """List work calendars used for SLA calculations — working days, hours, holidays.

        Backed by ``GET /rest/sla/1.0/calendars`` with automatic fallback
        to ``/rest/sla/1.0/slas/calendars`` on 404 (older plugin layout).
        """
        client = await _get_client(ctx)
        try:
            return _fmt(client.rest_get("/rest/sla/1.0/calendars"))
        except AnalystError as exc:
            if exc.status == 404:
                try:
                    return _fmt(client.rest_get("/rest/sla/1.0/slas/calendars"))
                except AnalystError as exc2:
                    return _err(
                        "list_sla_calendars failed on both known leaf paths",
                        status=exc2.status,
                        detail=str(exc2),
                    )
            return _err(f"list_sla_calendars failed: {exc}", status=exc.status)

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_sla"},
        annotations={"title": "Search SLA Status by JQL", "readOnlyHint": True},
    )
    async def search_sla_status(
        ctx: Context,
        jql: Annotated[
            str,
            Field(description="JQL selecting issues whose SLA status you want."),
        ],
        start_at: Annotated[int, Field(description="Pagination start (0-based).")] = 0,
        max_results: Annotated[
            int, Field(description="Page size (1..100 per plugin docs).")
        ] = 50,
    ) -> str:
        """Per-issue SLA status across a JQL result set.

        Returns each issue with its SLAs (elapsed / remaining / paused /
        breached / startDate / targetDate / stopDate / calendarId). The
        most valuable analyst endpoint of this plugin — answers "which
        tickets are breached" and "which SLAs are close to breach" in a
        single call.

        If this 404s, the instance may expose the endpoint as
        ``/rest/sla/1.0/slaSearch``. Try that manually.
        """
        if not jql.strip():
            return _err("jql is required")
        params = {
            "jql": jql,
            "startAt": max(0, int(start_at)),
            "maxResults": max(1, min(int(max_results), 100)),
        }
        client = await _get_client(ctx)
        try:
            return _fmt(client.rest_get("/rest/sla/1.0/search", **params))
        except AnalystError as exc:
            if exc.status == 404:
                try:
                    return _fmt(
                        client.rest_get("/rest/sla/1.0/slaSearch", **params)
                    )
                except AnalystError as exc2:
                    return _err(
                        "search_sla_status failed on both known leaf paths",
                        status=exc2.status,
                        detail=str(exc2),
                    )
            return _err(f"search_sla_status failed: {exc}", status=exc.status)

    # =====================================================================
    # OBSS "Timepiece — Time in Status for Jira" (Marketplace 1211756)
    # Public REST at /rest/tis/report/1.0/ — well-documented:
    # https://documentation.obss.tech/timepiece-time-in-status-for-jira-data-center/
    #
    # The plugin's legacy /api/list was deprecated after August 2025 when
    # Atlassian's JQL search API changed; we target the modern /api/list2
    # only, which uses cursor-paging and supports up to 1000 issues/page.
    # =====================================================================

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_time_in_status"},
        annotations={"title": "Get Time-in-Status for Issue", "readOnlyHint": True},
    )
    async def get_issue_time_in_status(
        ctx: Context,
        issue_key: Annotated[str, Field(description="Issue key, e.g. 'HR-123'.")],
        columns_by: Annotated[
            str,
            Field(
                description=(
                    "Breakdown axis: 'statuses' (default), 'assignees', "
                    "'groups', or a custom-field id for custom-breakdowns."
                )
            ),
        ] = "statuses",
        calendar: Annotated[
            str,
            Field(
                description=(
                    "Optional work-calendar id (from ``list_tis_calendars``). "
                    "Omit for 24×7."
                )
            ),
        ] = "",
        view_format: Annotated[
            str,
            Field(
                description=(
                    "'duration' (e.g. '2d 3h'), 'decimal' (hours), or "
                    "'raw-seconds'. Default 'raw-seconds' — easier to "
                    "post-process programmatically."
                )
            ),
        ] = "raw-seconds",
    ) -> str:
        """Get time-in-status breakdown for one issue — how long it sat in each status.

        Returns seconds per status (or per assignee / group / custom-field
        bucket depending on ``columns_by``). Any authenticated user with
        Browse permission can call. Backed by
        ``GET /rest/tis/report/1.0/api/issue``.
        """
        params: dict[str, Any] = {
            "issueKey": issue_key,
            "columnsBy": columns_by,
            "viewFormat": view_format,
        }
        if calendar:
            params["calendar"] = calendar
        client = await _get_client(ctx)
        try:
            return _fmt(
                client.rest_get("/rest/tis/report/1.0/api/issue", **params)
            )
        except AnalystError as exc:
            return _err(
                f"get_issue_time_in_status failed: {exc}", status=exc.status
            )

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_time_in_status"},
        annotations={"title": "Search Time-in-Status by JQL", "readOnlyHint": True},
    )
    async def search_time_in_status(
        ctx: Context,
        jql: Annotated[
            str,
            Field(description="JQL selecting target issues (custom JQL filter mode)."),
        ],
        output_type: Annotated[
            str,
            Field(
                description=(
                    "'list' = per-issue breakdown, 'average' = average per "
                    "status across the set, 'sum' = totals across the set."
                )
            ),
        ] = "list",
        columns_by: Annotated[
            str,
            Field(description="'statuses', 'assignees', 'groups', or custom-field id."),
        ] = "statuses",
        page_size: Annotated[
            int,
            Field(description="Cursor page size (1..1000). Default 200."),
        ] = 200,
        next_page_token: Annotated[
            str,
            Field(
                description=(
                    "Cursor from a previous call's ``nextPageToken``. Leave "
                    "empty for the first page."
                )
            ),
        ] = "",
        view_format: Annotated[
            str, Field(description="'duration', 'decimal', or 'raw-seconds'.")
        ] = "raw-seconds",
        calendar: Annotated[
            str, Field(description="Optional work-calendar id.")
        ] = "",
    ) -> str:
        """Run a bulk time-in-status report across a JQL — per-issue, average, or sum.

        Answers "how long do tickets sit in Code Review on average" or
        "team throughput by status this quarter". Three output modes:

        * ``list`` — per-issue seconds-in-each-status table
        * ``average`` — average per status across the JQL set
        * ``sum`` — total across the set

        Backed by ``GET /rest/tis/report/1.0/api/list2`` (cursor-paginated,
        ~20× faster than the deprecated ``/api/list`` which stopped working
        after Atlassian's Aug 2025 JQL search API change).
        """
        if not jql.strip():
            return _err("jql is required")
        if output_type not in ("list", "average", "sum"):
            return _err("output_type must be 'list', 'average', or 'sum'")
        params: dict[str, Any] = {
            "filterType": "customjql",
            "customjql": jql,
            "outputType": output_type,
            "columnsBy": columns_by,
            "pageSize": max(1, min(int(page_size), 1000)),
            "viewFormat": view_format,
        }
        if next_page_token:
            params["nextPageToken"] = next_page_token
        if calendar:
            params["calendar"] = calendar
        client = await _get_client(ctx)
        try:
            return _fmt(
                client.rest_get("/rest/tis/report/1.0/api/list2", **params)
            )
        except AnalystError as exc:
            return _err(
                f"search_time_in_status failed: {exc}", status=exc.status
            )

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_time_in_status"},
        annotations={"title": "List TIS Calendars", "readOnlyHint": True},
    )
    async def list_tis_calendars(ctx: Context,
        random_string: Annotated[
            str,
            Field(description="Reserved — included to keep a non-empty tool schema for OpenAI-gateway compatibility."),
        ] = "",
    ) -> str:
        """List work calendars configured for Time-in-Status reports.

        Returns calendar ids + working days/hours/holidays. Accepted by
        ``get_issue_time_in_status`` / ``search_time_in_status`` as the
        ``calendar`` param. Backed by ``GET /rest/tis/report/1.0/data/calendars``.
        """
        client = await _get_client(ctx)
        try:
            return _fmt(client.rest_get("/rest/tis/report/1.0/data/calendars"))
        except AnalystError as exc:
            return _err(
                f"list_tis_calendars failed: {exc}", status=exc.status
            )

    # =====================================================================
    # MetaInf "Email This Issue" (JETI, Marketplace 4977) — /rest/jeti/1.0/
    #
    # Vendor docs: https://docs.meta-inf.hu/email-this-issue/
    # Public REST only covers the audit log and queue metrics; template /
    # notification-rule / handler CRUD is exposed via OSGi API only and
    # would require ScriptRunner. For analyst needs ("why did this issue
    # get an email", "is the queue backing up") the REST surface is enough.
    # =====================================================================

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_email"},
        annotations={"title": "Search JETI Email Audit", "readOnlyHint": True},
    )
    async def search_jeti_audit_log(
        ctx: Context,
        issue_key: Annotated[
            str,
            Field(description="Filter by Jira issue key (e.g. 'HR-123')."),
        ] = "",
        recipient: Annotated[
            str,
            Field(description="Filter by recipient email address or username."),
        ] = "",
        template: Annotated[
            str, Field(description="Filter by email-template name or id.")
        ] = "",
        from_date: Annotated[
            str,
            Field(description="ISO date ('2026-03-01') — audit records from this date."),
        ] = "",
        to_date: Annotated[
            str, Field(description="ISO date — audit records up to this date.")
        ] = "",
        limit: Annotated[
            int, Field(description="Max records to return (1..1000).")
        ] = 100,
    ) -> str:
        """Find who received what email for a Jira issue and when.

        Audit log of emails sent by the Email This Issue (JETI) plugin.
        Filters: issue key, recipient, template, date range, limit. Results
        are filtered by the plugin to what the caller has permission to see
        (issue browse at minimum). Backed by
        ``GET /rest/jeti/1.0/email/query``.
        """
        params: dict[str, Any] = {"limit": max(1, min(int(limit), 1000))}
        if issue_key:
            params["issueKey"] = issue_key
        if recipient:
            params["recipient"] = recipient
        if template:
            params["template"] = template
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date
        client = await _get_client(ctx)
        try:
            return _fmt(client.rest_get("/rest/jeti/1.0/email/query", **params))
        except AnalystError as exc:
            return _err(
                f"search_jeti_audit_log failed: {exc}", status=exc.status
            )

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_email"},
        annotations={"title": "JETI Audit Count", "readOnlyHint": True},
    )
    async def get_jeti_audit_count(
        ctx: Context,
        issue_key: Annotated[str, Field(description="Optional issue key.")] = "",
        recipient: Annotated[str, Field(description="Optional recipient.")] = "",
        template: Annotated[str, Field(description="Optional template.")] = "",
        from_date: Annotated[str, Field(description="ISO date.")] = "",
        to_date: Annotated[str, Field(description="ISO date.")] = "",
    ) -> str:
        """Count JETI audit-log entries matching a filter — cheap sanity check.

        Run this before a heavy ``search_jeti_audit_log`` if you only need
        "how many emails went out". Backed by ``GET /rest/jeti/1.0/email/stat``.
        """
        params: dict[str, Any] = {}
        if issue_key:
            params["issueKey"] = issue_key
        if recipient:
            params["recipient"] = recipient
        if template:
            params["template"] = template
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date
        client = await _get_client(ctx)
        try:
            return _fmt(client.rest_get("/rest/jeti/1.0/email/stat", **params))
        except AnalystError as exc:
            return _err(
                f"get_jeti_audit_count failed: {exc}", status=exc.status
            )

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_email"},
        annotations={"title": "JETI Outgoing Mail Queue", "readOnlyHint": True},
    )
    async def get_jeti_outgoing_queue_stats(ctx: Context,
        random_string: Annotated[
            str,
            Field(description="Reserved — included to keep a non-empty tool schema for OpenAI-gateway compatibility."),
        ] = "",
    ) -> str:
        """Diagnose "JETI emails aren't arriving" — outbound mail queue stats.

        Shows queue depth and processing lag. JETI v9.0.0+ only. Backed by
        ``GET /rest/jeti/1.0/outgoingMailQueue/statistic``.
        """
        client = await _get_client(ctx)
        try:
            return _fmt(
                client.rest_get("/rest/jeti/1.0/outgoingMailQueue/statistic")
            )
        except AnalystError as exc:
            return _err(
                f"get_jeti_outgoing_queue_stats failed: {exc}",
                status=exc.status,
                hint=(
                    "Requires JETI v9.0.0+. Older versions return 404 on "
                    "queue endpoints."
                ),
            )

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_email"},
        annotations={"title": "JETI Incoming Mail Queue", "readOnlyHint": True},
    )
    async def get_jeti_incoming_queue_stats(ctx: Context,
        random_string: Annotated[
            str,
            Field(description="Reserved — included to keep a non-empty tool schema for OpenAI-gateway compatibility."),
        ] = "",
    ) -> str:
        """Diagnose inbound JETI mail handlers — are they processing or stuck.

        Queue depth and lag for incoming mail. JETI v9.0.0+ only. Backed by
        ``GET /rest/jeti/1.0/incomingMailQueue/statistic``.
        """
        client = await _get_client(ctx)
        try:
            return _fmt(
                client.rest_get("/rest/jeti/1.0/incomingMailQueue/statistic")
            )
        except AnalystError as exc:
            return _err(
                f"get_jeti_incoming_queue_stats failed: {exc}",
                status=exc.status,
                hint="Requires JETI v9.0.0+.",
            )

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_email"},
        annotations={"title": "JETI Mail Generation Queue", "readOnlyHint": True},
    )
    async def get_jeti_generation_queue_stats(ctx: Context,
        random_string: Annotated[
            str,
            Field(description="Reserved — included to keep a non-empty tool schema for OpenAI-gateway compatibility."),
        ] = "",
    ) -> str:
        """Spot bottlenecks between JETI event firing and email send — template-rendering queue.

        Diagnostic for "event fired but no email yet". JETI v9.0.0+ only.
        Backed by ``GET /rest/jeti/1.0/mailGenerationQueue/statistic``.
        """
        client = await _get_client(ctx)
        try:
            return _fmt(
                client.rest_get("/rest/jeti/1.0/mailGenerationQueue/statistic")
            )
        except AnalystError as exc:
            return _err(
                f"get_jeti_generation_queue_stats failed: {exc}",
                status=exc.status,
                hint="Requires JETI v9.0.0+.",
            )
