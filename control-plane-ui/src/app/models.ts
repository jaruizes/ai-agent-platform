export interface Overview {version:string;executionsByStatus:Record<string,number>;totals:Record<string,number>;}
export interface RuntimeInfo {service:{name:string;version:string};dependencies:Record<string,{status:string;baseUrl?:string;endpoint?:string}>;models:Record<string,string>;knowledge:any;durability:any;memory?:any;contextEngine?:any;}
export interface ExecutionSummary {executionId:string;correlationId:string;sessionId?:string;commandName?:string;intent:string;status:string;controlAction?:string;controlReason?:string;objective?:string;planStatus?:string;plannerModel?:string;waitingApprovals:number;retryingSteps:number;leaseOwner?:string;leaseExpiresAt?:string;createdAt:string;updatedAt:string;completedAt?:string;}
export interface ExecutionDetail {executionId:string;correlationId:string;sessionId?:string;command:{name?:string};intent:string;status:string;control:any;lease:any;result:any;error:any;orchestration:any;createdAt:string;updatedAt:string;completedAt?:string;}
export interface OrchestrationStep {id:string;type:string;description:string;agent?:string;tool?:string;knowledgeBases:string[];dependsOn:string[];status:string;requiresApproval:boolean;approvalSource?:string;toolPolicy:any;approval:any;attemptCount:number;maxAttempts:number;timeoutSeconds:number;retryPolicy:any;nextRetryAt?:string;idempotencyKey?:string;usage:any;output:any;error:any;startedAt?:string;completedAt?:string;}
export interface Orchestration {executionId:string;status:string;plan:any;steps:OrchestrationStep[];activeAgents:any[];waitingApprovals:any[];retryingSteps:any[];usage:{promptTokens:number;completionTokens:number;totalTokens:number};}
export interface PendingApproval {executionId:string;commandName?:string;intent:string;executionCreatedAt:string;stepId:string;description:string;agent?:string;tool?:string;reason?:string;approvalSource?:string;sideEffect?:string;approvalPolicy?:string;waitingSince?:string;}
export interface Skill {id:string;name:string;description:string;instructions:string;enabled:boolean;source:string;}
export interface Agent {id:string;name:string;description:string;instructions:string;enabled:boolean;source:string;skills:Skill[];}
export interface Prompt {id:string;name:string;description:string;content:string;version:number;enabled:boolean;source:string;}
export interface Tool {id:string;name:string;description:string;instructions:string;implementationType:string;configuration:any;inputSchema:any;sideEffect:string;approvalPolicy:string;enabled:boolean;source:string;}
export interface McpServer {id:string;name:string;description:string;command:string;args:string[];cwd?:string;environment:Record<string,string>;enabled:boolean;source:string;}
export interface KnowledgeBase {id:string;name:string;description:string;scope:string;retentionPolicy:string;expiresAt?:string;enabled:boolean;chunkingPolicy:any;metadata:any;}
export interface KnowledgeDocument {id:string;knowledgeBaseId:string;name:string;sourceType:string;sourceId?:string;sourceUri?:string;mimeType?:string;status:string;version:number;checksum?:string;metadata:any;error?:any;}
export interface RetrievalHit {chunkId:string;documentId:string;knowledgeBaseId:string;documentName:string;content:string;score:number;metadata:any;}

export interface SessionInfo {id:string;name?:string;status:string;scope:string;ownerKey?:string;metadata:any;expiresAt?:string;createdAt:string;updatedAt:string;closedAt?:string;}
export interface MemoryInfo {id:string;scopeType:string;scopeId:string;memoryType:string;key?:string;content:string;metadata:any;confidence:number;importance:number;explicit:boolean;status:string;policyDecision:any;sourceExecutionId?:string;sourceStepId?:string;supersedesMemoryId?:string;expiresAt?:string;createdAt:string;updatedAt:string;revokedAt?:string;}
export interface ContextSnapshotComponent {type:string;priority:number;mandatory:boolean;sourceRef?:string;tokenEstimate:number;selected:boolean;action:string;metadata:any;}
export interface ContextSnapshot {id:string;executionId:string;stepId:string;attempt:number;modelProfile:string;budget:any;components:ContextSnapshotComponent[];provenance:any[];promptTokenEstimate:number;selectedTokenEstimate:number;droppedTokenEstimate:number;compressed:boolean;createdAt:string;}


export interface GovernancePolicy {id:string;name:string;description:string;policyType:string;effect:string;resourceType:string;resourcePattern:string;subjectType:string;subjectPattern:string;conditions:any;priority:number;enabled:boolean;source:string;createdAt:string;updatedAt:string;}
export interface GovernanceBudget {id:string;name:string;scopeType:string;scopeId:string;period:string;maxPromptTokens?:number;maxCompletionTokens?:number;maxTotalTokens?:number;maxCostUsd?:number;action:string;degradeModelProfile?:string;enabled:boolean;createdAt:string;updatedAt:string;}
export interface GovernanceDecision {id:string;executionId:string;stepId?:string;policyName?:string;policyType:string;effect:string;resourceType:string;resourceName:string;subjectType:string;subjectId:string;reason:string;createdAt:string;}
export interface BudgetDecision {id:string;executionId:string;stepId?:string;budgetName?:string;action:string;allowed:boolean;requestedModelProfile:string;effectiveModelProfile:string;reason?:string;current:any;projected:any;createdAt:string;}

export interface EvalDatasetItem {id?:string;name:string;command:any;expectedOutput?:string;assertions:any[];tags:string[];}
export interface EvalDataset {id:string;name:string;description:string;version:number;enabled:boolean;items:EvalDatasetItem[];createdAt:string;updatedAt:string;}
export interface EvalDefinition {id:string;name:string;description:string;datasetId:string;datasetName:string;metrics:string[];thresholds:Record<string,number>;judgeModelProfile?:string;enabled:boolean;createdAt:string;updatedAt:string;}
export interface EvalResult {id:string;datasetItemId:string;itemName:string;executionId?:string;status:string;output?:string;scores:Record<string,number>;checks:any[];passed:boolean;tokenUsage:any;costUsd:number;latencyMs:number;error?:any;}
export interface EvalRun {id:string;definitionId:string;baselineRunId?:string;status:string;datasetVersion:number;configurationSnapshot:any;aggregateScores:Record<string,number>;regression:any;totalCases:number;passedCases:number;failedCases:number;totalTokens:number;totalCostUsd:number;error?:any;createdAt:string;startedAt?:string;completedAt?:string;results?:EvalResult[];}


export type ProcessStepType='SERVICE'|'AGENTIC_EXECUTION'|'DECISION'|'HUMAN'|'WAIT_EVENT'|'SUBPROCESS';
export type ProcessDefinitionStatus='DRAFT'|'ACTIVE'|'RETIRED';
export type ProcessInstanceStatus='CREATED'|'RUNNING'|'WAITING'|'PAUSED'|'COMPLETED'|'FAILED'|'CANCELLED';

export interface ProcessServiceDefinition {
  id:string;
  serviceKey:string;
  name:string;
  description:string;
  version:number;
  status:'DRAFT'|'ACTIVE'|'RETIRED';
  implementationKey:string;
  configuration:any;
  inputSchema:any;
  outputSchema:any;
  createdAt:string;
  updatedAt:string;
  activatedAt?:string;
}
export interface ProcessStepDefinition {
  id?:string;
  stepKey:string;
  name:string;
  description:string;
  type:ProcessStepType;
  dependsOn:string[];
  inputSchema:any;
  outputSchema:any;
  configuration:any;
}
export interface ProcessDefinition {
  id:string;
  definitionKey:string;
  name:string;
  description:string;
  version:number;
  status:ProcessDefinitionStatus;
  inputSchema:any;
  outputSchema:any;
  steps:ProcessStepDefinition[];
  createdAt:string;
  updatedAt:string;
  activatedAt?:string;
}
export interface ProcessStepInstance {
  id:string;
  processInstanceId:string;
  stepDefinitionId:string;
  stepKey:string;
  type:ProcessStepType;
  status:string;
  input:any;
  output:any;
  error:any;
  delegatedExecutionId?:string;
  attemptCount:number;
  availableAt?:string;
  deadlineAt?:string;
  startedAt?:string;
  completedAt?:string;
  updatedAt:string;
}
export interface ProcessInstance {
  id:string;
  definitionId:string;
  definitionKey:string;
  definitionVersion:number;
  status:ProcessInstanceStatus;
  correlationId:string;
  input:any;
  context:any;
  steps:ProcessStepInstance[];
  createdAt:string;
  updatedAt:string;
  completedAt?:string;
}
export interface ProcessHumanTask {
  id:string;
  processInstanceId:string;
  stepKey:string;
  iteration:number;
  title:string;
  description:string;
  payload:any;
  status:'PENDING'|'COMPLETED'|'CANCELLED';
  decision?:string;
  result:any;
  createdAt:string;
  completedAt?:string;
}
