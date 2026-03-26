# Azure AI Foundry — Diagnostic Logging via Azure Policy

## Table of Contents

- [Overview](#overview)
- [Policy Enforcement Concepts](#policy-enforcement-concepts)
  - [Azure Policy Lifecycle](#azure-policy-lifecycle)
  - [DeployIfNotExists (DINE) Effect](#deployifnotexists-dine-effect)
  - [Remediation Task Mechanics](#remediation-task-mechanics)
- [Policy Definition](#policy-definition)
- [Deployment Steps — Azure Portal](#deployment-steps--azure-portal)
- [Deployment Steps — Azure CLI / PowerShell](#deployment-steps--azure-cli--powershell)
- [Remediation Troubleshooting](#remediation-troubleshooting)
- [Appendix: Role Definition ID Reference](#appendix-role-definition-id-reference)

---

## Overview

This document describes how to use **Azure Policy** to automatically enable **Diagnostic Settings** for all Azure AI Foundry (Cognitive Services) resources, sending logs and metrics to:

1. **Log Analytics Workspace** — for real-time querying and monitoring
2. **Storage Account (Blob)** — for long-term retention and compliance

---

## Policy Enforcement Concepts

### Azure Policy Lifecycle

```
Create Policy Definition
        ↓
Assign Policy (specify scope: Subscription / Management Group)
        ↓
Compliance Evaluation (automatic or manual trigger)
        ↓
Mark resources as Compliant / Non-Compliant
        ↓
Remediation Task (fix Non-Compliant resources)
```

| Phase | Description |
|-------|-------------|
| **Policy Definition** | Defines the rules: what resource types to check, what conditions constitute compliance, and what action to take when non-compliant |
| **Policy Assignment** | Binds a Definition to a specific scope (Subscription / Resource Group / Management Group) |
| **Compliance Evaluation** | Azure automatically evaluates compliance approximately every 24 hours, or when resources are created/updated |
| **Remediation** | Fixes existing non-compliant resources (requires manually creating a Remediation Task) |

### DeployIfNotExists (DINE) Effect

`DeployIfNotExists` is the effect used by this policy. It works as follows:

1. **New resources**: When a new Cognitive Services resource is created, the Policy Engine automatically checks the `existenceCondition`. If the diagnostic setting does not exist or does not meet the conditions, it triggers an ARM deployment to create one.
2. **Existing resources**: Already existing resources are **not** automatically remediated — they require a **Remediation Task**.

```
Resource Created / Updated
        ↓
Policy Engine checks existenceCondition
        ↓
  ┌─────────────────────┐
  │ Condition satisfied? │
  └──────────┬──────────┘
        Yes  │  No
         ↓       ↓
    Compliant   Trigger ARM Deployment
                (auto-create Diagnostic Setting)
```

### Remediation Task Mechanics

Remediation Tasks support two Resource Discovery Modes:

| Mode | Description | When to Use |
|------|-------------|-------------|
| `ExistingNonCompliant` | Only remediates resources **already marked as non-compliant** in the compliance cache | Standard use; compliance data is stable |
| `ReEvaluateCompliance` | Re-evaluates all resources first, then remediates any that are non-compliant | After updating a Policy Definition or Assignment; when compliance cache may be stale |

> **Important**: If you have recently updated a Policy Definition or Assignment, you **must** use `ReEvaluateCompliance` mode. Otherwise, the remediation task may show **0 resources selected** because the compliance cache has not been refreshed yet.

---

## Policy Definition

The following Policy Definition uses `DeployIfNotExists` to automatically create diagnostic settings on all Cognitive Services resources, sending logs and metrics to both Log Analytics and Blob Storage:

```json
{
  "displayName": "poc-foundrylogging-cogsvcs",
  "policyType": "Custom",
  "mode": "All",
  "description": "Deploy diagnostic settings to Log Analytics and Blob Storage for Azure AI services (Cognitive Services accounts).",
  "metadata": {
    "category": "foundry-custom",
    "version": "1.1.0"
  },
  "parameters": {
    "logAnalyticsWorkspaceId": {
      "type": "String",
      "metadata": {
        "displayName": "Log Analytics Workspace Resource ID",
        "description": "Resource ID of the Log Analytics workspace to send diagnostics to."
      }
    },
    "diagnosticSettingName": {
      "type": "String",
      "defaultValue": "setByPolicy",
      "metadata": {
        "displayName": "Diagnostic setting name",
        "description": "Name of the diagnostic setting to create."
      }
    },
    "storageAccountId": {
      "type": "String",
      "metadata": {
        "displayName": "Storage Account Resource ID",
        "description": "Resource ID of the Storage Account to send diagnostics to (blob storage)."
      }
    },
    "effect": {
      "type": "String",
      "allowedValues": ["DeployIfNotExists", "AuditIfNotExists", "Disabled"],
      "defaultValue": "DeployIfNotExists",
      "metadata": {
        "displayName": "Effect",
        "description": "Enable or disable the execution of the policy."
      }
    }
  },
  "policyRule": {
    "if": {
      "field": "type",
      "equals": "Microsoft.CognitiveServices/accounts"
    },
    "then": {
      "effect": "[parameters('effect')]",
      "details": {
        "type": "Microsoft.Insights/diagnosticSettings",
        "name": "[parameters('diagnosticSettingName')]",
        "existenceCondition": {
          "allOf": [
            {
              "field": "Microsoft.Insights/diagnosticSettings/workspaceId",
              "equals": "[parameters('logAnalyticsWorkspaceId')]"
            },
            {
              "field": "Microsoft.Insights/diagnosticSettings/logs[*].enabled",
              "equals": "true"
            },
            {
              "field": "Microsoft.Insights/diagnosticSettings/metrics[*].enabled",
              "equals": "true"
            },
            {
              "field": "Microsoft.Insights/diagnosticSettings/storageAccountId",
              "equals": "[parameters('storageAccountId')]"
            }
          ]
        },
        "roleDefinitionIds": [
          "/providers/Microsoft.Authorization/roleDefinitions/92aaf0da-9dab-42b6-94a3-d43ce8d16293",
          "/providers/Microsoft.Authorization/roleDefinitions/749f88d5-cbae-40b8-bcfc-e573ddc772fa",
          "/providers/Microsoft.Authorization/roleDefinitions/17d1049b-9a84-46fb-8f53-869881c3d3ab"
        ],
        "deployment": {
          "properties": {
            "mode": "incremental",
            "template": {
              "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#",
              "contentVersion": "1.0.0.0",
              "parameters": {
                "logAnalyticsWorkspaceId": { "type": "String" },
                "storageAccountId": { "type": "String" },
                "diagnosticSettingName": { "type": "String" },
                "resourceId": { "type": "String" }
              },
              "resources": [
                {
                  "type": "Microsoft.Insights/diagnosticSettings",
                  "apiVersion": "2021-05-01-preview",
                  "name": "[parameters('diagnosticSettingName')]",
                  "scope": "[parameters('resourceId')]",
                  "properties": {
                    "workspaceId": "[parameters('logAnalyticsWorkspaceId')]",
                    "storageAccountId": "[parameters('storageAccountId')]",
                    "logs": [{ "categoryGroup": "allLogs", "enabled": true }],
                    "metrics": [{ "category": "AllMetrics", "enabled": true }]
                  }
                }
              ]
            },
            "parameters": {
              "logAnalyticsWorkspaceId": { "value": "[parameters('logAnalyticsWorkspaceId')]" },
              "storageAccountId": { "value": "[parameters('storageAccountId')]" },
              "diagnosticSettingName": { "value": "[parameters('diagnosticSettingName')]" },
              "resourceId": { "value": "[field('id')]" }
            }
          }
        }
      }
    }
  }
}
```

### Key Design Notes

| # | Detail |
|---|--------|
| 1 | `field('id')` is passed via `deployment.parameters` (not directly in the ARM template `resources` block, as `field()` is a Policy-only function) |
| 2 | Supports both **Log Analytics** and **Blob Storage** as diagnostic destinations |
| 3 | `roleDefinitionIds` includes **Log Analytics Contributor**, **Monitoring Contributor**, and **Storage Account Contributor** |

---

## Deployment Steps — Azure Portal

### Step 1: Create the Policy Definition

1. Navigate to **Azure Portal** → **Policy** → **Definitions**
2. Click **+ Policy definition**
3. Fill in:
   - **Definition location**: Select the target Subscription
   - **Name**: `poc-foundrylogging-cogsvcs`
   - **Category**: `foundry-custom` (create new or select existing)
4. Paste the fixed JSON (above) into the **Policy rule** field
5. Click **Save**

### Step 2: Assign the Policy

1. Navigate to **Policy** → **Assignments** → **Assign policy**
2. **Basics**:
   - **Scope**: Select the Subscription or Management Group
   - **Policy definition**: Search for and select `poc-foundrylogging-cogsvcs`
3. **Parameters**:
   - **Log Analytics Workspace Resource ID**:
     ```
     /subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.OperationalInsights/workspaces/<workspace-name>
     ```
   - **Storage Account Resource ID**:
     ```
     /subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.Storage/storageAccounts/<storage-name>
     ```
   - **Diagnostic setting name**: Keep default `setByPolicy` or customize
   - **Effect**: `DeployIfNotExists`
4. **Remediation**:
   - Check **Create a Managed Identity**
   - Select **System assigned managed identity**
   - **Location**: Choose the same region as your resources (e.g., `East US 2`)
5. Click **Review + create** → **Create**

### Step 3: Create a Remediation Task

1. Navigate to **Policy** → **Remediation** → **Create remediation task**
2. Select the Policy Assignment you just created
3. **Important**: Check ✅ **Re-evaluate resource compliance before remediating**
4. **Locations**: `All selected`
5. Click **Remediate**

> ⚠️ If you do not check "Re-evaluate resource compliance before remediating", the remediation task may show **0 resources selected** because it relies on a stale compliance cache.

---

## Deployment Steps — Azure CLI / PowerShell

### Using Azure CLI

```bash
# Step 1: Create Policy Definition
az policy definition create \
  --name "poc-foundrylogging-cogsvcs" \
  --display-name "poc-foundrylogging-cogsvcs" \
  --description "Deploy diagnostic settings to Log Analytics and Blob Storage for Azure AI services." \
  --rules policy-definition.json \
  --mode All \
  --subscription "<subscription-id>"

# Step 2: Assign Policy
az policy assignment create \
  --name "poc-foundrylogging-cogsvcs-assign" \
  --display-name "poc-foundrylogging-cogsvcs" \
  --policy "poc-foundrylogging-cogsvcs" \
  --scope "/subscriptions/<subscription-id>" \
  --mi-system-assigned \
  --location "eastus2" \
  --params '{
    "logAnalyticsWorkspaceId": {"value": "/subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.OperationalInsights/workspaces/<workspace>"},
    "storageAccountId": {"value": "/subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.Storage/storageAccounts/<storage>"}
  }'

# Step 3: Assign roles to the Managed Identity
PRINCIPAL_ID=$(az policy assignment show \
  --name "poc-foundrylogging-cogsvcs-assign" \
  --scope "/subscriptions/<subscription-id>" \
  --query identity.principalId -o tsv)

# Log Analytics Contributor
az role assignment create --assignee "$PRINCIPAL_ID" \
  --role "92aaf0da-9dab-42b6-94a3-d43ce8d16293" \
  --scope "/subscriptions/<subscription-id>"

# Monitoring Contributor
az role assignment create --assignee "$PRINCIPAL_ID" \
  --role "749f88d5-cbae-40b8-bcfc-e573ddc772fa" \
  --scope "/subscriptions/<subscription-id>"

# Storage Account Contributor
az role assignment create --assignee "$PRINCIPAL_ID" \
  --role "17d1049b-9a84-46fb-8f53-869881c3d3ab" \
  --scope "/subscriptions/<subscription-id>"

# Step 4: Create Remediation Task (with ReEvaluateCompliance mode)
az policy remediation create \
  --name "remediate-foundry-cogsvcs-diag" \
  --subscription "<subscription-id>" \
  --policy-assignment "/subscriptions/<subscription-id>/providers/Microsoft.Authorization/policyAssignments/poc-foundrylogging-cogsvcs-assign" \
  --resource-discovery-mode ReEvaluateCompliance
```

### Using PowerShell (Az Module)

```powershell
# Step 1: Create Policy Definition
$definition = New-AzPolicyDefinition `
  -Name "poc-foundrylogging-cogsvcs" `
  -DisplayName "poc-foundrylogging-cogsvcs" `
  -Description "Deploy diagnostic settings to Log Analytics and Blob Storage for Azure AI services." `
  -Policy ".\policy-definition.json" `
  -Mode All

# Step 2: Assign Policy
$params = @{
  logAnalyticsWorkspaceId = "/subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.OperationalInsights/workspaces/<workspace>"
  storageAccountId       = "/subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.Storage/storageAccounts/<storage>"
}

$assignment = New-AzPolicyAssignment `
  -Name "poc-foundrylogging-cogsvcs-assign" `
  -DisplayName "poc-foundrylogging-cogsvcs" `
  -PolicyDefinition $definition `
  -Scope "/subscriptions/<subscription-id>" `
  -PolicyParameterObject $params `
  -IdentityType "SystemAssigned" `
  -Location "eastus2"

# Step 3: Assign roles to the Managed Identity
$principalId = $assignment.Identity.PrincipalId

New-AzRoleAssignment -ObjectId $principalId `
  -RoleDefinitionId "92aaf0da-9dab-42b6-94a3-d43ce8d16293" `
  -Scope "/subscriptions/<subscription-id>"

New-AzRoleAssignment -ObjectId $principalId `
  -RoleDefinitionId "749f88d5-cbae-40b8-bcfc-e573ddc772fa" `
  -Scope "/subscriptions/<subscription-id>"

New-AzRoleAssignment -ObjectId $principalId `
  -RoleDefinitionId "17d1049b-9a84-46fb-8f53-869881c3d3ab" `
  -Scope "/subscriptions/<subscription-id>"

# Step 4: Trigger Compliance Scan
Start-AzPolicyComplianceScan -AsJob

# Step 5: Create Remediation Task
Start-AzPolicyRemediation `
  -Name "remediate-foundry-cogsvcs-diag" `
  -PolicyAssignmentId $assignment.PolicyAssignmentId `
  -ResourceDiscoveryMode "ReEvaluateCompliance"

# Check Remediation Status
Get-AzPolicyRemediation -Name "remediate-foundry-cogsvcs-diag" |
  Select-Object Name, ProvisioningState, @{N='Total';E={$_.DeploymentSummary.TotalDeployments}},
    @{N='Succeeded';E={$_.DeploymentSummary.SuccessfulDeployments}},
    @{N='Failed';E={$_.DeploymentSummary.FailedDeployments}}
```

---

## Remediation Troubleshooting

### Common Issue: Remediation Shows 0/0

| Symptom | Cause | Solution |
|---------|-------|----------|
| Remediation state = `Complete`, but `0 out of 0` | Compliance cache is stale | Create a new remediation task with `ReEvaluateCompliance` mode |
| Remediation state = `Complete`, but `0 out of 0` | Managed Identity is missing required roles | Check the Managed Identity tab on the Assignment; ensure all 3 roles are assigned |
| Remediation deployment fails | `field()` function used inside the ARM template | Use the fixed version — pass `resourceId` via `deployment.parameters` instead |
| Cannot create remediation | An active remediation already exists for the same scope | Wait for the existing remediation to complete, or cancel it first |

### Required Managed Identity Roles

| Role | Role Definition ID | Purpose |
|------|--------------------|----------|
| Log Analytics Contributor | `92aaf0da-9dab-42b6-94a3-d43ce8d16293` | Write to Log Analytics Workspace |
| Monitoring Contributor | `749f88d5-cbae-40b8-bcfc-e573ddc772fa` | Create Diagnostic Settings |
| Storage Account Contributor | `17d1049b-9a84-46fb-8f53-869881c3d3ab` | Write to Storage Account (Blob) |

---

## Appendix: Role Definition ID Reference

| Role Name | Role Definition ID |
|-----------|--------------------|
| Log Analytics Contributor | `92aaf0da-9dab-42b6-94a3-d43ce8d16293` |
| Monitoring Contributor | `749f88d5-cbae-40b8-bcfc-e573ddc772fa` |
| Storage Account Contributor | `17d1049b-9a84-46fb-8f53-869881c3d3ab` |
| Log Analytics Reader | `73c42c96-874c-492b-b04d-ab87d138a893` |
| Monitoring Reader | `43d0d8ad-25c7-4714-9337-8ba259a9fe05` |
