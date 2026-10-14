import type { AppComponent } from '../../app.component';
import type { Agent, BudgetDecision, ContextSnapshot, EvalDataset, EvalDefinition, EvalRun, ExecutionArtifact, ExecutionDetail, ExecutionSummary, GovernanceBudget, GovernanceDecision, GovernancePolicy, KnowledgeBase, KnowledgeDocument, McpServer, MemoryInfo, Orchestration, Overview, PendingApproval, ProcessDefinition, ProcessHumanTask, ProcessInstance, ProcessServiceDefinition, ProcessStepDefinition, ProcessStepType, Prompt, RetrievalHit, RuntimeInfo, SessionInfo, Skill, Tool } from '../../models';

/** memory domain operations. */
export async function loadMemory(this: AppComponent){try{const [m,p,a]=await Promise.all([this.api.memories(),this.api.memoryPolicy(),this.api.memoryPolicyAudit()]);this.memories.set(m);this.memoryPolicy.set(p);this.memoryAudit.set(a);}catch(e:any){this.error.set(this.message(e));}}

export function openCreateMemory(this: AppComponent){this.draft={scopeType:'TENANT',scopeId:'',memoryType:'FACT',key:'',content:'',importance:0.5,expiresAt:''};this.modal.set('memory');}

export async function saveMemory(this: AppComponent){await this.run(async()=>{await this.api.createMemory({scopeType:this.draft.scopeType,scopeId:this.draft.scopeId,memoryType:this.draft.memoryType,key:this.draft.key||null,content:this.draft.content,importance:Number(this.draft.importance||0.5),expiresAt:this.draft.expiresAt?new Date(this.draft.expiresAt).toISOString():null});this.memories.set(await this.api.memories());this.closeModal();});}

export async function revokeMemoryItem(this: AppComponent, m:MemoryInfo){if(confirm('Revoke this memory?'))await this.run(async()=>{await this.api.revokeMemory(m.id);this.memories.set(await this.api.memories());});}

export async function searchMemory(this: AppComponent){if(!this.memoryQuery||!this.memoryScopeId)return;await this.run(async()=>{this.memoryHits.set(await this.api.retrieveMemories(this.memoryQuery,[{scopeType:this.memoryScopeType,scopeId:this.memoryScopeId}],this.memoryTopK));});}
