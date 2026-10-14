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

export function processStatusLabel(this: AppComponent, status:string,type?:ProcessStepType){
    if(status!=='WAITING')return status;
    if(type==='HUMAN')return 'WAITING REVIEW';
    if(type==='WAIT_EVENT')return 'WAITING EVENT';
    return 'IN PROCESS';
  }

export function processDefinitionName(this: AppComponent, instance?:ProcessInstance|null){
    if(!instance)return '';
    const definition=this.processDefinitions().find(d=>d.id===instance.definitionId)
      ||this.processDefinitions().find(d=>d.definitionKey===instance.definitionKey&&d.version===instance.definitionVersion);
    return definition?.name||instance.definitionKey;
  }

export function processStepName(this: AppComponent, instance:ProcessInstance|null|undefined,stepKey:string){
    if(!instance)return stepKey;
    const definition=this.processDefinitions().find(d=>d.id===instance.definitionId)
      ||this.processDefinitions().find(d=>d.definitionKey===instance.definitionKey&&d.version===instance.definitionVersion);
    return definition?.steps.find(s=>s.stepKey===stepKey)?.name||stepKey;
  }

export function humanTaskProcessName(this: AppComponent, task:ProcessHumanTask){
    const instance=this.processInstances().find(x=>x.id===task.processInstanceId);
    return instance?this.processDefinitionName(instance):task.processInstanceId;
  }

export function humanTaskStepName(this: AppComponent, task:ProcessHumanTask){
    const instance=this.processInstances().find(x=>x.id===task.processInstanceId);
    return this.processStepName(instance,task.stepKey);
  }

export function agentDisplayName(this: AppComponent, ref?:string|null){
    if(!ref)return '';
    const agent=this.agents().find(a=>a.id===ref||a.name===ref);
    return agent?.name||this.humanizeIdentifier(ref);
  }

export function stepDisplayName(this: AppComponent, step:any){
    if(step?.description?.trim())return step.description;
    return this.humanizeIdentifier(step?.id||'Step');
  }

export function humanizeIdentifier(this: AppComponent, value?:string|null){
    return String(value||'').replace(/[-_]+/g,' ').replace(/\b\w/g,c=>c.toUpperCase());
  }

export function processStepLabel(this: AppComponent, type:ProcessStepType){
    return ({SERVICE:'Service',AGENTIC_EXECUTION:'Agentic execution',DECISION:'Decision',HUMAN:'Human task',WAIT_EVENT:'Wait event',SUBPROCESS:'Subprocess'} as any)[type]||type;
  }

export function processStepIcon(this: AppComponent, type:ProcessStepType){
    return ({SERVICE:'↗',AGENTIC_EXECUTION:'◎',DECISION:'◇',HUMAN:'♙',WAIT_EVENT:'◷',SUBPROCESS:'▣'} as any)[type]||'•';
  }

export function defaultProcessStepConfiguration(this: AppComponent, type:ProcessStepType){
    if(type==='SERVICE'){
      const svc=this.processServices().filter(s=>s.status==='ACTIVE').sort((a,b)=>b.version-a.version)[0];
      return {serviceKey:svc?.serviceKey||'',serviceVersion:svc?.version||null};
    }
    if(type==='AGENTIC_EXECUTION')return {intent:'',instructions:[],metadata:{}};
    if(type==='DECISION')return {path:'processInput.value',operator:'EQ',value:true,onTrue:'TRUE',onFalse:'FALSE'};
    if(type==='HUMAN')return {title:'Human approval',description:''};
    if(type==='WAIT_EVENT')return {eventType:'event.received'};
    return {};
  }

export function selectReviewProducer(this: AppComponent, step:any,key:string){
    const previous=step.reviewRepeatStep;
    const deps=new Set<string>(step.dependsOn||[]);
    if(previous)deps.delete(previous);
    if(key)deps.add(key);
    step.reviewRepeatStep=key;
    step.dependsOn=[...deps];
    this.processStepDraft.set({...step});
  }

export function reviewableProducerSteps(this: AppComponent, currentStepKey:string){
    return (this.processDesigner()?.steps||[]).filter((s:any)=>
      s.stepKey!==currentStepKey
      && (s.type==='SERVICE'||s.type==='AGENTIC_EXECUTION'));
  }

export function taskArtifactRefs(this: AppComponent, task:ProcessHumanTask){
    const refs:any[]=[];
    const visit=(value:any)=>{
      if(Array.isArray(value)){value.forEach(visit);return;}
      if(value&&typeof value==='object'){
        if(value.artifactId&&value.type)refs.push(value);
        Object.values(value).forEach(visit);
      }
    };
    visit(task.payload);
    return refs.filter((x,index,arr)=>arr.findIndex(y=>y.artifactId===x.artifactId)===index);
  }

export function taskReviewArtifacts(this: AppComponent, task:ProcessHumanTask){
    return this.taskArtifactRefs(task).filter((a:any)=>
      a.type==='HUMAN_DOCUMENT'||a.type==='FINAL_DELIVERABLE'
    );
  }

export function humanTaskProducerStep(this: AppComponent, task:ProcessHumanTask){
    const review=this.humanTaskReviewPolicy(task);
    return review?.repeatStep||Object.keys(task.payload?.dependencies||{})[0]||'';
  }

export function humanTaskProducerResult(this: AppComponent, task:ProcessHumanTask){
    const key=this.humanTaskProducerStep(task);
    return key?task.payload?.dependencies?.[key]:null;
  }

export function humanTaskProducerName(this: AppComponent, task:ProcessHumanTask){
    const instance=this.processInstances().find(x=>x.id===task.processInstanceId);
    return this.processStepName(instance,this.humanTaskProducerStep(task));
  }

export function humanTaskLegacyReviewText(this: AppComponent, task:ProcessHumanTask){
    if(this.taskReviewArtifacts(task).length)return '';
    const result:any=this.humanTaskProducerResult(task);
    if(!result)return '';
    const candidates=[
      result?.data?.finalStep?.output?.content,
      result?.data?.finalStep?.summary,
      result?.output?.content,
      result?.summary,
      result?.content
    ];
    return String(candidates.find(x=>typeof x==='string'&&x.trim())||'');
  }

export function textDisplayBlocks(this: AppComponent, rawValue:string){
    const raw=String(rawValue||'');
    const blocks:any[]=[];
    let paragraph:string[]=[];
    const flush=()=>{if(paragraph.length){blocks.push({kind:'p',text:paragraph.join(' ')});paragraph=[];}};
    for(const sourceLine of raw.split('\n')){
      const line=sourceLine.trim();
      if(!line){flush();continue;}
      const heading=line.match(/^(#{1,3})\s+(.+)$/);
      if(heading){flush();blocks.push({kind:'h'+heading[1].length,text:heading[2]});continue;}
      const bullet=line.match(/^[-*]\s+(.+)$/);
      if(bullet){flush();blocks.push({kind:'li',text:bullet[1]});continue;}
      paragraph.push(line);
    }
    flush();
    return blocks;
  }

export function unwrapStructuredText(this: AppComponent, rawValue:string){
    const raw=String(rawValue||'').trim();
    return raw.replace(/^\s*```(?:json|markdown|md)?\s*/i,'').replace(/\s*```\s*$/,'').trim();
  }

export function extractJsonStringField(this: AppComponent, rawValue:string,field:string){
    const raw=this.unwrapStructuredText(rawValue);
    const token=`"${field}"`;
    const keyIndex=raw.indexOf(token);
    if(keyIndex<0)return '';
    const colon=raw.indexOf(':',keyIndex+token.length);
    if(colon<0)return '';
    const quote=raw.indexOf('"',colon+1);
    if(quote<0)return '';
    let escaped=false;
    for(let i=quote+1;i<raw.length;i++){
      const ch=raw[i];
      if(ch==='"'&&!escaped){
        const literal=raw.slice(quote,i+1);
        try{return JSON.parse(literal);}catch{return raw.slice(quote+1,i);}
      }
      escaped=ch==='\\'&&!escaped;
      if(ch!=='\\')escaped=false;
    }
    return '';
  }

export function markdownFrom(this: AppComponent, value:any,depth=0):string{
    if(value==null||depth>7)return '';
    if(typeof value==='object'){
      const human=value.humanDocument||value.human_document;
      if(typeof human?.markdown==='string'&&human.markdown.trim())return human.markdown.trim();
      if(typeof value.markdown==='string'&&value.markdown.trim()){
        const nested=this.markdownFrom(value.markdown,depth+1);
        if(nested)return nested;
      }
      for(const key of ['content','data','output','result','document']){
        if(value[key]!=null){
          const nested=this.markdownFrom(value[key],depth+1);
          if(nested)return nested;
        }
      }
      return '';
    }
    if(typeof value!=='string')return '';
    const raw=this.unwrapStructuredText(value);
    if((raw.startsWith('{')&&raw.endsWith('}'))||(raw.startsWith('[')&&raw.endsWith(']'))){
      try{
        const parsed=JSON.parse(raw);
        const nested=this.markdownFrom(parsed,depth+1);
        if(nested)return nested;
      }catch{
        const markdown=this.extractJsonStringField(raw,'markdown');
        if(markdown)return markdown;
      }
    }
    const embeddedMarkdown=this.extractJsonStringField(raw,'markdown');
    if(embeddedMarkdown)return embeddedMarkdown;
    return raw;
  }

export function summaryFrom(this: AppComponent, value:any,depth=0):string{
    if(value==null||depth>6)return '';
    if(typeof value==='object'){
      if(typeof value.summary==='string'&&value.summary.trim())return this.summaryFrom(value.summary,depth+1);
      for(const key of ['content','data','output','result']){
        if(value[key]!=null){
          const nested=this.summaryFrom(value[key],depth+1);
          if(nested)return nested;
        }
      }
      return '';
    }
    if(typeof value!=='string')return '';
    const raw=this.unwrapStructuredText(value);
    if(raw.startsWith('{')||raw.startsWith('[')){
      try{
        const parsed=JSON.parse(raw);
        const nested=this.summaryFrom(parsed,depth+1);
        if(nested)return nested;
      }catch{
        const summary=this.extractJsonStringField(raw,'summary');
        if(summary)return summary;
      }
    }
    const embedded=this.extractJsonStringField(raw,'summary');
    return embedded||raw;
  }

export function artifactMarkdown(this: AppComponent, a:ExecutionArtifact){
    return this.markdownFrom(a.content);
  }

export function artifactSummary(this: AppComponent, a:any){
    const parsed=this.summaryFrom(a?.summary);
    if(parsed&&parsed!==a?.summary)return parsed;
    const fromContent=this.summaryFrom(a?.content);
    return fromContent||parsed||'';
  }

export function artifactDisplayBlocks(this: AppComponent, a:ExecutionArtifact){
    return this.textDisplayBlocks(this.artifactMarkdown(a));
  }

export function toggleHumanTaskTechnical(this: AppComponent, task:ProcessHumanTask){
    this.humanTaskTechnicalOpen[task.id]=!this.humanTaskTechnicalOpen[task.id];
  }

export function isHumanTaskTechnicalOpen(this: AppComponent, task:ProcessHumanTask){
    return !!this.humanTaskTechnicalOpen[task.id];
  }

export function trackByHumanTaskId(this: AppComponent, _index:number,task:ProcessHumanTask){
    return task.id;
  }

export async function openArtifact(this: AppComponent, ref:any){
    await this.run(async()=>{
      this.selectedArtifact.set(await this.api.artifact(ref.artifactId||ref.id));
      this.modal.set('artifact');
    });
  }

export function humanTaskReviewPolicy(this: AppComponent, task:ProcessHumanTask){
    const instance=this.processInstances().find(x=>x.id===task.processInstanceId);
    const definition=this.processDefinitions().find(d=>d.id===instance?.definitionId);
    return definition?.steps.find(s=>s.stepKey===task.stepKey)?.configuration?.review||null;
  }

export function pendingProcessHumanTasks(this: AppComponent){return this.processHumanTasks().filter(x=>x.status==='PENDING').length;}

export function activeProcessServices(this: AppComponent){return this.processServices().filter(x=>x.status==='ACTIVE').length;}

export function processProgress(this: AppComponent, x:ProcessInstance){return x.steps.filter(s=>s.status==='COMPLETED'||s.status==='SKIPPED').length;}

export function processCompletedSteps(this: AppComponent, x:ProcessInstance){return x.steps.filter(s=>s.status==='COMPLETED').length;}

export function processWaitingSteps(this: AppComponent, x:ProcessInstance){return x.steps.filter(s=>s.status==='WAITING').length;}

export function processServiceSelection(this: AppComponent, step:any){
    const key=step.configuration?.serviceKey,version=step.configuration?.serviceVersion;
    return key&&version?`${key}::${version}`:'';
  }

export function selectProcessService(this: AppComponent, step:any,value:string){
    const [key,version]=String(value||'').split('::');
    step.configuration.serviceKey=key||'';
    step.configuration.serviceVersion=version?Number(version):null;
  }

export function activeProcessServiceVersions(this: AppComponent){
    return this.processServices()
      .filter(s=>s.status==='ACTIVE')
      .sort((a,b)=>a.serviceKey.localeCompare(b.serviceKey)||b.version-a.version);
  }

export function processServiceName(this: AppComponent, step:any){
    if(step.type!=='SERVICE')return '';
    const key=step.configuration?.serviceKey,version=step.configuration?.serviceVersion;
    const svc=this.processServices().find(s=>s.serviceKey===key&&(!version||s.version===version));
    return svc?`${svc.name} · v${svc.version}`:key||'No service selected';
  }

export function selectedProcessDefinitionForInstance(this: AppComponent){
    const x=this.selectedProcessInstance();
    return x?this.processDefinitions().find(d=>d.id===x.definitionId)||null:null;
  }
