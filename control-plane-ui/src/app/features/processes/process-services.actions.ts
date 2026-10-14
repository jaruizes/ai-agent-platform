import type { AppComponent, ProcessTab } from '../../app.component';
import type { Agent, BudgetDecision, ContextSnapshot, EvalDataset, EvalDefinition, EvalRun, ExecutionArtifact, ExecutionDetail, ExecutionSummary, GovernanceBudget, GovernanceDecision, GovernancePolicy, KnowledgeBase, KnowledgeDocument, McpServer, MemoryInfo, Orchestration, Overview, PendingApproval, ProcessDefinition, ProcessHumanTask, ProcessInstance, ProcessServiceDefinition, ProcessStepDefinition, ProcessStepType, Prompt, RetrievalHit, RuntimeInfo, SessionInfo, Skill, Tool } from '../../models';

/** process-services behavior; application state remains in the host during migration. */
export function openCreateProcessService(this: AppComponent){
    this.draft={serviceKey:'',name:'',description:'',version:1,implementationKey:'http',configuration:'{"url":"http://service:8080/api","method":"POST"}',inputSchema:'{"type":"object"}',outputSchema:'{"type":"object"}'};
    this.modal.set('process-service');
  }

export function editProcessService(this: AppComponent, x:ProcessServiceDefinition){
    this.draft={...x,configuration:this.json(x.configuration),inputSchema:this.json(x.inputSchema),outputSchema:this.json(x.outputSchema)};
    this.modal.set('process-service');
  }

export async function saveProcessService(this: AppComponent){await this.run(async()=>{await this.api.saveProcessService(this.draft);this.processServices.set(await this.api.processServices());this.closeModal();});}

export async function activateProcessService(this: AppComponent, x:ProcessServiceDefinition){await this.run(async()=>{await this.api.activateProcessService(x.id);this.processServices.set(await this.api.processServices());});}

export async function retireProcessService(this: AppComponent, x:ProcessServiceDefinition){await this.run(async()=>{await this.api.retireProcessService(x.id);this.processServices.set(await this.api.processServices());});}

export async function nextProcessServiceVersion(this: AppComponent, x:ProcessServiceDefinition){await this.run(async()=>{const v=await this.api.nextProcessServiceVersion(x.id);this.processServices.set(await this.api.processServices());this.editProcessService(v);});}
