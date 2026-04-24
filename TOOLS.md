# Tools reference — mcp-atlassian-analyst

113 read-only deep-inspection tools for Jira Data Center admins, on top of 51 inherited upstream tools.

Auto-generated from tool registrations on `feat/jira-analyst-toolset-v4`.
Source: [`src/mcp_atlassian/servers/jira_analyst.py`](src/mcp_atlassian/servers/jira_analyst.py).

**162 tools total across 28 toolsets.**

Tool names below include the `jira_` / `confluence_` prefix that FastMCP mounts automatically.

Kind legend: **read** = read-only · **write** = state-changing (disabled under `READ_ONLY_MODE`) · **write (destructive)** = carries the MCP `destructiveHint` annotation so clients prompt before executing.

---

## Fork-specific toolsets

### `jira_analyst_admin` — Jira DC admin configuration (SR-backed + REST) (45)

| Tool | Kind | Description |
|---|---|---|
| `jira_get_application_properties` | read | Global settings: time tracking, attachment limits, voting, watching, subtasks. |
| `jira_get_cluster_info` | read | DC cluster: is clustered, node count, each node ID/state/IP, current node flag. |
| `jira_get_custom_field` | read | Custom field with ALL contexts and project/issue-type scope. |
| `jira_get_field_config_scheme` | read | Issue type → field configuration mappings. |
| `jira_get_field_configuration` | read | Per-field settings: hidden, required, renderer, description override. |
| `jira_get_group_members` | read | Group members — username, display name, email, active flag. |
| `jira_get_issue_security_scheme` | read | All security levels with their access grants (users, groups, roles). |
| `jira_get_notification_scheme` | read | All event-to-recipient mappings for the scheme. |
| `jira_get_permission_scheme` | read | All permission grants (permission key, grant type, grant value). |
| `jira_get_project_config` | read | Full project admin view — all assigned schemes, roles with members, components, versions. |
| `jira_get_project_role_members` | read | Users and groups assigned to a role in the given project. |
| `jira_get_reindex_status` | read | ``GET /rest/api/2/reindex`` — current/last reindex progress. |
| `jira_get_screen` | read | Screen tabs with their fields (id, name, position). |
| `jira_get_server_info` | read | Jira version, build number, base URL, title. |
| `jira_get_user` | read | Display name, email, active, groups, application roles (Software/JSM/Core). |
| `jira_get_workflow` | read | Get workflow structure — steps with linked statuses, global actions, transitions. |
| `jira_get_workflow_scheme` | read | Default workflow and issue type → workflow mappings. |
| `jira_get_workflow_transition` | read | Conditions tree, validators, pre/post-functions with class names and parameters. |
| `jira_get_workflow_xml` | read | Raw OSWorkflow XML — for deep inspection, migration, or diffing. |
| `jira_list_application_roles` | read | License tiers with seat usage — critical for capacity audits. |
| `jira_list_custom_field_types` | read | Available custom field types — essential for building admin ТЗ. |
| `jira_list_dashboards` | read | All shared dashboards — name, owner, favourite count, system default. |
| `jira_list_event_types` | read | All event types — maps event IDs in notification schemes to human-readable names. |
| `jira_list_field_config_schemes` | read | Field-config schemes with associated projects. |
| `jira_list_field_configurations` | read | Field configurations — id, name, isDefault, field count. |
| `jira_list_global_permissions` | read | Who has SYSTEM_ADMIN, ADMINISTER, USE, BULK_CHANGE, etc. |
| `jira_list_groups` | read | List all groups with member counts. |
| `jira_list_issue_link_types` | read | All link types — name, inward/outward descriptions. |
| `jira_list_issue_security_schemes` | read | All issue security schemes with associated project keys. |
| `jira_list_issue_type_schemes` | read | Default issue type, mapped types, associated projects. |
| `jira_list_issue_type_screen_schemes` | read | Maps issue types to screen schemes. |
| `jira_list_issue_types` | read | All issue types — id, name, description, isSubtask, icon. |
| `jira_list_notification_schemes` | read | List all notification schemes with associated project keys. |
| `jira_list_permission_schemes` | read | List all permission schemes with associated project keys. |
| `jira_list_priority_schemes` | read | Priority schemes (Jira 10.x). Error hint if not available. |
| `jira_list_project_categories` | read | Project categories — used to group projects. |
| `jira_list_project_roles` | read | All project roles — id, name, description. |
| `jira_list_projects` | read | Projects with key, name, lead, category, assigned permission/workflow schemes. |
| `jira_list_reference_data` | read | All statuses (with categories), priorities, resolutions. |
| `jira_list_screen_schemes` | read | Maps operations (Create/Edit/View) to screens. |
| `jira_list_screens` | read | List all field screens — id, name, description, tab count. |
| `jira_list_shared_filters` | read | All shared filters — name, JQL, owner, favourite count. |
| `jira_list_workflow_schemes` | read | List all workflow schemes with associated project keys. |
| `jira_list_workflows` | read | List all Jira workflows with step counts and last-updated dates. |
| `jira_my_permissions` | read | ``GET /rest/api/2/mypermissions`` — resolves the effective permissions |

### `jira_analyst_scriptrunner` — ScriptRunner inspection (full Groovy source) (11)

| Tool | Kind | Description |
|---|---|---|
| `jira_get_sr_behaviour` | read | FULL Groovy per field — server-side validation, initialisers, conditions. |
| `jira_get_sr_escalation_service` | read | Full JQL, cron schedule, transition/script actions, enabled state. |
| `jira_get_sr_listener` | read | FULL Groovy script + event bindings for a single listener. |
| `jira_get_sr_script_field` | read | FULL Groovy, template type, caching config, preview issue. |
| `jira_list_sr_behaviours` | read | Form behaviours — id, name, disabled, field count (no scripts). |
| `jira_list_sr_endpoints` | read | Custom REST endpoints found under JIRA_HOME/scripts — name, method, preview. |
| `jira_list_sr_escalation_services` | read | JQL-based scheduled rules that auto-transition or modify issues. |
| `jira_list_sr_fragments` | read | Web items, panels, sections, and show/hide conditions injected into the UI. |
| `jira_list_sr_jobs` | read | Scheduled jobs — name, cron, last run, script file, enabled state. |
| `jira_list_sr_listeners` | read | Listeners with events, script file, enabled state, projects, inline scripts. |
| `jira_list_sr_script_fields` | read | Scripted fields — field name, template, hasInlineScript, scriptFile path. |

### `jira_analyst_jmwe` — JMWE inspection (4)

| Tool | Kind | Description |
|---|---|---|
| `jira_get_jmwe_event_action` | read | Full config — trigger, scope, JQL, Groovy condition, post-functions with classes + JSON. |
| `jira_get_jmwe_shared_action` | read | All getters from the AO entity — config JSON, inline Groovy, run-as user. |
| `jira_list_jmwe_event_actions` | read | JMWE event-based actions — trigger event, project scope, JQL, condition, post-functions. |
| `jira_list_jmwe_shared_actions` | read | Reusable post-functions, conditions, validators referenced from workflow transitions. |

### `jira_analyst_structure` — ALM Works Structure + Gantt (SR) (7)

| Tool | Kind | Description |
|---|---|---|
| `jira_get_gantt_calendar` | read | Working days, holidays, work hours. |
| `jira_get_gantt_config` | read | Gantt config — date fields, progress, dependencies, calendar, leveling, baseline. |
| `jira_get_gantt_schedule` | read | Calculated dates, critical path, dependencies, baselines. |
| `jira_get_structure` | read | Name, description, owner, row count, generator configuration. |
| `jira_get_structure_view` | read | FULL column config — types, parameters, resolved field names, display modes. |
| `jira_list_structure_views` | read | Structure views — id, name, owner, shared, column count. |
| `jira_list_structures` | read | Structure plugin hierarchies — id, name, description, owner, archived state. |

### `jira_analyst_assets` — Insight/Assets CMDB (read) (10)

| Tool | Kind | Description |
|---|---|---|
| `jira_aql_search` | read | Search Assets objects using AQL. Returns object key, label, type. |
| `jira_get_asset_object` | read | All attributes with values, referenced objects, object type, timestamps. |
| `jira_get_object_connected_tickets` | read | Jira issues connected to an Assets object — CMDB ↔ issue relationships. |
| `jira_get_object_schema` | read | Schema metadata + object-type hierarchy. |
| `jira_get_object_type_attributes` | read | All attributes — data type, required, cardinality, reference type for links. |
| `jira_list_import_configs` | read | LDAP/CSV/DB syncs with cron schedules and last execution — where CMDB data comes from. |
| `jira_list_object_schemas` | read | All Insight/Assets object schemas. |
| `jira_list_object_types` | read | Object types in the schema — name, parent, object count, abstract flag. |
| `jira_list_reference_types` | read | Relationship kinds between objects (Dependency, Installed on, Uses, …). |
| `jira_list_status_types` | read | Object lifecycle states (Active, Inactive, Pending) with categories. |

### `jira_analyst_automation` — Automation for Jira (2)

| Tool | Kind | Description |
|---|---|---|
| `jira_get_a4j_rule` | read | Full trigger / conditions / actions config for an A4J rule. |
| `jira_list_a4j_rules` | read | List Automation for Jira rules — id, name, state, description. |

### `jira_analyst_logs` — Audit + system logs (2)

| Tool | Kind | Description |
|---|---|---|
| `jira_get_audit_log` | read | Admin audit events — permission changes, scheme edits, user management. |
| `jira_get_system_log` | read | Tail of atlassian-jira.log for debugging plugin errors and startup issues. |

### `jira_analyst_integrations` — Integration surface (plugins, webhooks, applinks) (6)

| Tool | Kind | Description |
|---|---|---|
| `jira_get_plugin` | read | Single plugin details — UPM ``/rest/plugins/1.0/{key}-key``. |
| `jira_get_plugin_modules` | read | Enabled/disabled modules for a plugin (completeKey, type, name). |
| `jira_list_application_links` | read | Application links to Confluence/Bitbucket/other (admin-only). |
| `jira_list_dark_features` | read | Dark-features toggles via ``/rest/internal/1.0/darkFeatures``. |
| `jira_list_plugins` | read | Installed plugins via Universal Plugin Manager (SYS_ADMIN required). |
| `jira_list_webhooks` | read | List instance webhooks. |

### `jira_analyst_issue_inspect` — Deep issue inspection (4)

| Tool | Kind | Description |
|---|---|---|
| `jira_get_attachment_content` | read | Download an attachment and return it inline for analysis. |
| `jira_get_attachment_thumbnail` | read | Fetch the server-generated thumbnail for an image attachment. |
| `jira_get_issue_remotelinks` | read | External links attached to an issue — ``/rest/api/2/issue/{key}/remotelink``. |
| `jira_get_issue_votes` | read | Total votes and (where visible) voter list for an issue. |

### `jira_analyst_dvcs` — DVCS + Git Integration + dev-status (10)

| Tool | Kind | Description |
|---|---|---|
| `jira_get_dvcs_organization` | read | ``GET /rest/bitbucket/1.0/organization/{id}`` — org detail: |
| `jira_get_dvcs_repository` | read | ``GET /rest/bitbucket/1.0/repository/{id}`` — single repo detail. |
| `jira_get_dvcs_sync_audit` | read | ``GET /rest/bitbucket/1.0/audit/repository/{id\|all}`` — this |
| `jira_get_gij_commit_issues` | read | ``GET /rest/gitplugin/1.0/commit/{sha}/issues`` — reverse |
| `jira_get_issue_dev_detail` | read | ``GET /rest/dev-status/1.0/issue/detail`` — raw dev-panel payload |
| `jira_get_issue_dev_summary` | read | ``GET /rest/dev-status/1.0/issue/summary?issueId=<id>`` — counts |
| `jira_list_dvcs_organizations` | read | ``GET /rest/bitbucket/1.0/organization/page`` — connected |
| `jira_list_dvcs_repositories` | read | ``GET /rest/bitbucket/1.0/organization/{id}/repository`` — |
| `jira_list_gij_issue_branches` | read | ``GET /rest/gitplugin/1.0/issues/branches?key=<issueKey>`` — |
| `jira_list_gij_issue_commits` | read | ``GET /rest/gitplugin/1.0/issues/{key}/commits`` — commits |

### `jira_analyst_properties` — Entity properties (projects/issues/users) (6)

| Tool | Kind | Description |
|---|---|---|
| `jira_get_issue_property` | read | Full JSON of one issue property. |
| `jira_get_project_property` | read | Full JSON value of a single project property. The schema inside |
| `jira_get_user_property` | read | Full JSON of one user property. |
| `jira_list_issue_properties` | read | Keys of all entity properties on an issue. Useful for debugging |
| `jira_list_project_properties` | read | Keys of all entity properties on a project — the first step when |
| `jira_list_user_properties` | read | Keys of all per-user properties. Some plugins store personal |

### `jira_analyst_sla` — Appfire/SaaSJet Time to SLA (3)

| Tool | Kind | Description |
|---|---|---|
| `jira_list_sla_calendars` | read | ``GET /rest/sla/1.0/calendars`` — work schedules backing SLA |
| `jira_list_sla_definitions` | read | ``GET /rest/sla/1.0/slas`` — every SLA definition on the instance |
| `jira_search_sla_status` | read | Per-issue SLA status across a JQL result set. |

### `jira_analyst_time_in_status` — OBSS Timepiece — Time in Status (3)

| Tool | Kind | Description |
|---|---|---|
| `jira_get_issue_time_in_status` | read | ``GET /rest/tis/report/1.0/api/issue`` — seconds spent in each |
| `jira_list_tis_calendars` | read | ``GET /rest/tis/report/1.0/data/calendars`` — work calendars |
| `jira_search_time_in_status` | read | ``GET /rest/tis/report/1.0/api/list2`` (cursor-paginated, ~20× |

---

## Upstream toolsets (inherited from `sooperset/mcp-atlassian`)

Listed for completeness — this fork does not modify these tools.

### `jira_agile` (7)

| Tool | Kind | Description |
|---|---|---|
| `jira_add_issues_to_sprint` | write | Add issues to a Jira sprint. |
| `jira_create_sprint` | write (destructive) | Create Jira sprint for a board. |
| `jira_get_agile_boards` | read | Get jira agile boards by name, project key, or type. |
| `jira_get_board_issues` | read | Get all issues linked to a specific board filtered by JQL. |
| `jira_get_sprint_issues` | read | Get jira issues from sprint. |
| `jira_get_sprints_from_board` | read | Get jira sprints from board by state. |
| `jira_update_sprint` | write (destructive) | Update jira sprint. |

### `jira_attachments` (2)

| Tool | Kind | Description |
|---|---|---|
| `jira_download_attachments` | read | Download attachments from a Jira issue. |
| `jira_get_issue_images` | read | Get all images attached to a Jira issue as inline image content. |

### `jira_comments` (2)

| Tool | Kind | Description |
|---|---|---|
| `jira_add_comment` | write (destructive) | Add a comment to a Jira issue. |
| `jira_edit_comment` | write (destructive) | Edit an existing comment on a Jira issue. |

### `jira_development` (2)

| Tool | Kind | Description |
|---|---|---|
| `jira_get_issue_development_info` | read | Get development information (PRs, commits, branches) linked to a Jira issue. |
| `jira_get_issues_development_info` | read | Get development information for multiple Jira issues. |

### `jira_fields` (2)

| Tool | Kind | Description |
|---|---|---|
| `jira_get_field_options` | read | Get allowed option values for a custom field. |
| `jira_search_fields` | read | Search Jira fields by keyword with fuzzy match. |

### `jira_forms` (3)

| Tool | Kind | Description |
|---|---|---|
| `jira_get_issue_proforma_forms` | read | Get all ProForma forms associated with a Jira issue. |
| `jira_get_proforma_form_details` | read | Get detailed information about a specific ProForma form. |
| `jira_update_proforma_form_answers` | write (destructive) | Update form field answers using the Jira Forms REST API. |

### `jira_issues` (8)

| Tool | Kind | Description |
|---|---|---|
| `jira_batch_create_issues` | write (destructive) | Create multiple Jira issues in a batch. |
| `jira_batch_get_changelogs` | read | Get changelogs for multiple Jira issues (Cloud only). |
| `jira_create_issue` | write (destructive) | Create a new Jira issue with optional Epic link or parent for subtasks. |
| `jira_delete_issue` | write (destructive) | Delete an existing Jira issue. |
| `jira_get_issue` | read | Get details of a specific Jira issue including its Epic links and relationship information. |
| `jira_get_project_issues` | read | Get all issues for a specific Jira project. |
| `jira_search` | read | Search Jira issues using JQL (Jira Query Language). |
| `jira_update_issue` | write (destructive) | Update an existing Jira issue including changing status, adding Epic links, updating fields, etc. |

### `jira_links` (5)

| Tool | Kind | Description |
|---|---|---|
| `jira_create_issue_link` | write (destructive) | Create a link between two Jira issues. |
| `jira_create_remote_issue_link` | write (destructive) | Create a remote issue link (web link or Confluence link) for a Jira issue. |
| `jira_get_link_types` | read | Get all available issue link types. |
| `jira_link_to_epic` | write (destructive) | Link an existing issue to an epic. |
| `jira_remove_issue_link` | write (destructive) | Remove a link between two Jira issues. |

### `jira_metrics` (2)

| Tool | Kind | Description |
|---|---|---|
| `jira_get_issue_dates` | read | Get date information and status transition history for a Jira issue. |
| `jira_get_issue_sla` | read | Calculate SLA metrics for a Jira issue. |

### `jira_projects` (5)

| Tool | Kind | Description |
|---|---|---|
| `jira_batch_create_versions` | write (destructive) | Batch create multiple versions in a Jira project. |
| `jira_create_version` | write (destructive) | Create a new fix version in a Jira project. |
| `jira_get_all_projects` | read | Get all Jira projects accessible to the current user. |
| `jira_get_project_components` | read | Get all components for a specific Jira project. |
| `jira_get_project_versions` | read | Get all fix versions for a specific Jira project. |

### `jira_service_desk` (3)

| Tool | Kind | Description |
|---|---|---|
| `jira_get_queue_issues` | read | Get issues from a Jira Service Desk queue. |
| `jira_get_service_desk_for_project` | read | Get the Jira Service Desk associated with a project key. |
| `jira_get_service_desk_queues` | read | Get queues for a Jira Service Desk. |

### `jira_transitions` (2)

| Tool | Kind | Description |
|---|---|---|
| `jira_get_transitions` | read | Get available status transitions for a Jira issue. |
| `jira_transition_issue` | write (destructive) | Transition a Jira issue to a new status. |

### `jira_users` (1)

| Tool | Kind | Description |
|---|---|---|
| `jira_get_user_profile` | read | Retrieve profile information for a specific Jira user. |

### `jira_watchers` (3)

| Tool | Kind | Description |
|---|---|---|
| `jira_add_watcher` | write | Add a user as a watcher to a Jira issue. |
| `jira_get_issue_watchers` | read | Get the list of watchers for a Jira issue. |
| `jira_remove_watcher` | write | Remove a user from watching a Jira issue. |

### `jira_worklog` (2)

| Tool | Kind | Description |
|---|---|---|
| `jira_add_worklog` | write (destructive) | Add a worklog entry to a Jira issue. |
| `jira_get_worklog` | read | Get worklog entries for a Jira issue. |
