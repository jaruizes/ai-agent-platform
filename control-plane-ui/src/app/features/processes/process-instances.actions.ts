import type { AppComponent, ProcessTab } from '../../app.component';
import type { Agent, BudgetDecision, ContextSnapshot, EvalDataset, EvalDefinition, EvalRun, ExecutionArtifact, ExecutionDetail, ExecutionSummary, GovernanceBudget, GovernanceDecision, GovernancePolicy, KnowledgeBase, KnowledgeDocument, McpServer, MemoryInfo, Orchestration, Overview, PendingApproval, ProcessDefinition, ProcessHumanTask, ProcessInstance, ProcessServiceDefinition, ProcessStepDefinition, ProcessStepType, Prompt, RetrievalHit, RuntimeInfo, SessionInfo, Skill, Tool } from '../../models';

/** process-instances behavior; application state remains in the host during migration. */
export function openCreateProcessInstance(this: AppComponent, x?:ProcessDefinition){
    const active=x||(this.processDefinitions().find(d=>d.status==='ACTIVE'));
    this.draft={
      definitionSelection:active?`${active.definitionKey}::${active.version}`:'',
      definitionKey:active?.definitionKey||'',
      version:active?.version||null,
      correlationId:crypto.randomUUID(),input:'{}',context:'{}',start:true
    };
    this.modal.set('process-instance-create');
  }

export function selectProcessDefinitionForNewInstance(this: AppComponent, value:string){
    const [definitionKey,version]=String(value||'').split('::');
    this.draft.definitionSelection=value;
    this.draft.definitionKey=definitionKey||'';
    this.draft.version=version?Number(version):null;
  }

export function activeProcessDefinitions(this: AppComponent){
    return this.processDefinitions()
      .filter(d=>d.status==='ACTIVE')
      .sort((a,b)=>a.definitionKey.localeCompare(b.definitionKey)||b.version-a.version);
  }

export async function saveProcessInstance(this: AppComponent){
    await this.run(async()=>{
      const body={definitionKey:this.draft.definitionKey,version:this.draft.version?Number(this.draft.version):null,correlationId:this.draft.correlationId||crypto.randomUUID(),input:JSON.parse(this.draft.input||'{}'),context:JSON.parse(this.draft.context||'{}')};
      const created=await this.api.createProcessInstance(body);
      if(this.draft.start!==false)await this.api.startProcessInstance(created.id);
      this.processInstances.set(await this.api.processInstances());
      this.closeModal();
      await this.openProcessInstance(created.id);
    });
  }

export async function openProcessInstance(this: AppComponent, id:string){
    await this.run(async()=>{const x=await this.api.processInstance(id);this.selectedProcessInstance.set(x);this.modal.set('process-instance');});
  }

export async function processInstanceAction(this: AppComponent, kind:'start'|'pause'|'resume'|'cancel'){
    const x=this.selectedProcessInstance();if(!x)return;
    await this.run(async()=>{
      if(kind==='start')await this.api.startProcessInstance(x.id);
      if(kind==='pause')await this.api.pauseProcessInstance(x.id);
      if(kind==='resume')await this.api.resumeProcessInstance(x.id);
      if(kind==='cancel')await this.api.cancelProcessInstance(x.id);
      this.selectedProcessInstance.set(await this.api.processInstance(x.id));
      this.processInstances.set(await this.api.processInstances());
    });
  }

export async function completeHumanTask(this: AppComponent, x:ProcessHumanTask,explicitDecision?:string){
    await this.run(async()=>{
      const review=this.humanTaskReviewPolicy(x);
      const allowed=review?[review.approveDecision||'APPROVE',review.repeatDecision||'REQUEST_CHANGES']:[];
      const decision=explicitDecision||(review&&!allowed.includes(this.processHumanDecision)
        ? (review.approveDecision||'APPROVE')
        : this.processHumanDecision);
      await this.api.completeProcessHumanTask(x.id,decision,JSON.parse(this.processHumanResult||'{}'));
      this.processHumanTasks.set(await this.api.processHumanTasks());
      this.processInstances.set(await this.api.processInstances());
      this.processHumanResult='{}';
    });
  }

export function openSignalProcessEvent(this: AppComponent, x?:ProcessInstance){
    let eventType='';
    if(x){
      const waiting=x.steps.find(s=>s.type==='WAIT_EVENT'&&s.status==='WAITING');
      const definition=this.processDefinitions().find(d=>d.id===x.definitionId);
      eventType=definition?.steps.find(s=>s.stepKey===waiting?.stepKey)?.configuration?.eventType||'';
    }
    this.processSignalEventType=eventType;
    this.processSignalCorrelation=x?.correlationId||'';
    this.processSignalPayload='{}';
    this.modal.set('process-event');
  }

export async function signalProcessEvent(this: AppComponent){
    await this.run(async()=>{
      await this.api.signalProcessEvent(this.processSignalEventType,this.processSignalCorrelation,JSON.parse(this.processSignalPayload||'{}'));
      this.closeModal();
      await this.refreshProcessesLive();
    });
  }
