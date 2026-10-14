import * as definitionActions from './features/processes/process-definitions.actions';
import * as serviceActions from './features/processes/process-services.actions';
import * as instanceActions from './features/processes/process-instances.actions';
import * as presentationActions from './features/processes/process-presentation.actions';
import * as resourceActions from './features/resources/resource.actions';
import { DashboardViewComponent } from './features/dashboard/dashboard-view.component';
import { ExecutionsViewComponent } from './features/executions/executions-view.component';
import { ApprovalsViewComponent } from './features/approvals/approvals-view.component';
import { ProcessesViewComponent } from './features/processes/processes-view.component';
import { ServicesViewComponent } from './features/services/services-view.component';
import { SessionsViewComponent } from './features/sessions/sessions-view.component';
import { MemoryViewComponent } from './features/memory/memory-view.component';
import { AgentsViewComponent } from './features/agents/agents-view.component';
import { SkillsViewComponent } from './features/skills/skills-view.component';
import { PromptsViewComponent } from './features/prompts/prompts-view.component';
import { ToolsViewComponent } from './features/tools/tools-view.component';
import { McpViewComponent } from './features/mcp/mcp-view.component';
import { KnowledgeViewComponent } from './features/knowledge/knowledge-view.component';
import { GovernanceViewComponent } from './features/governance/governance-view.component';
import { EvalsViewComponent } from './features/evals/evals-view.component';
import { RuntimeViewComponent } from './features/runtime/runtime-view.component';
import { ExecutionDialogComponent } from './dialogs/execution-dialog/execution-dialog.component';
import { EditorDialogComponent } from './dialogs/editor-dialog/editor-dialog.component';
import { CommonModule } from '@angular/common';
import { Component, OnDestroy, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ApiService } from './api.service';
import { Agent, BudgetDecision, ContextSnapshot, EvalDataset, EvalDefinition, EvalRun, ExecutionArtifact, ExecutionDetail, ExecutionSummary, GovernanceBudget, GovernanceDecision, GovernancePolicy, KnowledgeBase, KnowledgeDocument, McpServer, MemoryInfo, Orchestration, Overview, PendingApproval, ProcessDefinition, ProcessHumanTask, ProcessInstance, ProcessServiceDefinition, ProcessStepDefinition, ProcessStepType, Prompt, RetrievalHit, RuntimeInfo, SessionInfo, Skill, Tool } from './models';

type View='dashboard'|'executions'|'approvals'|'processes'|'services'|'sessions'|'memory'|'agents'|'skills'|'prompts'|'tools'|'mcp'|'knowledge'|'governance'|'evals'|'runtime';
export type ProcessTab='definitions'|'instances'|'human';

@Component({selector:'app-root',standalone:true,imports:[CommonModule,FormsModule,DashboardViewComponent,ExecutionsViewComponent,ApprovalsViewComponent,ProcessesViewComponent,ServicesViewComponent,SessionsViewComponent,MemoryViewComponent,AgentsViewComponent,SkillsViewComponent,PromptsViewComponent,ToolsViewComponent,McpViewComponent,KnowledgeViewComponent,GovernanceViewComponent,EvalsViewComponent,RuntimeViewComponent,ExecutionDialogComponent,EditorDialogComponent],templateUrl:'./app.component.html'})
export class AppComponent implements OnInit,OnDestroy {
  view=signal<View>('dashboard'); busy=signal(false); error=signal('');
  overview=signal<Overview|null>(null); runtime=signal<RuntimeInfo|null>(null);
  executions=signal<ExecutionSummary[]>([]); approvals=signal<PendingApproval[]>([]);
  agents=signal<Agent[]>([]); skills=signal<Skill[]>([]); prompts=signal<Prompt[]>([]); tools=signal<Tool[]>([]); mcpServers=signal<McpServer[]>([]);
  knowledgeBases=signal<KnowledgeBase[]>([]); documents=signal<KnowledgeDocument[]>([]); retrievalHits=signal<RetrievalHit[]>([]);
  governancePolicies=signal<GovernancePolicy[]>([]); governanceBudgets=signal<GovernanceBudget[]>([]); governanceDecisions=signal<GovernanceDecision[]>([]); budgetDecisions=signal<BudgetDecision[]>([]);
  evalDatasets=signal<EvalDataset[]>([]); evalDefinitions=signal<EvalDefinition[]>([]); evalRuns=signal<EvalRun[]>([]); selectedEvalRun=signal<EvalRun|null>(null);
  sessions=signal<SessionInfo[]>([]); memories=signal<MemoryInfo[]>([]); contextSnapshots=signal<ContextSnapshot[]>([]); executionContext=signal<any[]>([]);
  memoryPolicy=signal<any>(null); memoryAudit=signal<any[]>([]); selectedSession=signal<SessionInfo|null>(null); sessionContext=signal<any[]>([]); sessionExecutions=signal<any[]>([]);
  memoryQuery=''; memoryScopeType='SESSION'; memoryScopeId=''; memoryTopK=8; memoryHits=signal<MemoryInfo[]>([]);
  selectedExecution=signal<ExecutionDetail|null>(null); orchestration=signal<Orchestration|null>(null); selectedKb=signal<KnowledgeBase|null>(null); selectedArtifact=signal<ExecutionArtifact|null>(null); executionArtifacts=signal<ExecutionArtifact[]>([]);
  modal=signal<string|null>(null); draft:any={}; search=''; executionStatus=''; retrievalQuery=''; retrievalTopK=8; actor='operator'; approvalComment='';
  agentKnowledge=signal<any[]>([]); knowledgeDraft:Record<string,string>={};

  processTab=signal<ProcessTab>('definitions');
  processDefinitions=signal<ProcessDefinition[]>([]);
  processServices=signal<ProcessServiceDefinition[]>([]);
  processInstances=signal<ProcessInstance[]>([]);
  processHumanTasks=signal<ProcessHumanTask[]>([]);
  selectedProcessDefinition=signal<ProcessDefinition|null>(null);
  selectedProcessInstance=signal<ProcessInstance|null>(null);
  processDesigner=signal<any|null>(null);
  processStepDraft=signal<any|null>(null);
  processInstanceSearch='';
  processDefinitionSearch='';
  processHumanDecision='APPROVED';
  processHumanResult='{}';
  humanTaskTechnicalOpen:Record<string,boolean>={};
  processSignalEventType='';
  processSignalCorrelation='';
  processSignalPayload='{}';

  private poller?:ReturnType<typeof setInterval>;

  constructor(public api:ApiService){}
  async ngOnInit(){await this.refreshAll();this.poller=setInterval(()=>this.refreshLive(),3000);}
  ngOnDestroy(){if(this.poller)clearInterval(this.poller);}
  async refreshAll(){await this.run(async()=>{const [o,r,e,a,ag,sk,pr,to,mc,kb,se,me,mp,ma,gp,gb,gd,bd,ed,ef,er]=await Promise.all([this.api.overview(),this.api.runtime(),this.api.executions(),this.api.approvals(),this.api.agents(),this.api.skills(),this.api.prompts(),this.api.tools(),this.api.mcpServers(),this.api.knowledgeBases(),this.api.sessions(),this.api.memories(),this.api.memoryPolicy(),this.api.memoryPolicyAudit(),this.api.governancePolicies(),this.api.governanceBudgets(),this.api.governanceDecisions(),this.api.budgetDecisions(),this.api.evalDatasets(),this.api.evalDefinitions(),this.api.evalRuns()]);this.overview.set(o);this.runtime.set(r);this.executions.set(e);this.approvals.set(a);this.agents.set(ag);this.skills.set(sk);this.prompts.set(pr);this.tools.set(to);this.mcpServers.set(mc);this.knowledgeBases.set(kb);this.sessions.set(se);this.memories.set(me);this.memoryPolicy.set(mp);this.memoryAudit.set(ma);this.governancePolicies.set(gp);this.governanceBudgets.set(gb);this.governanceDecisions.set(gd);this.budgetDecisions.set(bd);this.evalDatasets.set(ed);this.evalDefinitions.set(ef);this.evalRuns.set(er);});}
  async refreshLive(){try{this.overview.set(await this.api.overview());this.executions.set(await this.api.executions(this.executionStatus));this.approvals.set(await this.api.approvals());if(this.selectedExecution())await this.openExecution(this.selectedExecution()!.executionId,false);if(this.view()==='processes'||this.view()==='services')await this.refreshProcessesLive();}catch{}}
  setView(v:View){this.view.set(v);if(v==='runtime')this.loadRuntime();if(v==='sessions')this.loadSessions();if(v==='memory')this.loadMemory();if(v==='governance')this.loadGovernance();if(v==='evals')this.loadEvals();if(v==='processes'||v==='services')this.loadProcesses();}

  async loadGovernance(){try{const [p,b,d,bd]=await Promise.all([this.api.governancePolicies(),this.api.governanceBudgets(),this.api.governanceDecisions(),this.api.budgetDecisions()]);this.governancePolicies.set(p);this.governanceBudgets.set(b);this.governanceDecisions.set(d);this.budgetDecisions.set(bd);}catch(e:any){this.error.set(this.message(e));}}
  editGovernancePolicy(x?:GovernancePolicy){this.draft=x?{...x,conditions:this.json(x.conditions)}:{name:'',description:'',policyType:'RESOURCE_ACCESS',effect:'ALLOW',resourceType:'MODEL',resourcePattern:'*',subjectType:'GLOBAL',subjectPattern:'*',conditions:'{}',priority:100,enabled:true};this.modal.set('governance-policy');}
  async saveGovernancePolicy(){await this.run(async()=>{await this.api.saveGovernancePolicy(this.draft);this.governancePolicies.set(await this.api.governancePolicies());this.closeModal();});}
  async deleteGovernancePolicy(x:GovernancePolicy){if(confirm(`Delete policy ${x.name}?`))await this.run(async()=>{await this.api.deleteGovernancePolicy(x.id);this.governancePolicies.set(await this.api.governancePolicies());});}
  editGovernanceBudget(x?:GovernanceBudget){this.draft=x?{...x}:{name:'',scopeType:'GLOBAL',scopeId:'*',period:'EXECUTION',maxPromptTokens:null,maxCompletionTokens:null,maxTotalTokens:null,maxCostUsd:null,action:'DENY',degradeModelProfile:'',enabled:true};this.modal.set('governance-budget');}
  async saveGovernanceBudget(){await this.run(async()=>{await this.api.saveGovernanceBudget(this.draft);this.governanceBudgets.set(await this.api.governanceBudgets());this.closeModal();});}
  async deleteGovernanceBudget(x:GovernanceBudget){if(confirm(`Delete budget ${x.name}?`))await this.run(async()=>{await this.api.deleteGovernanceBudget(x.id);this.governanceBudgets.set(await this.api.governanceBudgets());});}

  async loadEvals(){try{const [d,f,r]=await Promise.all([this.api.evalDatasets(),this.api.evalDefinitions(),this.api.evalRuns()]);this.evalDatasets.set(d);this.evalDefinitions.set(f);this.evalRuns.set(r);}catch(e:any){this.error.set(this.message(e));}}
  editEvalDataset(x?:EvalDataset){this.draft=x?{...x,items:this.json(x.items)}:{name:'',description:'',version:1,enabled:true,items:'[{"name":"case-1","command":{"name":"eval-case","intent":"Explain briefly what an API Gateway is.","input":{},"context":{},"instructions":[]},"expectedOutput":"An API Gateway is an entry point for APIs.","assertions":[{"type":"CONTAINS","value":"API"}],"tags":["smoke"]}]'};this.modal.set('eval-dataset');}
  async saveEvalDataset(){await this.run(async()=>{const items=typeof this.draft.items==='string'?JSON.parse(this.draft.items):this.draft.items;await this.api.saveEvalDataset({name:this.draft.name,description:this.draft.description||'',version:Number(this.draft.version||1),enabled:this.draft.enabled!==false,items});this.evalDatasets.set(await this.api.evalDatasets());this.closeModal();});}
  async deleteEvalDataset(x:EvalDataset){if(confirm(`Delete dataset ${x.name}?`))await this.run(async()=>{await this.api.deleteEvalDataset(x.id);this.evalDatasets.set(await this.api.evalDatasets());});}
  editEvalDefinition(x?:EvalDefinition){this.draft=x?{...x,metrics:[...(x.metrics||[])],thresholds:this.json(x.thresholds)}:{name:'',description:'',datasetId:this.evalDatasets()[0]?.id||'',metrics:['relevance','instruction_adherence'],thresholds:'{"passRate":0.8,"relevance":0.7}',judgeModelProfile:'router-fast',enabled:true};this.modal.set('eval-definition');}
  toggleEvalMetric(name:string,checked:boolean){const set=new Set<string>(this.draft.metrics||[]);checked?set.add(name):set.delete(name);this.draft.metrics=[...set];}
  async saveEvalDefinition(){await this.run(async()=>{await this.api.saveEvalDefinition({name:this.draft.name,description:this.draft.description||'',datasetId:this.draft.datasetId,metrics:this.draft.metrics||[],thresholds:typeof this.draft.thresholds==='string'?JSON.parse(this.draft.thresholds):this.draft.thresholds,judgeModelProfile:this.draft.metrics?.length?this.draft.judgeModelProfile:null,enabled:this.draft.enabled!==false});this.evalDefinitions.set(await this.api.evalDefinitions());this.closeModal();});}
  async deleteEvalDefinition(x:EvalDefinition){if(confirm(`Delete eval ${x.name}?`))await this.run(async()=>{await this.api.deleteEvalDefinition(x.id);this.evalDefinitions.set(await this.api.evalDefinitions());});}
  async runEval(x:EvalDefinition){await this.run(async()=>{const previous=this.evalRuns().find(r=>r.definitionId===x.id&&r.status==='COMPLETED');await this.api.createEvalRun(x.id,previous?.id);this.evalRuns.set(await this.api.evalRuns());});}
  async inspectEvalRun(x:EvalRun){await this.run(async()=>{this.selectedEvalRun.set(await this.api.evalRun(x.id));this.modal.set('eval-run');});}

  async loadRuntime(){try{this.runtime.set(await this.api.runtime());}catch(e:any){this.error.set(this.message(e));}}
  filteredExecutions(){const q=this.search.toLowerCase();return this.executions().filter(x=>(!q||[x.executionId,x.commandName,x.intent,x.objective].some(v=>(v||'').toLowerCase().includes(q)))&&(!this.executionStatus||x.status===this.executionStatus));}
  async filterExecutions(){this.executions.set(await this.api.executions(this.executionStatus));}
  async openExecution(id:string,show=true){try{const [d,o,s,c,a]=await Promise.all([this.api.execution(id),this.api.orchestration(id),this.api.contextSnapshots(id),this.api.executionContext(id),this.api.executionArtifacts(id)]);this.selectedExecution.set(d);this.orchestration.set(o);this.contextSnapshots.set(s);this.executionContext.set(c);this.executionArtifacts.set(a);if(show)this.modal.set('execution');}catch(e:any){this.error.set(this.message(e));}}
  cancelModal(){
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
  closeModal(){this.modal.set(null);this.draft={};this.approvalComment='';}
  statusClass(s:string){return (s||'').toLowerCase().replaceAll('_','-');}
  tokens(v:any){return new Intl.NumberFormat('es-ES').format(Number(v||0));}
  runningEvalCount(){return this.evalRuns().filter(r=>r.status==='RUNNING').length;}
  regressionEvalCount(){return this.evalRuns().filter(r=>r.regression?.regressed).length;}
  date(v:any){return v?new Date(v).toLocaleString('es-ES'):'—';}
  json(v:any){return JSON.stringify(v??{},null,2);}
  short(v:string,n=80){return !v?'—':v.length>n?v.slice(0,n)+'…':v;}
  executionLevels(){const steps=this.orchestration()?.steps||[];const level=new Map<string,number>();let changed=true;while(changed){changed=false;for(const s of steps){const l=s.dependsOn?.length?Math.max(...s.dependsOn.map(d=>level.get(d)??0))+1:0;if(level.get(s.id)!==l){level.set(s.id,l);changed=true;}}}return [...new Set([...level.values()])].sort((a,b)=>a-b).map(l=>steps.filter(s=>level.get(s.id)===l));}
  canPause(){return ['RUNNING','RETRYING','ACCEPTED'].includes(this.selectedExecution()?.status||'');}
  canResume(){return this.selectedExecution()?.status==='PAUSED';}
  canRetry(){return this.selectedExecution()?.status==='FAILED';}
  async execAction(kind:'pause'|'resume'|'retry'|'cancel'){const id=this.selectedExecution()?.executionId;if(!id)return;await this.run(async()=>{if(kind==='pause')await this.api.pause(id);if(kind==='resume')await this.api.resume(id);if(kind==='retry')await this.api.retry(id);if(kind==='cancel')await this.api.cancel(id);await this.openExecution(id,false);});}
  async decide(executionId:string,stepId:string,approved:boolean){await this.run(async()=>{await this.api.approval(executionId,stepId,approved,this.actor,this.approvalComment|| (approved?'Approved from Control Plane':'Rejected from Control Plane'));this.approvals.set(await this.api.approvals());if(this.selectedExecution()?.executionId===executionId)await this.openExecution(executionId,false);this.approvalComment='';});}

  openCreateExecution(){this.draft={name:'control-plane-request',intent:'',sessionId:'',input:'{}',context:'{}',instructions:''};this.modal.set('create-execution');}
  async saveExecution(){await this.run(async()=>{const body={correlationId:crypto.randomUUID(),sessionId:this.draft.sessionId||null,command:{name:this.draft.name||null,intent:this.draft.intent,input:JSON.parse(this.draft.input||'{}'),context:JSON.parse(this.draft.context||'{}'),instructions:(this.draft.instructions||'').split('\n').filter(Boolean)}};const r=await this.api.createExecution(body);this.closeModal();await this.refreshAll();await this.openExecution(r.executionId);});}

  async loadSessions(){try{this.sessions.set(await this.api.sessions());}catch(e:any){this.error.set(this.message(e));}}
  openCreateSession(){this.draft={name:'',scope:'TENANT',ownerKey:'',expiresAt:'',metadata:'{}'};this.modal.set('session');}
  editSession(s:SessionInfo){this.draft={...s,expiresAt:s.expiresAt?new Date(s.expiresAt).toISOString().slice(0,16):'',metadata:this.json(s.metadata)};this.modal.set('session');}
  async saveSession(){await this.run(async()=>{const body={name:this.draft.name||null,scope:this.draft.scope,ownerKey:this.draft.ownerKey||null,expiresAt:this.draft.expiresAt?new Date(this.draft.expiresAt).toISOString():null,metadata:JSON.parse(this.draft.metadata||'{}')};if(this.draft.id)await this.api.updateSession(this.draft.id,body);else await this.api.createSession(body);this.sessions.set(await this.api.sessions());this.closeModal();});}
  async closeSessionItem(s:SessionInfo){if(confirm(`Close session ${s.name||s.id}?`))await this.run(async()=>{await this.api.closeSession(s.id);this.sessions.set(await this.api.sessions());if(this.selectedSession()?.id===s.id)this.selectedSession.set(null);});}
  async inspectSession(s:SessionInfo){await this.run(async()=>{const [ctx,execs]=await Promise.all([this.api.sessionContext(s.id),this.api.sessionExecutions(s.id)]);this.selectedSession.set(s);this.sessionContext.set(ctx);this.sessionExecutions.set(execs);this.modal.set('session-inspect');});}

  async loadMemory(){try{const [m,p,a]=await Promise.all([this.api.memories(),this.api.memoryPolicy(),this.api.memoryPolicyAudit()]);this.memories.set(m);this.memoryPolicy.set(p);this.memoryAudit.set(a);}catch(e:any){this.error.set(this.message(e));}}
  openCreateMemory(){this.draft={scopeType:'TENANT',scopeId:'',memoryType:'FACT',key:'',content:'',importance:0.5,expiresAt:''};this.modal.set('memory');}
  async saveMemory(){await this.run(async()=>{await this.api.createMemory({scopeType:this.draft.scopeType,scopeId:this.draft.scopeId,memoryType:this.draft.memoryType,key:this.draft.key||null,content:this.draft.content,importance:Number(this.draft.importance||0.5),expiresAt:this.draft.expiresAt?new Date(this.draft.expiresAt).toISOString():null});this.memories.set(await this.api.memories());this.closeModal();});}
  async revokeMemoryItem(m:MemoryInfo){if(confirm('Revoke this memory?'))await this.run(async()=>{await this.api.revokeMemory(m.id);this.memories.set(await this.api.memories());});}
  async searchMemory(){if(!this.memoryQuery||!this.memoryScopeId)return;await this.run(async()=>{this.memoryHits.set(await this.api.retrieveMemories(this.memoryQuery,[{scopeType:this.memoryScopeType,scopeId:this.memoryScopeId}],this.memoryTopK));});}

  editSkill(x?:Skill){ return resourceActions.editSkill.apply(this, arguments as any); }
  async saveSkill(){ return resourceActions.saveSkill.apply(this, arguments as any); }
  async deleteSkill(x:Skill){ return resourceActions.deleteSkill.apply(this, arguments as any); }
  editAgent(x?:Agent){ return resourceActions.editAgent.apply(this, arguments as any); }
  toggleSkill(name:string,checked:boolean){ return resourceActions.toggleSkill.apply(this, arguments as any); }
  async saveAgent(){ return resourceActions.saveAgent.apply(this, arguments as any); }
  async deleteAgent(x:Agent){ return resourceActions.deleteAgent.apply(this, arguments as any); }
  async editAgentKnowledge(x:Agent){ return resourceActions.editAgentKnowledge.apply(this, arguments as any); }
  setKbAssignment(name:string,value:string){ return resourceActions.setKbAssignment.apply(this, arguments as any); }
  async saveAgentKnowledge(){ return resourceActions.saveAgentKnowledge.apply(this, arguments as any); }
  editPrompt(x?:Prompt){ return resourceActions.editPrompt.apply(this, arguments as any); }
  async savePrompt(){ return resourceActions.savePrompt.apply(this, arguments as any); }
  async deletePrompt(x:Prompt){ return resourceActions.deletePrompt.apply(this, arguments as any); }
  editTool(x?:Tool){ return resourceActions.editTool.apply(this, arguments as any); }
  async saveTool(){ return resourceActions.saveTool.apply(this, arguments as any); }
  async deleteTool(x:Tool){ return resourceActions.deleteTool.apply(this, arguments as any); }
  editMcp(x?:McpServer){ return resourceActions.editMcp.apply(this, arguments as any); }
  async saveMcp(){ return resourceActions.saveMcp.apply(this, arguments as any); }
  async deleteMcp(x:McpServer){ return resourceActions.deleteMcp.apply(this, arguments as any); }
  editKb(x?:KnowledgeBase){ return resourceActions.editKb.apply(this, arguments as any); }
  async saveKb(){ return resourceActions.saveKb.apply(this, arguments as any); }
  async deleteKb(x:KnowledgeBase){ return resourceActions.deleteKb.apply(this, arguments as any); }
  async selectKb(x:KnowledgeBase){ return resourceActions.selectKb.apply(this, arguments as any); }
  async uploadFile(event:Event){ return resourceActions.uploadFile.apply(this, arguments as any); }
  addGoogle(){ return resourceActions.addGoogle.apply(this, arguments as any); }
  async saveGoogle(){ return resourceActions.saveGoogle.apply(this, arguments as any); }
  async reindex(d:KnowledgeDocument){ return resourceActions.reindex.apply(this, arguments as any); }
  async deleteDocument(d:KnowledgeDocument){ return resourceActions.deleteDocument.apply(this, arguments as any); }
  async retrieve(){ return resourceActions.retrieve.apply(this, arguments as any); }

  async loadProcesses(){ return definitionActions.loadProcesses.apply(this, arguments as any); }
  async refreshProcessesLive(){ return definitionActions.refreshProcessesLive.apply(this, arguments as any); }
  setProcessTab(tab:ProcessTab){ return definitionActions.setProcessTab.apply(this, arguments as any); }
  filteredProcessDefinitions(){ return definitionActions.filteredProcessDefinitions.apply(this, arguments as any); }
  filteredProcessInstances(){ return definitionActions.filteredProcessInstances.apply(this, arguments as any); }
  processDefinitionLevels(definition?:ProcessDefinition|null){ return definitionActions.processDefinitionLevels.apply(this, arguments as any); }
  processInstanceLevels(instance?:ProcessInstance|null){ return definitionActions.processInstanceLevels.apply(this, arguments as any); }
  openCreateProcessDefinition(){ return definitionActions.openCreateProcessDefinition.apply(this, arguments as any); }
  editProcessDefinition(x:ProcessDefinition){ return definitionActions.editProcessDefinition.apply(this, arguments as any); }
  addProcessStep(type:ProcessStepType){ return definitionActions.addProcessStep.apply(this, arguments as any); }
  editProcessStep(step:any){ return definitionActions.editProcessStep.apply(this, arguments as any); }
  saveProcessStep(){ return definitionActions.saveProcessStep.apply(this, arguments as any); }
  removeProcessStep(step:any){ return definitionActions.removeProcessStep.apply(this, arguments as any); }
  toggleProcessDependency(key:string,checked:boolean){ return definitionActions.toggleProcessDependency.apply(this, arguments as any); }
  async saveProcessDefinition(){ return definitionActions.saveProcessDefinition.apply(this, arguments as any); }
  async activateProcessDefinition(x:ProcessDefinition){ return definitionActions.activateProcessDefinition.apply(this, arguments as any); }
  async retireProcessDefinition(x:ProcessDefinition){ return definitionActions.retireProcessDefinition.apply(this, arguments as any); }
  async nextProcessDefinitionVersion(x:ProcessDefinition){ return definitionActions.nextProcessDefinitionVersion.apply(this, arguments as any); }
  openCreateProcessService(){ return serviceActions.openCreateProcessService.apply(this, arguments as any); }
  editProcessService(x:ProcessServiceDefinition){ return serviceActions.editProcessService.apply(this, arguments as any); }
  async saveProcessService(){ return serviceActions.saveProcessService.apply(this, arguments as any); }
  async activateProcessService(x:ProcessServiceDefinition){ return serviceActions.activateProcessService.apply(this, arguments as any); }
  async retireProcessService(x:ProcessServiceDefinition){ return serviceActions.retireProcessService.apply(this, arguments as any); }
  async nextProcessServiceVersion(x:ProcessServiceDefinition){ return serviceActions.nextProcessServiceVersion.apply(this, arguments as any); }
  openCreateProcessInstance(x?:ProcessDefinition){ return instanceActions.openCreateProcessInstance.apply(this, arguments as any); }
  selectProcessDefinitionForNewInstance(value:string){ return instanceActions.selectProcessDefinitionForNewInstance.apply(this, arguments as any); }
  activeProcessDefinitions(){ return instanceActions.activeProcessDefinitions.apply(this, arguments as any); }
  async saveProcessInstance(){ return instanceActions.saveProcessInstance.apply(this, arguments as any); }
  async openProcessInstance(id:string){ return instanceActions.openProcessInstance.apply(this, arguments as any); }
  async processInstanceAction(kind:'start'|'pause'|'resume'|'cancel'){ return instanceActions.processInstanceAction.apply(this, arguments as any); }
  async completeHumanTask(x:ProcessHumanTask,explicitDecision?:string){ return instanceActions.completeHumanTask.apply(this, arguments as any); }
  openSignalProcessEvent(x?:ProcessInstance){ return instanceActions.openSignalProcessEvent.apply(this, arguments as any); }
  async signalProcessEvent(){ return instanceActions.signalProcessEvent.apply(this, arguments as any); }
  processStatusLabel(status:string,type?:ProcessStepType){ return presentationActions.processStatusLabel.apply(this, arguments as any); }
  processDefinitionName(instance?:ProcessInstance|null){ return presentationActions.processDefinitionName.apply(this, arguments as any); }
  processStepName(instance:ProcessInstance|null|undefined,stepKey:string){ return presentationActions.processStepName.apply(this, arguments as any); }
  humanTaskProcessName(task:ProcessHumanTask){ return presentationActions.humanTaskProcessName.apply(this, arguments as any); }
  humanTaskStepName(task:ProcessHumanTask){ return presentationActions.humanTaskStepName.apply(this, arguments as any); }
  agentDisplayName(ref?:string|null){ return presentationActions.agentDisplayName.apply(this, arguments as any); }
  stepDisplayName(step:any){ return presentationActions.stepDisplayName.apply(this, arguments as any); }
  humanizeIdentifier(value?:string|null){ return presentationActions.humanizeIdentifier.apply(this, arguments as any); }
  processStepLabel(type:ProcessStepType){ return presentationActions.processStepLabel.apply(this, arguments as any); }
  processStepIcon(type:ProcessStepType){ return presentationActions.processStepIcon.apply(this, arguments as any); }
  defaultProcessStepConfiguration(type:ProcessStepType){ return presentationActions.defaultProcessStepConfiguration.apply(this, arguments as any); }
  selectReviewProducer(step:any,key:string){ return presentationActions.selectReviewProducer.apply(this, arguments as any); }
  reviewableProducerSteps(currentStepKey:string){ return presentationActions.reviewableProducerSteps.apply(this, arguments as any); }
  taskArtifactRefs(task:ProcessHumanTask){ return presentationActions.taskArtifactRefs.apply(this, arguments as any); }
  taskReviewArtifacts(task:ProcessHumanTask){ return presentationActions.taskReviewArtifacts.apply(this, arguments as any); }
  humanTaskProducerStep(task:ProcessHumanTask){ return presentationActions.humanTaskProducerStep.apply(this, arguments as any); }
  humanTaskProducerResult(task:ProcessHumanTask){ return presentationActions.humanTaskProducerResult.apply(this, arguments as any); }
  humanTaskProducerName(task:ProcessHumanTask){ return presentationActions.humanTaskProducerName.apply(this, arguments as any); }
  humanTaskLegacyReviewText(task:ProcessHumanTask){ return presentationActions.humanTaskLegacyReviewText.apply(this, arguments as any); }
  textDisplayBlocks(rawValue:string){ return presentationActions.textDisplayBlocks.apply(this, arguments as any); }
  unwrapStructuredText(rawValue:string){ return presentationActions.unwrapStructuredText.apply(this, arguments as any); }
  extractJsonStringField(rawValue:string,field:string){ return presentationActions.extractJsonStringField.apply(this, arguments as any); }
  markdownFrom(value:any,depth=0):string{ return presentationActions.markdownFrom.apply(this, arguments as any); }
  summaryFrom(value:any,depth=0):string{ return presentationActions.summaryFrom.apply(this, arguments as any); }
  artifactMarkdown(a:ExecutionArtifact){ return presentationActions.artifactMarkdown.apply(this, arguments as any); }
  artifactSummary(a:any){ return presentationActions.artifactSummary.apply(this, arguments as any); }
  artifactDisplayBlocks(a:ExecutionArtifact){ return presentationActions.artifactDisplayBlocks.apply(this, arguments as any); }
  toggleHumanTaskTechnical(task:ProcessHumanTask){ return presentationActions.toggleHumanTaskTechnical.apply(this, arguments as any); }
  isHumanTaskTechnicalOpen(task:ProcessHumanTask){ return presentationActions.isHumanTaskTechnicalOpen.apply(this, arguments as any); }
  trackByHumanTaskId(_index:number,task:ProcessHumanTask){ return presentationActions.trackByHumanTaskId.apply(this, arguments as any); }
  async openArtifact(ref:any){ return presentationActions.openArtifact.apply(this, arguments as any); }
  humanTaskReviewPolicy(task:ProcessHumanTask){ return presentationActions.humanTaskReviewPolicy.apply(this, arguments as any); }
  pendingProcessHumanTasks(){ return presentationActions.pendingProcessHumanTasks.apply(this, arguments as any); }
  activeProcessServices(){ return presentationActions.activeProcessServices.apply(this, arguments as any); }
  processProgress(x:ProcessInstance){ return presentationActions.processProgress.apply(this, arguments as any); }
  processCompletedSteps(x:ProcessInstance){ return presentationActions.processCompletedSteps.apply(this, arguments as any); }
  processWaitingSteps(x:ProcessInstance){ return presentationActions.processWaitingSteps.apply(this, arguments as any); }
  processServiceSelection(step:any){ return presentationActions.processServiceSelection.apply(this, arguments as any); }
  selectProcessService(step:any,value:string){ return presentationActions.selectProcessService.apply(this, arguments as any); }
  activeProcessServiceVersions(){ return presentationActions.activeProcessServiceVersions.apply(this, arguments as any); }
  processServiceName(step:any){ return presentationActions.processServiceName.apply(this, arguments as any); }
  selectedProcessDefinitionForInstance(){ return presentationActions.selectedProcessDefinitionForInstance.apply(this, arguments as any); }




  async run(fn:()=>Promise<any>){this.busy.set(true);this.error.set('');try{await fn();}catch(e:any){this.error.set(this.message(e));}finally{this.busy.set(false);}}
  message(e:any){return e?.error?.detail||e?.message||'Error inesperado';}
}
