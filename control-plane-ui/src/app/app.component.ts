import * as governanceActions from './features/governance/governance.actions';
import * as evalsActions from './features/evals/evals.actions';
import * as executionsActions from './features/executions/executions.actions';
import * as sessionsActions from './features/sessions/sessions.actions';
import * as memoryActions from './features/memory/memory.actions';
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

  async loadGovernance(){ return governanceActions.loadGovernance.apply(this, arguments as any); }
  editGovernancePolicy(x?:GovernancePolicy){ return governanceActions.editGovernancePolicy.apply(this, arguments as any); }
  async saveGovernancePolicy(){ return governanceActions.saveGovernancePolicy.apply(this, arguments as any); }
  async deleteGovernancePolicy(x:GovernancePolicy){ return governanceActions.deleteGovernancePolicy.apply(this, arguments as any); }
  editGovernanceBudget(x?:GovernanceBudget){ return governanceActions.editGovernanceBudget.apply(this, arguments as any); }
  async saveGovernanceBudget(){ return governanceActions.saveGovernanceBudget.apply(this, arguments as any); }
  async deleteGovernanceBudget(x:GovernanceBudget){ return governanceActions.deleteGovernanceBudget.apply(this, arguments as any); }
  async loadEvals(){ return evalsActions.loadEvals.apply(this, arguments as any); }
  editEvalDataset(x?:EvalDataset){ return evalsActions.editEvalDataset.apply(this, arguments as any); }
  async saveEvalDataset(){ return evalsActions.saveEvalDataset.apply(this, arguments as any); }
  async deleteEvalDataset(x:EvalDataset){ return evalsActions.deleteEvalDataset.apply(this, arguments as any); }
  editEvalDefinition(x?:EvalDefinition){ return evalsActions.editEvalDefinition.apply(this, arguments as any); }
  toggleEvalMetric(name:string,checked:boolean){ return evalsActions.toggleEvalMetric.apply(this, arguments as any); }
  async saveEvalDefinition(){ return evalsActions.saveEvalDefinition.apply(this, arguments as any); }
  async deleteEvalDefinition(x:EvalDefinition){ return evalsActions.deleteEvalDefinition.apply(this, arguments as any); }
  async runEval(x:EvalDefinition){ return evalsActions.runEval.apply(this, arguments as any); }
  async inspectEvalRun(x:EvalRun){ return evalsActions.inspectEvalRun.apply(this, arguments as any); }
  async loadRuntime(){ return executionsActions.loadRuntime.apply(this, arguments as any); }
  filteredExecutions(){ return executionsActions.filteredExecutions.apply(this, arguments as any); }
  async filterExecutions(){ return executionsActions.filterExecutions.apply(this, arguments as any); }
  async openExecution(id:string,show=true){ return executionsActions.openExecution.apply(this, arguments as any); }
  cancelModal(){ return executionsActions.cancelModal.apply(this, arguments as any); }
  closeModal(){ return executionsActions.closeModal.apply(this, arguments as any); }
  statusClass(s:string){ return executionsActions.statusClass.apply(this, arguments as any); }
  tokens(v:any){ return executionsActions.tokens.apply(this, arguments as any); }
  runningEvalCount(){ return executionsActions.runningEvalCount.apply(this, arguments as any); }
  regressionEvalCount(){ return executionsActions.regressionEvalCount.apply(this, arguments as any); }
  date(v:any){ return executionsActions.date.apply(this, arguments as any); }
  json(v:any){ return executionsActions.json.apply(this, arguments as any); }
  short(v:string,n=80){ return executionsActions.short.apply(this, arguments as any); }
  executionLevels(){ return executionsActions.executionLevels.apply(this, arguments as any); }
  canPause(){ return executionsActions.canPause.apply(this, arguments as any); }
  canResume(){ return executionsActions.canResume.apply(this, arguments as any); }
  canRetry(){ return executionsActions.canRetry.apply(this, arguments as any); }
  async execAction(kind:'pause'|'resume'|'retry'|'cancel'){ return executionsActions.execAction.apply(this, arguments as any); }
  async decide(executionId:string,stepId:string,approved:boolean){ return executionsActions.decide.apply(this, arguments as any); }
  openCreateExecution(){ return executionsActions.openCreateExecution.apply(this, arguments as any); }
  async saveExecution(){ return executionsActions.saveExecution.apply(this, arguments as any); }
  async loadSessions(){ return sessionsActions.loadSessions.apply(this, arguments as any); }
  openCreateSession(){ return sessionsActions.openCreateSession.apply(this, arguments as any); }
  editSession(s:SessionInfo){ return sessionsActions.editSession.apply(this, arguments as any); }
  async saveSession(){ return sessionsActions.saveSession.apply(this, arguments as any); }
  async closeSessionItem(s:SessionInfo){ return sessionsActions.closeSessionItem.apply(this, arguments as any); }
  async inspectSession(s:SessionInfo){ return sessionsActions.inspectSession.apply(this, arguments as any); }
  async loadMemory(){ return memoryActions.loadMemory.apply(this, arguments as any); }
  openCreateMemory(){ return memoryActions.openCreateMemory.apply(this, arguments as any); }
  async saveMemory(){ return memoryActions.saveMemory.apply(this, arguments as any); }
  async revokeMemoryItem(m:MemoryInfo){ return memoryActions.revokeMemoryItem.apply(this, arguments as any); }
  async searchMemory(){ return memoryActions.searchMemory.apply(this, arguments as any); }

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
