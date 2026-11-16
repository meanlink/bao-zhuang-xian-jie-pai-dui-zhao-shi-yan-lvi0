/** @typedef {{id:number,name:string,source:string,rows:number,checksum:string}} Dataset */
/** @typedef {{id:number,name:string,dataset_id:number,status:string,result:Object,approved:boolean,engine_version:string}} AnalysisJob */
/** @typedef {{id:number,name:string,job_id:number,destination:string,next_run:number,enabled:boolean}} ReportSchedule */
/** @typedef {{version:string,title:string,is_default:boolean,retired:boolean,in_flight:number,method:string,description:string}} EngineVersionRow */
/** @typedef {{id:number,name:string,candidate_version:string,baseline_version:string,status:string,dataset_ids:number[],locked_params:Object[],tolerance:Object,start_default_version:string,expires_at:number,published_at:number,rolled_back_at:number,failure_reason:string,checks_count:Object,checks:Object[]}} Release */
export {};
