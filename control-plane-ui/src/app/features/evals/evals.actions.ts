import type { AppComponent } from '../../app.component';
import type { Agent, BudgetDecision, ContextSnapshot, EvalDataset, EvalDefinition, EvalRun, ExecutionArtifact, ExecutionDetail, ExecutionSummary, GovernanceBudget, GovernanceDecision, GovernancePolicy, KnowledgeBase, KnowledgeDocument, McpServer, MemoryInfo, Orchestration, Overview, PendingApproval, ProcessDefinition, ProcessHumanTask, ProcessInstance, ProcessServiceDefinition, ProcessStepDefinition, ProcessStepType, Prompt, RetrievalHit, RuntimeInfo, SessionInfo, Skill, Tool } from '../../models';

/** evals domain operations. */
export async function loadEvals(this: AppComponent){try{const [d,f,r]=await Promise.all([this.api.evalDatasets(),this.api.evalDefinitions(),this.api.evalRuns()]);this.evalDatasets.set(d);this.evalDefinitions.set(f);this.evalRuns.set(r);}catch(e:any){this.error.set(this.message(e));}}

export function editEvalDataset(this: AppComponent, x?:EvalDataset){this.draft=x?{...x,items:this.json(x.items)}:{name:'',description:'',version:1,enabled:true,items:'[{"name":"case-1","command":{"name":"eval-case","intent":"Explain briefly what an API Gateway is.","input":{},"context":{},"instructions":[]},"expectedOutput":"An API Gateway is an entry point for APIs.","assertions":[{"type":"CONTAINS","value":"API"}],"tags":["smoke"]}]'};this.modal.set('eval-dataset');}

export async function saveEvalDataset(this: AppComponent){await this.run(async()=>{const items=typeof this.draft.items==='string'?JSON.parse(this.draft.items):this.draft.items;await this.api.saveEvalDataset({name:this.draft.name,description:this.draft.description||'',version:Number(this.draft.version||1),enabled:this.draft.enabled!==false,items});this.evalDatasets.set(await this.api.evalDatasets());this.closeModal();});}

export async function deleteEvalDataset(this: AppComponent, x:EvalDataset){if(confirm(`Delete dataset ${x.name}?`))await this.run(async()=>{await this.api.deleteEvalDataset(x.id);this.evalDatasets.set(await this.api.evalDatasets());});}

export function editEvalDefinition(this: AppComponent, x?:EvalDefinition){this.draft=x?{...x,metrics:[...(x.metrics||[])],thresholds:this.json(x.thresholds)}:{name:'',description:'',datasetId:this.evalDatasets()[0]?.id||'',metrics:['relevance','instruction_adherence'],thresholds:'{"passRate":0.8,"relevance":0.7}',judgeModelProfile:'router-fast',enabled:true};this.modal.set('eval-definition');}

export function toggleEvalMetric(this: AppComponent, name:string,checked:boolean){const set=new Set<string>(this.draft.metrics||[]);checked?set.add(name):set.delete(name);this.draft.metrics=[...set];}

export async function saveEvalDefinition(this: AppComponent){await this.run(async()=>{await this.api.saveEvalDefinition({name:this.draft.name,description:this.draft.description||'',datasetId:this.draft.datasetId,metrics:this.draft.metrics||[],thresholds:typeof this.draft.thresholds==='string'?JSON.parse(this.draft.thresholds):this.draft.thresholds,judgeModelProfile:this.draft.metrics?.length?this.draft.judgeModelProfile:null,enabled:this.draft.enabled!==false});this.evalDefinitions.set(await this.api.evalDefinitions());this.closeModal();});}

export async function deleteEvalDefinition(this: AppComponent, x:EvalDefinition){if(confirm(`Delete eval ${x.name}?`))await this.run(async()=>{await this.api.deleteEvalDefinition(x.id);this.evalDefinitions.set(await this.api.evalDefinitions());});}

export async function runEval(this: AppComponent, x:EvalDefinition){await this.run(async()=>{const previous=this.evalRuns().find(r=>r.definitionId===x.id&&r.status==='COMPLETED');await this.api.createEvalRun(x.id,previous?.id);this.evalRuns.set(await this.api.evalRuns());});}

export async function inspectEvalRun(this: AppComponent, x:EvalRun){await this.run(async()=>{this.selectedEvalRun.set(await this.api.evalRun(x.id));this.modal.set('eval-run');});}
