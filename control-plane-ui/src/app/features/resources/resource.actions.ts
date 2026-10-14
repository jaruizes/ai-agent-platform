import type { AppComponent } from '../../app.component';
import type { Agent, BudgetDecision, ContextSnapshot, EvalDataset, EvalDefinition, EvalRun, ExecutionArtifact, ExecutionDetail, ExecutionSummary, GovernanceBudget, GovernanceDecision, GovernancePolicy, KnowledgeBase, KnowledgeDocument, McpServer, MemoryInfo, Orchestration, Overview, PendingApproval, ProcessDefinition, ProcessHumanTask, ProcessInstance, ProcessServiceDefinition, ProcessStepDefinition, ProcessStepType, Prompt, RetrievalHit, RuntimeInfo, SessionInfo, Skill, Tool } from '../../models';

/** Domain operations for agent resources, tools, MCP, and knowledge. */
export function editSkill(this: AppComponent, x?:Skill){this.draft=x?{...x}:{name:'',description:'',instructions:'',enabled:true};this.modal.set('skill');}

export function async function saveSkill(this: AppComponent, ){await this.run(async()=>{await this.api.saveSkill(this.draft);this.skills.set(await this.api.skills());this.closeModal();});}

export function async function deleteSkill(this: AppComponent, x:Skill){if(confirm(`Eliminar skill ${x.name}?`))await this.run(async()=>{await this.api.deleteSkill(x.id);this.skills.set(await this.api.skills());});}

export function editAgent(this: AppComponent, x?:Agent){this.draft=x?{...x,skills:x.skills.map(s=>s.name)}:{name:'',description:'',instructions:'',skills:[],enabled:true};this.modal.set('agent');}

export function toggleSkill(this: AppComponent, name:string,checked:boolean){const set=new Set<string>(this.draft.skills||[]);checked?set.add(name):set.delete(name);this.draft.skills=[...set];}

export function async function saveAgent(this: AppComponent, ){await this.run(async()=>{await this.api.saveAgent(this.draft);this.agents.set(await this.api.agents());this.closeModal();});}

export function async function deleteAgent(this: AppComponent, x:Agent){if(confirm(`Eliminar agente ${x.name}?`))await this.run(async()=>{await this.api.deleteAgent(x.id);this.agents.set(await this.api.agents());});}

export function async function editAgentKnowledge(this: AppComponent, x:Agent){this.draft={...x};const assigned=await this.api.agentKnowledge(x.id);this.agentKnowledge.set(assigned);this.knowledgeDraft={};for(const a of assigned)this.knowledgeDraft[a.name]=a.usageMode;this.modal.set('agent-knowledge');}

export function setKbAssignment(this: AppComponent, name:string,value:string){if(value)this.knowledgeDraft[name]=value;else delete this.knowledgeDraft[name];}

export function async function saveAgentKnowledge(this: AppComponent, ){await this.run(async()=>{const items=Object.entries(this.knowledgeDraft).map(([name,usageMode])=>({name,usageMode}));await this.api.saveAgentKnowledge(this.draft.id,items);this.closeModal();});}

export function editPrompt(this: AppComponent, x?:Prompt){this.draft=x?{...x}:{name:'',description:'',content:'',version:1,enabled:true};this.modal.set('prompt');}

export function async function savePrompt(this: AppComponent, ){await this.run(async()=>{await this.api.savePrompt(this.draft);this.prompts.set(await this.api.prompts());this.closeModal();});}

export function async function deletePrompt(this: AppComponent, x:Prompt){if(confirm(`Eliminar prompt ${x.name}?`))await this.run(async()=>{await this.api.deletePrompt(x.id);this.prompts.set(await this.api.prompts());});}

export function editTool(this: AppComponent, x?:Tool){this.draft=x?{...x,configuration:this.json(x.configuration),inputSchema:this.json(x.inputSchema)}:{name:'',description:'',instructions:'',implementationType:'MCP',configuration:'{}',inputSchema:'{}',sideEffect:'READ',approvalPolicy:'NEVER',enabled:true};this.modal.set('tool');}

export function async function saveTool(this: AppComponent, ){await this.run(async()=>{await this.api.saveTool(this.draft);this.tools.set(await this.api.tools());this.closeModal();});}

export function async function deleteTool(this: AppComponent, x:Tool){if(confirm(`Eliminar tool ${x.name}?`))await this.run(async()=>{await this.api.deleteTool(x.id);this.tools.set(await this.api.tools());});}

export function editMcp(this: AppComponent, x?:McpServer){this.draft=x?{...x,args:this.json(x.args),environment:this.json(x.environment)}:{name:'',description:'',command:'',args:'[]',cwd:'',environment:'{}',enabled:true};this.modal.set('mcp');}

export function async function saveMcp(this: AppComponent, ){await this.run(async()=>{await this.api.saveMcp(this.draft);this.mcpServers.set(await this.api.mcpServers());this.closeModal();});}

export function async function deleteMcp(this: AppComponent, x:McpServer){if(confirm(`Eliminar MCP server ${x.name}?`))await this.run(async()=>{await this.api.deleteMcp(x.id);this.mcpServers.set(await this.api.mcpServers());});}

export function editKb(this: AppComponent, x?:KnowledgeBase){this.draft=x?{...x}:{name:'',description:'',scope:'TENANT',retentionPolicy:'PERSISTENT',enabled:true,chunkingPolicy:{strategy:'PARAGRAPH',chunkSize:1600,overlap:200,parentSize:6000,childSize:1600,childOverlap:200},metadata:{}};this.modal.set('kb');}

export function async function saveKb(this: AppComponent, ){await this.run(async()=>{await this.api.saveKnowledgeBase(this.draft);this.knowledgeBases.set(await this.api.knowledgeBases());this.closeModal();});}

export function async function deleteKb(this: AppComponent, x:KnowledgeBase){if(confirm(`Eliminar knowledge base ${x.name}?`))await this.run(async()=>{await this.api.deleteKnowledgeBase(x.id);this.knowledgeBases.set(await this.api.knowledgeBases());if(this.selectedKb()?.id===x.id)this.selectedKb.set(null);});}

export function async function selectKb(this: AppComponent, x:KnowledgeBase){this.selectedKb.set(x);this.documents.set(await this.api.documents(x.id));this.retrievalHits.set([]);}

export function async function uploadFile(this: AppComponent, event:Event){const file=(event.target as HTMLInputElement).files?.[0],kb=this.selectedKb();if(!file||!kb)return;await this.run(async()=>{await this.api.upload(kb.id,file);this.documents.set(await this.api.documents(kb.id));});}

export function addGoogle(this: AppComponent, ){this.draft={sourceType:'GOOGLE_DOCS',sourceId:'',name:'',sourceUri:'',metadata:{}};this.modal.set('google-doc');}

export function async function saveGoogle(this: AppComponent, ){const kb=this.selectedKb();if(!kb)return;await this.run(async()=>{await this.api.addGoogleDocument(kb.id,this.draft);this.documents.set(await this.api.documents(kb.id));this.closeModal();});}

export function async function reindex(this: AppComponent, d:KnowledgeDocument){await this.run(async()=>{await this.api.reindexDocument(d.id);if(this.selectedKb())this.documents.set(await this.api.documents(this.selectedKb()!.id));});}

export function async function deleteDocument(this: AppComponent, d:KnowledgeDocument){if(confirm(`Eliminar documento ${d.name}?`))await this.run(async()=>{await this.api.deleteDocument(d.id);if(this.selectedKb())this.documents.set(await this.api.documents(this.selectedKb()!.id));});}

export function async function retrieve(this: AppComponent, ){const kb=this.selectedKb();if(!kb||!this.retrievalQuery)return;await this.run(async()=>this.retrievalHits.set(await this.api.retrieve(this.retrievalQuery,[kb.name],this.retrievalTopK)));}
