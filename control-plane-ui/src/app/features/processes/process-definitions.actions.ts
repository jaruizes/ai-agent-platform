import type { AppComponent, ProcessTab } from '../../app.component';
import type { Agent, BudgetDecision, ContextSnapshot, EvalDataset, EvalDefinition, EvalRun, ExecutionArtifact, ExecutionDetail, ExecutionSummary, GovernanceBudget, GovernanceDecision, GovernancePolicy, KnowledgeBase, KnowledgeDocument, McpServer, MemoryInfo, Orchestration, Overview, PendingApproval, ProcessDefinition, ProcessHumanTask, ProcessInstance, ProcessServiceDefinition, ProcessStepDefinition, ProcessStepType, Prompt, RetrievalHit, RuntimeInfo, SessionInfo, Skill, Tool } from '../../models';

/** process-definitions behavior; application state remains in the host during migration. */
export async function loadProcesses(this: AppComponent){
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

export async function refreshProcessesLive(this: AppComponent){
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

export function setProcessTab(this: AppComponent, tab:ProcessTab){this.processTab.set(tab);}

export function filteredProcessDefinitions(this: AppComponent){
    const q=this.processDefinitionSearch.toLowerCase();
    return this.processDefinitions().filter(x=>!q||[x.definitionKey,x.name,x.description].some(v=>(v||'').toLowerCase().includes(q)));
  }

export function filteredProcessInstances(this: AppComponent){
    const q=this.processInstanceSearch.toLowerCase();
    return this.processInstances().filter(x=>!q||[x.id,x.definitionKey,x.correlationId,x.status].some(v=>(v||'').toLowerCase().includes(q)));
  }

export function processDefinitionLevels(this: AppComponent, definition?:ProcessDefinition|null){
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

export function processInstanceLevels(this: AppComponent, instance?:ProcessInstance|null){
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

export function openCreateProcessDefinition(this: AppComponent){
    this.processDesigner.set({
      id:null,definitionKey:'',name:'',description:'',version:1,status:'DRAFT',
      inputSchema:'{"type":"object"}',outputSchema:'{"type":"object"}',steps:[]
    });
    this.selectedProcessDefinition.set(null);
    this.modal.set('process-designer');
  }

export function editProcessDefinition(this: AppComponent, x:ProcessDefinition){
    this.selectedProcessDefinition.set(x);
    this.processDesigner.set({
      ...x,
      inputSchema:this.json(x.inputSchema),
      outputSchema:this.json(x.outputSchema),
      steps:x.steps.map(s=>({...s,inputSchema:this.json(s.inputSchema),outputSchema:this.json(s.outputSchema),configuration:{...(s.configuration||{})}}))
    });
    this.modal.set('process-designer');
  }

export function addProcessStep(this: AppComponent, type:ProcessStepType){
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
    this.editProcessStep(step);
  }

export function editProcessStep(this: AppComponent, step:any){
    this.processStepDraft.set({
      ...step,
      originalStepKey:step.stepKey,
      dependsOn:[...(step.dependsOn||[])],
      configuration:{...(step.configuration||{})},
      inputSchema:typeof step.inputSchema==='string'?step.inputSchema:this.json(step.inputSchema),
      outputSchema:typeof step.outputSchema==='string'?step.outputSchema:this.json(step.outputSchema),
      instructions:Array.isArray(step.configuration?.instructions)?step.configuration.instructions.join('\n'):'',
      metadata:this.json(step.configuration?.metadata||{}),
      decisionValue:this.json(step.configuration?.value),
      whenDecisionStep:step.configuration?.when?.decisionStep||'',
      whenEquals:step.configuration?.when?.equals??'',
      retryMaxAttempts:step.configuration?.retry?.maxAttempts||1,
      retryBackoffMs:step.configuration?.retry?.backoffMs||0,
      timeoutSeconds:step.configuration?.timeoutSeconds||null,
      reviewEnabled:!!step.configuration?.review,
      reviewRepeatStep:step.configuration?.review?.repeatStep||'',
      reviewApproveDecision:step.configuration?.review?.approveDecision||'APPROVE',
      reviewRepeatDecision:step.configuration?.review?.repeatDecision||'REQUEST_CHANGES',
      reviewMaxIterations:step.configuration?.review?.maxIterations||5,
      artifactEnabled:!!step.configuration?.artifactPolicy?.enabled,
      artifactSchema:step.configuration?.artifactPolicy?.schema||'generic-agent-output/v1',
      artifactHumanTitle:step.configuration?.artifactPolicy?.humanTitle||step.name||step.stepKey,
      artifactHumanType:step.configuration?.artifactPolicy?.humanArtifactType||'HUMAN_DOCUMENT',
      artifactAgentNames:(step.configuration?.artifactPolicy?.agentNames||[]).join(', '),
      artifactMaxOutputTokens:step.configuration?.artifactPolicy?.maxOutputTokens||8000,
      materializationEnabled:!!step.configuration?.materializationPolicy?.enabled,
      materializationAllowedTools:(step.configuration?.materializationPolicy?.allowedTools||[]).join(', ')
    });
    this.modal.set('process-step');
  }

export function saveProcessStep(this: AppComponent){
    try{
      const d=this.processDesigner(),s=this.processStepDraft();if(!d||!s)return;
      const config:any={...(s.configuration||{})};
      delete config.when;delete config.retry;delete config.timeoutSeconds;
      if(s.type==='AGENTIC_EXECUTION'){
        config.intent=s.configuration?.intent||'';
        config.instructions=(s.instructions||'').split('\n').map((x:string)=>x.trim()).filter(Boolean);
        config.metadata=JSON.parse(s.metadata||'{}');
        delete config.artifactPolicy;
        delete config.materializationPolicy;
        if(s.artifactEnabled){
          config.artifactPolicy={
            enabled:true,
            schema:s.artifactSchema||'generic-agent-output/v1',
            humanTitle:s.artifactHumanTitle||s.name||s.stepKey,
            humanArtifactType:s.artifactHumanType||'HUMAN_DOCUMENT',
            agentNames:String(s.artifactAgentNames||'').split(',').map((x:string)=>x.trim()).filter(Boolean),
            maxOutputTokens:Number(s.artifactMaxOutputTokens||8000)
          };
        }
        if(s.materializationEnabled){
          config.materializationPolicy={
            enabled:true,
            allowedTools:String(s.materializationAllowedTools||'').split(',').map((x:string)=>x.trim()).filter(Boolean)
          };
        }
      }
      if(s.type==='DECISION'){
        config.value=s.decisionValue===''||s.decisionValue==null?null:JSON.parse(s.decisionValue);
      }
      if(s.type==='HUMAN'){
        delete config.review;
        if(s.reviewEnabled){
          config.review={
            repeatStep:s.reviewRepeatStep,
            approveDecision:s.reviewApproveDecision||'APPROVE',
            repeatDecision:s.reviewRepeatDecision||'REQUEST_CHANGES',
            maxIterations:Number(s.reviewMaxIterations||5)
          };
        }
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
      let steps=[...(d.steps||[])];
      const original=s.originalStepKey||s.stepKey;
      const existingIndex=steps.findIndex((x:any)=>(x.id&&s.id&&x.id===s.id)||x.stepKey===original);
      if(existingIndex>=0)steps[existingIndex]=normalized;else steps.push(normalized);
      if(original!==s.stepKey){
        steps=steps.map((x:any)=>{
          if(x.stepKey===s.stepKey)return x;
          const configuration={...(x.configuration||{})};
          if(configuration.when?.decisionStep===original){
            configuration.when={...configuration.when,decisionStep:s.stepKey};
          }
          return {...x,dependsOn:(x.dependsOn||[]).map((k:string)=>k===original?s.stepKey:k),configuration};
        });
      }
      d.steps=steps;
      this.processDesigner.set({...d});
      this.processStepDraft.set(null);
      this.modal.set('process-designer');
    }catch(e:any){
      this.error.set(this.message(e));
    }
  }

export function removeProcessStep(this: AppComponent, step:any){
    const d=this.processDesigner();if(!d||d.status!=='DRAFT')return;
    if(!confirm(`Remove step ${step.stepKey}?`))return;
    d.steps=(d.steps||[]).filter((x:any)=>x.stepKey!==step.stepKey)
      .map((x:any)=>({...x,dependsOn:(x.dependsOn||[]).filter((k:string)=>k!==step.stepKey)}));
    this.processDesigner.set({...d});
  }

export function toggleProcessDependency(this: AppComponent, key:string,checked:boolean){
    const s=this.processStepDraft();if(!s)return;
    const deps=new Set<string>(s.dependsOn||[]);
    checked?deps.add(key):deps.delete(key);
    s.dependsOn=[...deps];
    this.processStepDraft.set({...s});
  }

export async function saveProcessDefinition(this: AppComponent){
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

export async function activateProcessDefinition(this: AppComponent, x:ProcessDefinition){
    if(!confirm(`Activate ${x.definitionKey} v${x.version}? The version becomes immutable.`))return;
    await this.run(async()=>{const saved=await this.api.activateProcessDefinition(x.id);this.processDefinitions.set(await this.api.processDefinitions());this.selectedProcessDefinition.set(saved);});
  }

export async function retireProcessDefinition(this: AppComponent, x:ProcessDefinition){await this.run(async()=>{await this.api.retireProcessDefinition(x.id);this.processDefinitions.set(await this.api.processDefinitions());});}

export async function nextProcessDefinitionVersion(this: AppComponent, x:ProcessDefinition){await this.run(async()=>{const v=await this.api.nextProcessDefinitionVersion(x.id);this.processDefinitions.set(await this.api.processDefinitions());this.editProcessDefinition(v);});}
