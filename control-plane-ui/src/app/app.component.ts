import { CommonModule } from '@angular/common';
import { Component, OnDestroy, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ApiService } from './api.service';
import { Agent, ContextSnapshot, ExecutionDetail, ExecutionSummary, KnowledgeBase, KnowledgeDocument, McpServer, MemoryInfo, Orchestration, Overview, PendingApproval, Prompt, RetrievalHit, RuntimeInfo, SessionInfo, Skill, Tool } from './models';

type View='dashboard'|'executions'|'approvals'|'sessions'|'memory'|'agents'|'skills'|'prompts'|'tools'|'mcp'|'knowledge'|'runtime';

@Component({selector:'app-root',standalone:true,imports:[CommonModule,FormsModule],templateUrl:'./app.component.html'})
export class AppComponent implements OnInit,OnDestroy {
  view=signal<View>('dashboard'); busy=signal(false); error=signal('');
  overview=signal<Overview|null>(null); runtime=signal<RuntimeInfo|null>(null);
  executions=signal<ExecutionSummary[]>([]); approvals=signal<PendingApproval[]>([]);
  agents=signal<Agent[]>([]); skills=signal<Skill[]>([]); prompts=signal<Prompt[]>([]); tools=signal<Tool[]>([]); mcpServers=signal<McpServer[]>([]);
  knowledgeBases=signal<KnowledgeBase[]>([]); documents=signal<KnowledgeDocument[]>([]); retrievalHits=signal<RetrievalHit[]>([]);
  sessions=signal<SessionInfo[]>([]); memories=signal<MemoryInfo[]>([]); contextSnapshots=signal<ContextSnapshot[]>([]);
  memoryPolicy=signal<any>(null); memoryAudit=signal<any[]>([]); selectedSession=signal<SessionInfo|null>(null); sessionContext=signal<any[]>([]); sessionExecutions=signal<any[]>([]);
  memoryQuery=''; memoryScopeType='SESSION'; memoryScopeId=''; memoryTopK=8; memoryHits=signal<MemoryInfo[]>([]);
  selectedExecution=signal<ExecutionDetail|null>(null); orchestration=signal<Orchestration|null>(null); selectedKb=signal<KnowledgeBase|null>(null);
  modal=signal<string|null>(null); draft:any={}; search=''; executionStatus=''; retrievalQuery=''; retrievalTopK=8; actor='operator'; approvalComment='';
  agentKnowledge=signal<any[]>([]); knowledgeDraft:Record<string,string>={}; private poller?:ReturnType<typeof setInterval>;

  constructor(public api:ApiService){}
  async ngOnInit(){await this.refreshAll();this.poller=setInterval(()=>this.refreshLive(),3000);}
  ngOnDestroy(){if(this.poller)clearInterval(this.poller);}
  async refreshAll(){await this.run(async()=>{const [o,r,e,a,ag,sk,pr,to,mc,kb,se,me,mp,ma]=await Promise.all([this.api.overview(),this.api.runtime(),this.api.executions(),this.api.approvals(),this.api.agents(),this.api.skills(),this.api.prompts(),this.api.tools(),this.api.mcpServers(),this.api.knowledgeBases(),this.api.sessions(),this.api.memories(),this.api.memoryPolicy(),this.api.memoryPolicyAudit()]);this.overview.set(o);this.runtime.set(r);this.executions.set(e);this.approvals.set(a);this.agents.set(ag);this.skills.set(sk);this.prompts.set(pr);this.tools.set(to);this.mcpServers.set(mc);this.knowledgeBases.set(kb);this.sessions.set(se);this.memories.set(me);this.memoryPolicy.set(mp);this.memoryAudit.set(ma);});}
  async refreshLive(){try{this.overview.set(await this.api.overview());this.executions.set(await this.api.executions(this.executionStatus));this.approvals.set(await this.api.approvals());if(this.selectedExecution())await this.openExecution(this.selectedExecution()!.executionId,false);}catch{}}
  setView(v:View){this.view.set(v);if(v==='runtime')this.loadRuntime();if(v==='sessions')this.loadSessions();if(v==='memory')this.loadMemory();}
  async loadRuntime(){try{this.runtime.set(await this.api.runtime());}catch(e:any){this.error.set(this.message(e));}}
  filteredExecutions(){const q=this.search.toLowerCase();return this.executions().filter(x=>(!q||[x.executionId,x.commandName,x.intent,x.objective].some(v=>(v||'').toLowerCase().includes(q)))&&(!this.executionStatus||x.status===this.executionStatus));}
  async filterExecutions(){this.executions.set(await this.api.executions(this.executionStatus));}
  async openExecution(id:string,show=true){try{const [d,o,s]=await Promise.all([this.api.execution(id),this.api.orchestration(id),this.api.contextSnapshots(id)]);this.selectedExecution.set(d);this.orchestration.set(o);this.contextSnapshots.set(s);if(show)this.modal.set('execution');}catch(e:any){this.error.set(this.message(e));}}
  closeModal(){this.modal.set(null);this.draft={};this.approvalComment='';}
  statusClass(s:string){return (s||'').toLowerCase().replaceAll('_','-');}
  tokens(v:any){return new Intl.NumberFormat('es-ES').format(Number(v||0));}
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

  private async run(fn:()=>Promise<any>){this.busy.set(true);this.error.set('');try{await fn();}catch(e:any){this.error.set(this.message(e));}finally{this.busy.set(false);}}
  private message(e:any){return e?.error?.detail||e?.message||'Error inesperado';}
}
