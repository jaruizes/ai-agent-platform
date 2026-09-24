import { CommonModule } from '@angular/common';
import { Component, OnDestroy, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ApiService } from './api.service';
import { Agent, BudgetDecision, ContextSnapshot, EvalDataset, EvalDefinition, EvalRun, ExecutionDetail, ExecutionSummary, GovernanceBudget, GovernanceDecision, GovernancePolicy, KnowledgeBase, KnowledgeDocument, McpServer, MemoryInfo, Orchestration, Overview, PendingApproval, ProcessDefinition, ProcessHumanTask, ProcessInstance, ProcessServiceDefinition, ProcessStepDefinition, ProcessStepType, Prompt, RetrievalHit, RuntimeInfo, SessionInfo, Skill, Tool } from './models';

type View='dashboard'|'executions'|'approvals'|'processes'|'sessions'|'memory'|'agents'|'skills'|'prompts'|'tools'|'mcp'|'knowledge'|'governance'|'evals'|'runtime';
type ProcessTab='definitions'|'instances'|'services'|'human';

@Component({selector:'app-root',standalone:true,imports:[CommonModule,FormsModule],templateUrl:'./app.component.html'})
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
  selectedExecution=signal<ExecutionDetail|null>(null); orchestration=signal<Orchestration|null>(null); selectedKb=signal<KnowledgeBase|null>(null);
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
  processSignalEventType='';
  processSignalCorrelation='';
  processSignalPayload='{}';

  private poller?:ReturnType<typeof setInterval>;

  constructor(public api:ApiService){}
  async ngOnInit(){await this.refreshAll();this.poller=setInterval(()=>this.refreshLive(),3000);}
  ngOnDestroy(){if(this.poller)clearInterval(this.poller);}
  async refreshAll(){await this.run(async()=>{const [o,r,e,a,ag,sk,pr,to,mc,kb,se,me,mp,ma,gp,gb,gd,bd,ed,ef,er]=await Promise.all([this.api.overview(),this.api.runtime(),this.api.executions(),this.api.approvals(),this.api.agents(),this.api.skills(),this.api.prompts(),this.api.tools(),this.api.mcpServers(),this.api.knowledgeBases(),this.api.sessions(),this.api.memories(),this.api.memoryPolicy(),this.api.memoryPolicyAudit(),this.api.governancePolicies(),this.api.governanceBudgets(),this.api.governanceDecisions(),this.api.budgetDecisions(),this.api.evalDatasets(),this.api.evalDefinitions(),this.api.evalRuns()]);this.overview.set(o);this.runtime.set(r);this.executions.set(e);this.approvals.set(a);this.agents.set(ag);this.skills.set(sk);this.prompts.set(pr);this.tools.set(to);this.mcpServers.set(mc);this.knowledgeBases.set(kb);this.sessions.set(se);this.memories.set(me);this.memoryPolicy.set(mp);this.memoryAudit.set(ma);this.governancePolicies.set(gp);this.governanceBudgets.set(gb);this.governanceDecisions.set(gd);this.budgetDecisions.set(bd);this.evalDatasets.set(ed);this.evalDefinitions.set(ef);this.evalRuns.set(er);});}
  async refreshLive(){try{this.overview.set(await this.api.overview());this.executions.set(await this.api.executions(this.executionStatus));this.approvals.set(await this.api.approvals());if(this.selectedExecution())await this.openExecution(this.selectedExecution()!.executionId,false);if(this.view()==='processes')await this.refreshProcessesLive();}catch{}}
  setView(v:View){this.view.set(v);if(v==='runtime')this.loadRuntime();if(v==='sessions')this.loadSessions();if(v==='memory')this.loadMemory();if(v==='governance')this.loadGovernance();if(v==='evals')this.loadEvals();if(v==='processes')this.loadProcesses();}

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
  async openExecution(id:string,show=true){try{const [d,o,s,c]=await Promise.all([this.api.execution(id),this.api.orchestration(id),this.api.contextSnapshots(id),this.api.executionContext(id)]);this.selectedExecution.set(d);this.orchestration.set(o);this.contextSnapshots.set(s);this.executionContext.set(c);if(show)this.modal.set('execution');}catch(e:any){this.error.set(this.message(e));}}
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

  editSkill(x?:Skill){this.draft=x?{...x}:{name:'',description:'',instructions:'',enabled:true};this.modal.set('skill');}
  async saveSkill(){await this.run(async()=>{await this.api.saveSkill(this.draft);this.skills.set(await this.api.skills());this.closeModal();});}
  async deleteSkill(x:Skill){if(confirm(`Eliminar skill ${x.name}?`))await this.run(async()=>{await this.api.deleteSkill(x.id);this.skills.set(await this.api.skills());});}
  editAgent(x?:Agent){this.draft=x?{...x,skills:x.skills.map(s=>s.name)}:{name:'',description:'',instructions:'',skills:[],enabled:true};this.modal.set('agent');}
  toggleSkill(name:string,checked:boolean){const set=new Set<string>(this.draft.skills||[]);checked?set.add(name):set.delete(name);this.draft.skills=[...set];}
  async saveAgent(){await this.run(async()=>{await this.api.saveAgent(this.draft);this.agents.set(await this.api.agents());this.closeModal();});}
  async deleteAgent(x:Agent){if(confirm(`Eliminar agente ${x.name}?`))await this.run(async()=>{await this.api.deleteAgent(x.id);this.agents.set(await this.api.agents());});}
  async editAgentKnowledge(x:Agent){this.draft={...x};const assigned=await this.api.agentKnowledge(x.id);this.agentKnowledge.set(assigned);this.knowledgeDraft={};for(const a of assigned)this.knowledgeDraft[a.name]=a.usageMode;this.modal.set('agent-knowledge');}
  setKbAssignment(name:string,value:string){if(value)this.knowledgeDraft[name]=value;else delete this.knowledgeDraft[name];}
  async saveAgentKnowledge(){await this.run(async()=>{const items=Object.entries(this.knowledgeDraft).map(([name,usageMode])=>({name,usageMode}));await this.api.saveAgentKnowledge(this.draft.id,items);this.closeModal();});}

  editPrompt(x?:Prompt){this.draft=x?{...x}:{name:'',description:'',content:'',version:1,enabled:true};this.modal.set('prompt');}
  async savePrompt(){await this.run(async()=>{await this.api.savePrompt(this.draft);this.prompts.set(await this.api.prompts());this.closeModal();});}
  async deletePrompt(x:Prompt){if(confirm(`Eliminar prompt ${x.name}?`))await this.run(async()=>{await this.api.deletePrompt(x.id);this.prompts.set(await this.api.prompts());});}

  editTool(x?:Tool){this.draft=x?{...x,configuration:this.json(x.configuration),inputSchema:this.json(x.inputSchema)}:{name:'',description:'',instructions:'',implementationType:'MCP',configuration:'{}',inputSchema:'{}',sideEffect:'READ',approvalPolicy:'NEVER',enabled:true};this.modal.set('tool');}
  async saveTool(){await this.run(async()=>{await this.api.saveTool(this.draft);this.tools.set(await this.api.tools());this.closeModal();});}
  async deleteTool(x:Tool){if(confirm(`Eliminar tool ${x.name}?`))await this.run(async()=>{await this.api.deleteTool(x.id);this.tools.set(await this.api.tools());});}

  editMcp(x?:McpServer){this.draft=x?{...x,args:this.json(x.args),environment:this.json(x.environment)}:{name:'',description:'',command:'',args:'[]',cwd:'',environment:'{}',enabled:true};this.modal.set('mcp');}
  async saveMcp(){await this.run(async()=>{await this.api.saveMcp(this.draft);this.mcpServers.set(await this.api.mcpServers());this.closeModal();});}
  async deleteMcp(x:McpServer){if(confirm(`Eliminar MCP server ${x.name}?`))await this.run(async()=>{await this.api.deleteMcp(x.id);this.mcpServers.set(await this.api.mcpServers());});}

  editKb(x?:KnowledgeBase){this.draft=x?{...x}:{name:'',description:'',scope:'TENANT',retentionPolicy:'PERSISTENT',enabled:true,chunkingPolicy:{strategy:'PARAGRAPH',chunkSize:1600,overlap:200,parentSize:6000,childSize:1600,childOverlap:200},metadata:{}};this.modal.set('kb');}
  async saveKb(){await this.run(async()=>{await this.api.saveKnowledgeBase(this.draft);this.knowledgeBases.set(await this.api.knowledgeBases());this.closeModal();});}
  async deleteKb(x:KnowledgeBase){if(confirm(`Eliminar knowledge base ${x.name}?`))await this.run(async()=>{await this.api.deleteKnowledgeBase(x.id);this.knowledgeBases.set(await this.api.knowledgeBases());if(this.selectedKb()?.id===x.id)this.selectedKb.set(null);});}
  async selectKb(x:KnowledgeBase){this.selectedKb.set(x);this.documents.set(await this.api.documents(x.id));this.retrievalHits.set([]);}
  async uploadFile(event:Event){const file=(event.target as HTMLInputElement).files?.[0],kb=this.selectedKb();if(!file||!kb)return;await this.run(async()=>{await this.api.upload(kb.id,file);this.documents.set(await this.api.documents(kb.id));});}
  addGoogle(){this.draft={sourceType:'GOOGLE_DOCS',sourceId:'',name:'',sourceUri:'',metadata:{}};this.modal.set('google-doc');}
  async saveGoogle(){const kb=this.selectedKb();if(!kb)return;await this.run(async()=>{await this.api.addGoogleDocument(kb.id,this.draft);this.documents.set(await this.api.documents(kb.id));this.closeModal();});}
  async reindex(d:KnowledgeDocument){await this.run(async()=>{await this.api.reindexDocument(d.id);if(this.selectedKb())this.documents.set(await this.api.documents(this.selectedKb()!.id));});}
  async deleteDocument(d:KnowledgeDocument){if(confirm(`Eliminar documento ${d.name}?`))await this.run(async()=>{await this.api.deleteDocument(d.id);if(this.selectedKb())this.documents.set(await this.api.documents(this.selectedKb()!.id));});}
  async retrieve(){const kb=this.selectedKb();if(!kb||!this.retrievalQuery)return;await this.run(async()=>this.retrievalHits.set(await this.api.retrieve(this.retrievalQuery,[kb.name],this.retrievalTopK)));}


  async loadProcesses(){
    await this.run(async()=>{
      const [definitions,services,instances,human]=await Promise.all([
        this.api.processDefinitions(),
        this.api.processServices(),
        this.api.processInstances(),
        this.api.processHumanTasks()
      ]);
      this.processDefinitions.set(definitions);
      this.processServices.set(services);
      this.processInstances.set(instances);
      this.processHumanTasks.set(human);
    });
  }

  async refreshProcessesLive(){
    const [instances,human]=await Promise.all([
      this.api.processInstances(),
      this.api.processHumanTasks()
    ]);
    this.processInstances.set(instances);
    this.processHumanTasks.set(human);
    if(this.selectedProcessInstance()){
      const updated=await this.api.processInstance(this.selectedProcessInstance()!.id);
      this.selectedProcessInstance.set(updated);
    }
  }

  setProcessTab(tab:ProcessTab){this.processTab.set(tab);}

  filteredProcessDefinitions(){
    const q=this.processDefinitionSearch.toLowerCase();
    return this.processDefinitions().filter(x=>!q||[x.definitionKey,x.name,x.description].some(v=>(v||'').toLowerCase().includes(q)));
  }

  filteredProcessInstances(){
    const q=this.processInstanceSearch.toLowerCase();
    return this.processInstances().filter(x=>!q||[x.id,x.definitionKey,x.correlationId,x.status].some(v=>(v||'').toLowerCase().includes(q)));
  }

  processDefinitionLevels(definition?:ProcessDefinition|null){
    const steps=definition?.steps||[];
    const level=new Map<string,number>();
    let changed=true,guard=0;
    while(changed&&guard++<steps.length+2){
      changed=false;
      for(const s of steps){
        const l=s.dependsOn?.length?Math.max(...s.dependsOn.map(d=>level.get(d)??0))+1:0;
        if(level.get(s.stepKey)!==l){level.set(s.stepKey,l);changed=true;}
      }
    }
    return [...new Set([...level.values()])].sort((a,b)=>a-b).map(l=>steps.filter(s=>level.get(s.stepKey)===l));
  }

  processInstanceLevels(instance?:ProcessInstance|null){
    const steps=instance?.steps||[];
    const definition=this.processDefinitions().find(d=>d.id===instance?.definitionId);
    const defs=new Map((definition?.steps||[]).map(s=>[s.stepKey,s]));
    const level=new Map<string,number>();
    let changed=true,guard=0;
    while(changed&&guard++<steps.length+2){
      changed=false;
      for(const s of steps){
        const deps=defs.get(s.stepKey)?.dependsOn||[];
        const l=deps.length?Math.max(...deps.map(d=>level.get(d)??0))+1:0;
        if(level.get(s.stepKey)!==l){level.set(s.stepKey,l);changed=true;}
      }
    }
    return [...new Set([...level.values()])].sort((a,b)=>a-b).map(l=>steps.filter(s=>level.get(s.stepKey)===l));
  }

  openCreateProcessDefinition(){
    this.processDesigner.set({
      id:null,definitionKey:'',name:'',description:'',version:1,status:'DRAFT',
      inputSchema:'{"type":"object"}',outputSchema:'{"type":"object"}',steps:[]
    });
    this.selectedProcessDefinition.set(null);
    this.modal.set('process-designer');
  }

  editProcessDefinition(x:ProcessDefinition){
    this.selectedProcessDefinition.set(x);
    this.processDesigner.set({
      ...x,
      inputSchema:this.json(x.inputSchema),
      outputSchema:this.json(x.outputSchema),
      steps:x.steps.map(s=>({...s,inputSchema:this.json(s.inputSchema),outputSchema:this.json(s.outputSchema),configuration:{...(s.configuration||{})}}))
    });
    this.modal.set('process-designer');
  }

  addProcessStep(type:ProcessStepType){
    const d=this.processDesigner();if(!d)return;
    const index=(d.steps?.length||0)+1;
    const step:any={
      stepKey:`${type.toLowerCase()}-${index}`,
      name:this.processStepLabel(type),
      description:'',
      type,
      dependsOn:[],
      inputSchema:'{"type":"object"}',
      outputSchema:'{"type":"object"}',
      configuration:this.defaultProcessStepConfiguration(type)
    };
    d.steps=[...(d.steps||[]),step];
    this.processDesigner.set({...d});
    this.editProcessStep(step);
  }

  editProcessStep(step:any){
    this.processStepDraft.set({
      ...step,
      originalStepKey:step.stepKey,
      dependsOn:[...(step.dependsOn||[])],
      configuration:{...(step.configuration||{})},
      inputSchema:typeof step.inputSchema==='string'?step.inputSchema:this.json(step.inputSchema),
      outputSchema:typeof step.outputSchema==='string'?step.outputSchema:this.json(step.outputSchema),
      instructions:Array.isArray(step.configuration?.instructions)?step.configuration.instructions.join('\n'):'',
      metadata:this.json(step.configuration?.metadata||{}),
      whenDecisionStep:step.configuration?.when?.decisionStep||'',
      whenEquals:step.configuration?.when?.equals??'',
      retryMaxAttempts:step.configuration?.retry?.maxAttempts||1,
      retryBackoffMs:step.configuration?.retry?.backoffMs||0,
      timeoutSeconds:step.configuration?.timeoutSeconds||null
    });
    this.modal.set('process-step');
  }

  saveProcessStep(){
    const d=this.processDesigner(),s=this.processStepDraft();if(!d||!s)return;
    const config:any={...(s.configuration||{})};
    delete config.when;delete config.retry;delete config.timeoutSeconds;
    if(s.type==='AGENTIC_EXECUTION'){
      config.intent=s.configuration?.intent||'';
      config.instructions=(s.instructions||'').split('\n').map((x:string)=>x.trim()).filter(Boolean);
      config.metadata=JSON.parse(s.metadata||'{}');
    }
    if(s.whenDecisionStep)config.when={decisionStep:s.whenDecisionStep,equals:s.whenEquals};
    if(Number(s.retryMaxAttempts)>1||Number(s.retryBackoffMs)>0)config.retry={maxAttempts:Number(s.retryMaxAttempts||1),backoffMs:Number(s.retryBackoffMs||0)};
    if(s.timeoutSeconds)config.timeoutSeconds=Number(s.timeoutSeconds);

    const normalized={
      ...s,
      dependsOn:[...(s.dependsOn||[])],
      inputSchema:s.inputSchema||'{}',
      outputSchema:s.outputSchema||'{}',
      configuration:config
    };
    const steps=[...(d.steps||[])];
    const i=steps.findIndex((x:any)=>x===s||x.id&&s.id&&x.id===s.id||x.stepKey===s.originalStepKey);
    const existingIndex=i>=0?i:steps.findIndex((x:any)=>x.stepKey===s.stepKey);
    if(existingIndex>=0)steps[existingIndex]=normalized;else steps.push(normalized);
    d.steps=steps;
    this.processDesigner.set({...d});
    this.processStepDraft.set(null);
    this.modal.set('process-designer');
  }

  removeProcessStep(step:any){
    const d=this.processDesigner();if(!d||d.status!=='DRAFT')return;
    if(!confirm(`Remove step ${step.stepKey}?`))return;
    d.steps=(d.steps||[]).filter((x:any)=>x.stepKey!==step.stepKey)
      .map((x:any)=>({...x,dependsOn:(x.dependsOn||[]).filter((k:string)=>k!==step.stepKey)}));
    this.processDesigner.set({...d});
  }

  toggleProcessDependency(key:string,checked:boolean){
    const s=this.processStepDraft();if(!s)return;
    const deps=new Set<string>(s.dependsOn||[]);
    checked?deps.add(key):deps.delete(key);
    s.dependsOn=[...deps];
    this.processStepDraft.set({...s});
  }

  async saveProcessDefinition(){
    const d=this.processDesigner();if(!d)return;
    await this.run(async()=>{
      const body={
        ...d,
        inputSchema:JSON.parse(d.inputSchema||'{}'),
        outputSchema:JSON.parse(d.outputSchema||'{}'),
        steps:(d.steps||[]).map((s:any)=>({
          id:s.id||null,stepKey:s.stepKey,name:s.name,description:s.description||'',type:s.type,
          dependsOn:s.dependsOn||[],
          inputSchema:typeof s.inputSchema==='string'?JSON.parse(s.inputSchema||'{}'):s.inputSchema,
          outputSchema:typeof s.outputSchema==='string'?JSON.parse(s.outputSchema||'{}'):s.outputSchema,
          configuration:s.configuration||{}
        }))
      };
      const saved=await this.api.saveProcessDefinition(body);
      this.processDefinitions.set(await this.api.processDefinitions());
      this.processDesigner.set(null);this.selectedProcessDefinition.set(saved);this.closeModal();
    });
  }

  async activateProcessDefinition(x:ProcessDefinition){
    if(!confirm(`Activate ${x.definitionKey} v${x.version}? The version becomes immutable.`))return;
    await this.run(async()=>{const saved=await this.api.activateProcessDefinition(x.id);this.processDefinitions.set(await this.api.processDefinitions());this.selectedProcessDefinition.set(saved);});
  }
  async retireProcessDefinition(x:ProcessDefinition){await this.run(async()=>{await this.api.retireProcessDefinition(x.id);this.processDefinitions.set(await this.api.processDefinitions());});}
  async nextProcessDefinitionVersion(x:ProcessDefinition){await this.run(async()=>{const v=await this.api.nextProcessDefinitionVersion(x.id);this.processDefinitions.set(await this.api.processDefinitions());this.editProcessDefinition(v);});}

  openCreateProcessService(){
    this.draft={serviceKey:'',name:'',description:'',version:1,implementationKey:'http',configuration:'{"url":"http://service:8080/api","method":"POST"}',inputSchema:'{"type":"object"}',outputSchema:'{"type":"object"}'};
    this.modal.set('process-service');
  }
  editProcessService(x:ProcessServiceDefinition){
    this.draft={...x,configuration:this.json(x.configuration),inputSchema:this.json(x.inputSchema),outputSchema:this.json(x.outputSchema)};
    this.modal.set('process-service');
  }
  async saveProcessService(){await this.run(async()=>{await this.api.saveProcessService(this.draft);this.processServices.set(await this.api.processServices());this.closeModal();});}
  async activateProcessService(x:ProcessServiceDefinition){await this.run(async()=>{await this.api.activateProcessService(x.id);this.processServices.set(await this.api.processServices());});}
  async retireProcessService(x:ProcessServiceDefinition){await this.run(async()=>{await this.api.retireProcessService(x.id);this.processServices.set(await this.api.processServices());});}
  async nextProcessServiceVersion(x:ProcessServiceDefinition){await this.run(async()=>{const v=await this.api.nextProcessServiceVersion(x.id);this.processServices.set(await this.api.processServices());this.editProcessService(v);});}

  openCreateProcessInstance(x?:ProcessDefinition){
    const active=x||(this.processDefinitions().find(d=>d.status==='ACTIVE'));
    this.draft={definitionKey:active?.definitionKey||'',version:active?.version||null,correlationId:crypto.randomUUID(),input:'{}',context:'{}',start:true};
    this.modal.set('process-instance-create');
  }
  async saveProcessInstance(){
    await this.run(async()=>{
      const body={definitionKey:this.draft.definitionKey,version:this.draft.version?Number(this.draft.version):null,correlationId:this.draft.correlationId||crypto.randomUUID(),input:JSON.parse(this.draft.input||'{}'),context:JSON.parse(this.draft.context||'{}')};
      const created=await this.api.createProcessInstance(body);
      if(this.draft.start!==false)await this.api.startProcessInstance(created.id);
      this.processInstances.set(await this.api.processInstances());
      this.closeModal();
      await this.openProcessInstance(created.id);
    });
  }

  async openProcessInstance(id:string){
    await this.run(async()=>{const x=await this.api.processInstance(id);this.selectedProcessInstance.set(x);this.modal.set('process-instance');});
  }
  async processInstanceAction(kind:'start'|'pause'|'resume'|'cancel'){
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

  async completeHumanTask(x:ProcessHumanTask){
    await this.run(async()=>{
      await this.api.completeProcessHumanTask(x.id,this.processHumanDecision,JSON.parse(this.processHumanResult||'{}'));
      this.processHumanTasks.set(await this.api.processHumanTasks());
      this.processInstances.set(await this.api.processInstances());
    });
  }

  openSignalProcessEvent(x?:ProcessInstance){
    this.processSignalEventType='';
    this.processSignalCorrelation=x?.correlationId||'';
    this.processSignalPayload='{}';
    this.modal.set('process-event');
  }
  async signalProcessEvent(){
    await this.run(async()=>{
      await this.api.signalProcessEvent(this.processSignalEventType,this.processSignalCorrelation,JSON.parse(this.processSignalPayload||'{}'));
      this.closeModal();
      await this.refreshProcessesLive();
    });
  }

  processStepLabel(type:ProcessStepType){
    return ({SERVICE:'Service',AGENTIC_EXECUTION:'Agentic execution',DECISION:'Decision',HUMAN:'Human task',WAIT_EVENT:'Wait event',SUBPROCESS:'Subprocess'} as any)[type]||type;
  }

  processStepIcon(type:ProcessStepType){
    return ({SERVICE:'↗',AGENTIC_EXECUTION:'◎',DECISION:'◇',HUMAN:'♙',WAIT_EVENT:'◷',SUBPROCESS:'▣'} as any)[type]||'•';
  }

  defaultProcessStepConfiguration(type:ProcessStepType){
    if(type==='SERVICE')return {serviceKey:this.processServices().find(s=>s.status==='ACTIVE')?.serviceKey||''};
    if(type==='AGENTIC_EXECUTION')return {intent:'',instructions:[],metadata:{}};
    if(type==='DECISION')return {path:'processInput.value',operator:'EQ',value:true,onTrue:'TRUE',onFalse:'FALSE'};
    if(type==='HUMAN')return {title:'Human approval',description:''};
    if(type==='WAIT_EVENT')return {eventType:'event.received'};
    return {};
  }

  pendingProcessHumanTasks(){return this.processHumanTasks().filter(x=>x.status==='PENDING').length;}
  activeProcessServices(){return this.processServices().filter(x=>x.status==='ACTIVE').length;}
  processProgress(x:ProcessInstance){return x.steps.filter(s=>s.status==='COMPLETED'||s.status==='SKIPPED').length;}
  processCompletedSteps(x:ProcessInstance){return x.steps.filter(s=>s.status==='COMPLETED').length;}
  processWaitingSteps(x:ProcessInstance){return x.steps.filter(s=>s.status==='WAITING').length;}

  processServiceName(step:any){
    if(step.type!=='SERVICE')return '';
    const key=step.configuration?.serviceKey,version=step.configuration?.serviceVersion;
    const svc=this.processServices().find(s=>s.serviceKey===key&&(!version||s.version===version));
    return svc?`${svc.name} · v${svc.version}`:key||'No service selected';
  }

  selectedProcessDefinitionForInstance(){
    const x=this.selectedProcessInstance();
    return x?this.processDefinitions().find(d=>d.id===x.definitionId)||null:null;
  }

  private async run(fn:()=>Promise<any>){this.busy.set(true);this.error.set('');try{await fn();}catch(e:any){this.error.set(this.message(e));}finally{this.busy.set(false);}}
  private message(e:any){return e?.error?.detail||e?.message||'Error inesperado';}
}
