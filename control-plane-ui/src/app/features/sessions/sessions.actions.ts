import type { AppComponent } from '../../app.component';
import type { Agent, BudgetDecision, ContextSnapshot, EvalDataset, EvalDefinition, EvalRun, ExecutionArtifact, ExecutionDetail, ExecutionSummary, GovernanceBudget, GovernanceDecision, GovernancePolicy, KnowledgeBase, KnowledgeDocument, McpServer, MemoryInfo, Orchestration, Overview, PendingApproval, ProcessDefinition, ProcessHumanTask, ProcessInstance, ProcessServiceDefinition, ProcessStepDefinition, ProcessStepType, Prompt, RetrievalHit, RuntimeInfo, SessionInfo, Skill, Tool } from '../../models';

/** sessions domain operations. */
export async function loadSessions(this: AppComponent){try{this.sessions.set(await this.api.sessions());}catch(e:any){this.error.set(this.message(e));}}

export function openCreateSession(this: AppComponent){this.draft={name:'',scope:'TENANT',ownerKey:'',expiresAt:'',metadata:'{}'};this.modal.set('session');}

export function editSession(this: AppComponent, s:SessionInfo){this.draft={...s,expiresAt:s.expiresAt?new Date(s.expiresAt).toISOString().slice(0,16):'',metadata:this.json(s.metadata)};this.modal.set('session');}

export async function saveSession(this: AppComponent){await this.run(async()=>{const body={name:this.draft.name||null,scope:this.draft.scope,ownerKey:this.draft.ownerKey||null,expiresAt:this.draft.expiresAt?new Date(this.draft.expiresAt).toISOString():null,metadata:JSON.parse(this.draft.metadata||'{}')};if(this.draft.id)await this.api.updateSession(this.draft.id,body);else await this.api.createSession(body);this.sessions.set(await this.api.sessions());this.closeModal();});}

export async function closeSessionItem(this: AppComponent, s:SessionInfo){if(confirm(`Close session ${s.name||s.id}?`))await this.run(async()=>{await this.api.closeSession(s.id);this.sessions.set(await this.api.sessions());if(this.selectedSession()?.id===s.id)this.selectedSession.set(null);});}

export async function inspectSession(this: AppComponent, s:SessionInfo){await this.run(async()=>{const [ctx,execs]=await Promise.all([this.api.sessionContext(s.id),this.api.sessionExecutions(s.id)]);this.selectedSession.set(s);this.sessionContext.set(ctx);this.sessionExecutions.set(execs);this.modal.set('session-inspect');});}
