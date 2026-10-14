import type { AppComponent } from '../../app.component';
import type { Agent, BudgetDecision, ContextSnapshot, EvalDataset, EvalDefinition, EvalRun, ExecutionArtifact, ExecutionDetail, ExecutionSummary, GovernanceBudget, GovernanceDecision, GovernancePolicy, KnowledgeBase, KnowledgeDocument, McpServer, MemoryInfo, Orchestration, Overview, PendingApproval, ProcessDefinition, ProcessHumanTask, ProcessInstance, ProcessServiceDefinition, ProcessStepDefinition, ProcessStepType, Prompt, RetrievalHit, RuntimeInfo, SessionInfo, Skill, Tool } from '../../models';

/** executions domain operations. */
export async function loadRuntime(this: AppComponent){try{this.runtime.set(await this.api.runtime());}catch(e:any){this.error.set(this.message(e));}}

export function filteredExecutions(this: AppComponent){const q=this.search.toLowerCase();return this.executions().filter(x=>(!q||[x.executionId,x.commandName,x.intent,x.objective].some(v=>(v||'').toLowerCase().includes(q)))&&(!this.executionStatus||x.status===this.executionStatus));}

export async function filterExecutions(this: AppComponent){this.executions.set(await this.api.executions(this.executionStatus));}

export async function openExecution(this: AppComponent, id:string,show=true){try{const [d,o,s,c,a]=await Promise.all([this.api.execution(id),this.api.orchestration(id),this.api.contextSnapshots(id),this.api.executionContext(id),this.api.executionArtifacts(id)]);this.selectedExecution.set(d);this.orchestration.set(o);this.contextSnapshots.set(s);this.executionContext.set(c);this.executionArtifacts.set(a);if(show)this.modal.set('execution');}catch(e:any){this.error.set(this.message(e));}}

export function cancelModal(this: AppComponent){
    if(this.modal()==='process-step'){
      this.processStepDraft.set(null);
      this.modal.set('process-designer');
      return;
    }
    if(this.modal()==='process-designer'){
      this.processDesigner.set(null);
      this.processStepDraft.set(null);
    }
    this.closeModal();
  }

export function closeModal(this: AppComponent){this.modal.set(null);this.draft={};this.approvalComment='';}

export function statusClass(this: AppComponent, s:string){return (s||'').toLowerCase().replaceAll('_','-');}

export function tokens(this: AppComponent, v:any){return new Intl.NumberFormat('es-ES').format(Number(v||0));}

export function runningEvalCount(this: AppComponent){return this.evalRuns().filter(r=>r.status==='RUNNING').length;}

export function regressionEvalCount(this: AppComponent){return this.evalRuns().filter(r=>r.regression?.regressed).length;}

export function date(this: AppComponent, v:any){return v?new Date(v).toLocaleString('es-ES'):'—';}

export function json(this: AppComponent, v:any){return JSON.stringify(v??{},null,2);}

export function short(this: AppComponent, v:string,n=80){return !v?'—':v.length>n?v.slice(0,n)+'…':v;}

export function executionLevels(this: AppComponent){const steps=this.orchestration()?.steps||[];const level=new Map<string,number>();let changed=true;while(changed){changed=false;for(const s of steps){const l=s.dependsOn?.length?Math.max(...s.dependsOn.map(d=>level.get(d)??0))+1:0;if(level.get(s.id)!==l){level.set(s.id,l);changed=true;}}}return [...new Set([...level.values()])].sort((a,b)=>a-b).map(l=>steps.filter(s=>level.get(s.id)===l));}

export function canPause(this: AppComponent){return ['RUNNING','RETRYING','ACCEPTED'].includes(this.selectedExecution()?.status||'');}

export function canResume(this: AppComponent){return this.selectedExecution()?.status==='PAUSED';}

export function canRetry(this: AppComponent){return this.selectedExecution()?.status==='FAILED';}

export async function execAction(this: AppComponent, kind:'pause'|'resume'|'retry'|'cancel'){const id=this.selectedExecution()?.executionId;if(!id)return;await this.run(async()=>{if(kind==='pause')await this.api.pause(id);if(kind==='resume')await this.api.resume(id);if(kind==='retry')await this.api.retry(id);if(kind==='cancel')await this.api.cancel(id);await this.openExecution(id,false);});}

export async function decide(this: AppComponent, executionId:string,stepId:string,approved:boolean){await this.run(async()=>{await this.api.approval(executionId,stepId,approved,this.actor,this.approvalComment|| (approved?'Approved from Control Plane':'Rejected from Control Plane'));this.approvals.set(await this.api.approvals());if(this.selectedExecution()?.executionId===executionId)await this.openExecution(executionId,false);this.approvalComment='';});}

export function openCreateExecution(this: AppComponent){this.draft={name:'control-plane-request',intent:'',sessionId:'',input:'{}',context:'{}',instructions:''};this.modal.set('create-execution');}

export async function saveExecution(this: AppComponent){await this.run(async()=>{const body={correlationId:crypto.randomUUID(),sessionId:this.draft.sessionId||null,command:{name:this.draft.name||null,intent:this.draft.intent,input:JSON.parse(this.draft.input||'{}'),context:JSON.parse(this.draft.context||'{}'),instructions:(this.draft.instructions||'').split('\n').filter(Boolean)}};const r=await this.api.createExecution(body);this.closeModal();await this.refreshAll();await this.openExecution(r.executionId);});}
