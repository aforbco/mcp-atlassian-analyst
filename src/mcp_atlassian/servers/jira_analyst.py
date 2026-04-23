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

import json
import logging
from typing import Annotated, Any

from fastmcp import Context
from pydantic import Field

from mcp_atlassian.jira.analyst.client import AnalystClient, AnalystError
from mcp_atlassian.servers.dependencies import get_jira_fetcher

logger = logging.getLogger("mcp-atlassian.servers.jira_analyst")


MAX_AQL_LENGTH = 2000


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
    async def list_permission_schemes(ctx: Context) -> str:
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
    async def list_notification_schemes(ctx: Context) -> str:
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
    async def list_workflow_schemes(ctx: Context) -> str:
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
    async def list_project_roles(ctx: Context) -> str:
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
    async def list_application_roles(ctx: Context) -> str:
        """License tiers with seat usage — critical for capacity audits."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("list_application_roles"))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_admin"},
        annotations={"title": "List Issue Types", "readOnlyHint": True},
    )
    async def list_issue_types(ctx: Context) -> str:
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
    async def list_reference_data(ctx: Context) -> str:
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
    async def list_issue_link_types(ctx: Context) -> str:
        """All link types — name, inward/outward descriptions."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("list_issue_link_types"))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_admin"},
        annotations={"title": "List Issue Security Schemes", "readOnlyHint": True},
    )
    async def list_issue_security_schemes(ctx: Context) -> str:
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
    async def get_server_info(ctx: Context) -> str:
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
    async def list_project_categories(ctx: Context) -> str:
        """Project categories — used to group projects."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("list_project_categories"))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_admin"},
        annotations={"title": "List Event Types", "readOnlyHint": True},
    )
    async def list_event_types(ctx: Context) -> str:
        """All event types — maps event IDs in notification schemes to human-readable names."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("list_event_types"))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_admin"},
        annotations={"title": "List Global Permissions", "readOnlyHint": True},
    )
    async def list_global_permissions(ctx: Context) -> str:
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
    async def get_cluster_info(ctx: Context) -> str:
        """DC cluster: is clustered, node count, each node ID/state/IP, current node flag."""
        client = await _get_client(ctx)
        return _fmt(client.sr_action("get_cluster_info"))

    @jira_mcp.tool(
        tags={"jira", "read", "toolset:jira_analyst_admin"},
        annotations={"title": "List Priority Schemes", "readOnlyHint": True},
    )
    async def list_priority_schemes(ctx: Context) -> str:
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
    async def list_custom_field_types(ctx: Context) -> str:
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
    async def list_object_schemas(ctx: Context) -> str:
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
    async def list_sr_fragments(ctx: Context) -> str:
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
    async def list_sr_endpoints(ctx: Context) -> str:
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
