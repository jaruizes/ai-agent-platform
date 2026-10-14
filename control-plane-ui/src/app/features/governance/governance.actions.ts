import type { AppComponent } from '../../app.component';
import type { Agent, BudgetDecision, ContextSnapshot, EvalDataset, EvalDefinition, EvalRun, ExecutionArtifact, ExecutionDetail, ExecutionSummary, GovernanceBudget, GovernanceDecision, GovernancePolicy, KnowledgeBase, KnowledgeDocument, McpServer, MemoryInfo, Orchestration, Overview, PendingApproval, ProcessDefinition, ProcessHumanTask, ProcessInstance, ProcessServiceDefinition, ProcessStepDefinition, ProcessStepType, Prompt, RetrievalHit, RuntimeInfo, SessionInfo, Skill, Tool } from '../../models';

/** governance domain operations. */
export async function loadGovernance(this: AppComponent){try{const [p,b,d,bd]=await Promise.all([this.api.governancePolicies(),this.api.governanceBudgets(),this.api.governanceDecisions(),this.api.budgetDecisions()]);this.governancePolicies.set(p);this.governanceBudgets.set(b);this.governanceDecisions.set(d);this.budgetDecisions.set(bd);}catch(e:any){this.error.set(this.message(e));}}

export function editGovernancePolicy(this: AppComponent, x?:GovernancePolicy){this.draft=x?{...x,conditions:this.json(x.conditions)}:{name:'',description:'',policyType:'RESOURCE_ACCESS',effect:'ALLOW',resourceType:'MODEL',resourcePattern:'*',subjectType:'GLOBAL',subjectPattern:'*',conditions:'{}',priority:100,enabled:true};this.modal.set('governance-policy');}

export async function saveGovernancePolicy(this: AppComponent){await this.run(async()=>{await this.api.saveGovernancePolicy(this.draft);this.governancePolicies.set(await this.api.governancePolicies());this.closeModal();});}

export async function deleteGovernancePolicy(this: AppComponent, x:GovernancePolicy){if(confirm(`Delete policy ${x.name}?`))await this.run(async()=>{await this.api.deleteGovernancePolicy(x.id);this.governancePolicies.set(await this.api.governancePolicies());});}

export function editGovernanceBudget(this: AppComponent, x?:GovernanceBudget){this.draft=x?{...x}:{name:'',scopeType:'GLOBAL',scopeId:'*',period:'EXECUTION',maxPromptTokens:null,maxCompletionTokens:null,maxTotalTokens:null,maxCostUsd:null,action:'DENY',degradeModelProfile:'',enabled:true};this.modal.set('governance-budget');}

export async function saveGovernanceBudget(this: AppComponent){await this.run(async()=>{await this.api.saveGovernanceBudget(this.draft);this.governanceBudgets.set(await this.api.governanceBudgets());this.closeModal();});}

export async function deleteGovernanceBudget(this: AppComponent, x:GovernanceBudget){if(confirm(`Delete budget ${x.name}?`))await this.run(async()=>{await this.api.deleteGovernanceBudget(x.id);this.governanceBudgets.set(await this.api.governanceBudgets());});}
