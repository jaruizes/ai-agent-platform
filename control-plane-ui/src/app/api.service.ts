import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { Agent, ContextSnapshot, ExecutionDetail, ExecutionSummary, KnowledgeBase, KnowledgeDocument, McpServer, MemoryInfo, Orchestration, Overview, PendingApproval, Prompt, RetrievalHit, RuntimeInfo, SessionInfo, Skill, Tool } from './models';

@Injectable({providedIn:'root'})
export class ApiService {
  private readonly base='/api/v1';
  constructor(private http:HttpClient){}

  overview(){return firstValueFrom(this.http.get<Overview>(`${this.base}/admin/overview`));}
  runtime(){return firstValueFrom(this.http.get<RuntimeInfo>(`${this.base}/admin/runtime`));}
  executions(status=''){return firstValueFrom(this.http.get<ExecutionSummary[]>(`${this.base}/admin/executions`,{params:status?{status}:{}}));}
  approvals(){return firstValueFrom(this.http.get<PendingApproval[]>(`${this.base}/admin/approvals`));}
  execution(id:string){return firstValueFrom(this.http.get<ExecutionDetail>(`${this.base}/executions/${id}`));}
  orchestration(id:string){return firstValueFrom(this.http.get<Orchestration>(`${this.base}/executions/${id}/orchestration`));}
  createExecution(body:any){return firstValueFrom(this.http.post<any>(`${this.base}/executions`,body));}
  pause(id:string,reason='Control Plane'){return firstValueFrom(this.http.post(`${this.base}/executions/${id}/pause`,{reason}));}
  resume(id:string){return firstValueFrom(this.http.post(`${this.base}/executions/${id}/resume`,{}));}
  retry(id:string,reason='Control Plane retry'){return firstValueFrom(this.http.post(`${this.base}/executions/${id}/retry`,{reason}));}
  cancel(id:string,reason='Control Plane cancellation'){return firstValueFrom(this.http.post(`${this.base}/executions/${id}/cancel`,{reason}));}
  approval(executionId:string,stepId:string,approved:boolean,actor:string,comment:string){return firstValueFrom(this.http.post(`${this.base}/executions/${executionId}/steps/${stepId}/approval`,{approved,actor,comment}));}
  contextSnapshots(executionId:string){return firstValueFrom(this.http.get<ContextSnapshot[]>(`${this.base}/executions/${executionId}/context-snapshots`));}

  sessions(status=''){return firstValueFrom(this.http.get<SessionInfo[]>(`${this.base}/sessions`,{params:status?{status}:{}}));}
  createSession(body:any){return firstValueFrom(this.http.post<SessionInfo>(`${this.base}/sessions`,body));}
  closeSession(id:string){return firstValueFrom(this.http.post<SessionInfo>(`${this.base}/sessions/${id}/close`,{}));}
  sessionContext(id:string){return firstValueFrom(this.http.get<any[]>(`${this.base}/sessions/${id}/context`));}
  sessionExecutions(id:string){return firstValueFrom(this.http.get<any[]>(`${this.base}/sessions/${id}/executions`));}

  memories(params:any={}){return firstValueFrom(this.http.get<MemoryInfo[]>(`${this.base}/memories`,{params}));}
  createMemory(body:any){return firstValueFrom(this.http.post<any>(`${this.base}/memories`,body));}
  revokeMemory(id:string){return firstValueFrom(this.http.post<MemoryInfo>(`${this.base}/memories/${id}/revoke`,{}));}
  retrieveMemories(query:string,scopes:any[],topK=8){return firstValueFrom(this.http.post<MemoryInfo[]>(`${this.base}/memories/retrieve`,{query,scopes,topK}));}
  memoryPolicy(){return firstValueFrom(this.http.get<any>(`${this.base}/memory-policy`));}
  memoryPolicyAudit(){return firstValueFrom(this.http.get<any[]>(`${this.base}/memory-policy/audit`));}

  agents(){return firstValueFrom(this.http.get<Agent[]>(`${this.base}/agents`));}
  saveAgent(item:any){const body={name:item.name,description:item.description||'',instructions:item.instructions||'',skills:item.skills||[],enabled:item.enabled!==false};return item.id?firstValueFrom(this.http.put<Agent>(`${this.base}/agents/${item.id}`,body)):firstValueFrom(this.http.post<Agent>(`${this.base}/agents`,body));}
  deleteAgent(id:string){return firstValueFrom(this.http.delete(`${this.base}/agents/${id}`));}
  agentKnowledge(id:string){return firstValueFrom(this.http.get<any[]>(`${this.base}/agents/${id}/knowledge-bases`));}
  saveAgentKnowledge(id:string,items:any[]){return firstValueFrom(this.http.put(`${this.base}/agents/${id}/knowledge-bases`,{knowledgeBases:items}));}

  skills(){return firstValueFrom(this.http.get<Skill[]>(`${this.base}/skills`));}
  saveSkill(item:any){const body={name:item.name,description:item.description||'',instructions:item.instructions||'',enabled:item.enabled!==false};return item.id?firstValueFrom(this.http.put<Skill>(`${this.base}/skills/${item.id}`,body)):firstValueFrom(this.http.post<Skill>(`${this.base}/skills`,body));}
  deleteSkill(id:string){return firstValueFrom(this.http.delete(`${this.base}/skills/${id}`));}

  prompts(){return firstValueFrom(this.http.get<Prompt[]>(`${this.base}/prompts`));}
  savePrompt(item:any){const body={name:item.name,description:item.description||'',content:item.content||'',version:Number(item.version||1),enabled:item.enabled!==false};return item.id?firstValueFrom(this.http.put<Prompt>(`${this.base}/prompts/${item.id}`,body)):firstValueFrom(this.http.post<Prompt>(`${this.base}/prompts`,body));}
  deletePrompt(id:string){return firstValueFrom(this.http.delete(`${this.base}/prompts/${id}`));}

  tools(){return firstValueFrom(this.http.get<Tool[]>(`${this.base}/tools`));}
  saveTool(item:any){const body={name:item.name,description:item.description||'',instructions:item.instructions||'',implementationType:item.implementationType||'MCP',configuration:this.json(item.configuration),inputSchema:this.json(item.inputSchema),sideEffect:item.sideEffect||'READ',approvalPolicy:item.approvalPolicy||'NEVER',enabled:item.enabled!==false};return item.id?firstValueFrom(this.http.put<Tool>(`${this.base}/tools/${item.id}`,body)):firstValueFrom(this.http.post<Tool>(`${this.base}/tools`,body));}
  deleteTool(id:string){return firstValueFrom(this.http.delete(`${this.base}/tools/${id}`));}

  mcpServers(){return firstValueFrom(this.http.get<McpServer[]>(`${this.base}/mcp-servers`));}
  saveMcp(item:any){const body={name:item.name,description:item.description||'',command:item.command,args:this.jsonArray(item.args),cwd:item.cwd||null,environment:this.json(item.environment),enabled:item.enabled!==false};return item.id?firstValueFrom(this.http.put<McpServer>(`${this.base}/mcp-servers/${item.id}`,body)):firstValueFrom(this.http.post<McpServer>(`${this.base}/mcp-servers`,body));}
  deleteMcp(id:string){return firstValueFrom(this.http.delete(`${this.base}/mcp-servers/${id}`));}

  knowledgeBases(){return firstValueFrom(this.http.get<KnowledgeBase[]>(`${this.base}/knowledge-bases`));}
  saveKnowledgeBase(item:any){const body={name:item.name,description:item.description||'',scope:item.scope||'TENANT',retentionPolicy:item.retentionPolicy||'PERSISTENT',ttlSeconds:item.ttlSeconds?Number(item.ttlSeconds):null,enabled:item.enabled!==false,chunkingPolicy:item.chunkingPolicy||{strategy:'PARAGRAPH',chunkSize:1600,overlap:200,parentSize:6000,childSize:1600,childOverlap:200},metadata:item.metadata||{}};return item.id?firstValueFrom(this.http.put<KnowledgeBase>(`${this.base}/knowledge-bases/${item.id}`,body)):firstValueFrom(this.http.post<KnowledgeBase>(`${this.base}/knowledge-bases`,body));}
  deleteKnowledgeBase(id:string){return firstValueFrom(this.http.delete(`${this.base}/knowledge-bases/${id}`));}
  documents(kbId:string){return firstValueFrom(this.http.get<KnowledgeDocument[]>(`${this.base}/knowledge-bases/${kbId}/documents`));}
  upload(kbId:string,file:File){const form=new FormData();form.append('file',file);return firstValueFrom(this.http.post<KnowledgeDocument>(`${this.base}/knowledge-bases/${kbId}/documents/upload`,form));}
  addGoogleDocument(kbId:string,body:any){return firstValueFrom(this.http.post<KnowledgeDocument>(`${this.base}/knowledge-bases/${kbId}/documents/google`,body));}
  reindexDocument(id:string){return firstValueFrom(this.http.post(`${this.base}/knowledge-documents/${id}/reindex`,{}));}
  deleteDocument(id:string){return firstValueFrom(this.http.delete(`${this.base}/knowledge-documents/${id}`));}
  retrieve(query:string,kbs:string[],topK=8){return firstValueFrom(this.http.post<RetrievalHit[]>(`${this.base}/knowledge/retrieve`,{query,knowledgeBases:kbs,topK}));}

  private json(v:any){if(typeof v==='string'){try{return JSON.parse(v||'{}')}catch{throw new Error('JSON inválido');}}return v||{};}
  private jsonArray(v:any){if(Array.isArray(v))return v;if(typeof v==='string'){try{return JSON.parse(v||'[]')}catch{return v.split(/\s+/).filter(Boolean);}}return [];}
}
