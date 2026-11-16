import {api} from './client.js';
export const datasets={list:()=>api('/datasets'),get:id=>api('/datasets/'+id),create:data=>api('/datasets',{method:'POST',body:JSON.stringify(data)})};
export const jobs={list:()=>api('/jobs'),get:id=>api('/jobs/'+id),create:data=>api('/jobs',{method:'POST',body:JSON.stringify(data)}),approve:id=>api('/jobs/'+id+'/approve',{method:'POST'})};
export const reports={list:()=>api('/reports'),create:data=>api('/reports',{method:'POST',body:JSON.stringify(data)}),toggle:id=>api('/reports/'+id+'/toggle',{method:'POST'}),deliveries:()=>api('/deliveries')};
export const releases={
 list:()=>api('/releases'),
 get:id=>api('/releases/'+id),
 create:data=>api('/releases',{method:'POST',body:JSON.stringify(data)}),
 verify:id=>api('/releases/'+id+'/verify',{method:'POST'}),
 publish:id=>api('/releases/'+id+'/publish',{method:'POST'}),
 rollback:id=>api('/releases/'+id+'/rollback',{method:'POST'}),
 versions:()=>api('/releases/versions'),
 retire:version=>api('/releases/versions/retire',{method:'POST',body:JSON.stringify({version})})
};
