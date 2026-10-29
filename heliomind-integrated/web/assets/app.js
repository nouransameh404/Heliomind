const $=q=>document.querySelector(q),$$=q=>[...document.querySelectorAll(q)],fmt=n=>Math.round(n).toLocaleString('en-US');
const toast=t=>{const e=$('#toast');e.textContent=t;e.classList.add('on');clearTimeout(toast.t);toast.t=setTimeout(()=>e.classList.remove('on'),2400)};
const busy=(b,on,t)=>{b.disabled=!!on;b.textContent=on?'Working…':t};

/* ============ BACKEND CONNECTION ============
   Settings live in assets/config.js.
   Deployment requires the model backend.
   MOCK_MODE=false sends real HTTP POST requests to the backend.
*/
async function call(path, payload, local) {
  const cfg = window.SOLARAI_CONFIG || {};
  const base = (cfg.API_BASE_URL || '').replace(/\/$/, '');
  if (!base) throw new Error('Set API_BASE_URL in assets/config.js');
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), cfg.TIMEOUT_MS || 30000);
  try {
    const response = await fetch(base + path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...(cfg.API_KEY ? { 'Authorization': 'Bearer ' + cfg.API_KEY } : {}) },
      body: JSON.stringify(payload),
      signal: controller.signal
    });
    if (!response.ok) {
      let message = 'Server error (' + response.status + ')';
      try { const data = await response.json(); message = data.detail || data.message || message; } catch (_) {}
      throw new Error(typeof message === 'string' ? message : JSON.stringify(message));
    }
    return await response.json();
  } catch (error) {
    throw new Error(error.name === 'AbortError' ? 'Request timed out' : error.message);
  } finally {
    clearTimeout(timer);
  }
}
function showApiError(target, error) {
  console.error('Heliomind API request failed:', error);
  $(target).innerHTML = '<div class="status bad">⚠ ' + escapeHtml(error.message || 'Request failed') + '</div>';
  toast('Backend request failed');
}
function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

/* ============ navigation ============ */
const META={sizing:['Alice Springs — System Planning','Plan a proposed on-grid PV installation with editable resource assumptions and AUD costs.','Resource','User-supplied monthly PSH'],
 forecast:['Alice Springs Forecast','Predict 24–48 future hourly intervals from completed historical readings.','Training data','Alice Springs / DKASC'],
 anomaly:['Anomaly Research Benchmark','Test inverter anomaly detection on the Kaggle research dataset. This model is not trained on DKASC.','Dataset','Kaggle Solar Power Generation']};
function go(p){document.body.dataset.p=p;$$('.nav button').forEach(b=>b.classList.toggle('on',b.dataset.p==p));$$('.page').forEach(s=>s.classList.toggle('on',s.id=='p-'+p));
  const m=META[p];$('#hT').textContent=m[0];$('#hP').textContent=m[1]}
const narrow=()=>matchMedia('(max-width:900px)').matches;
$$('.nav button').forEach(b=>b.onclick=()=>{go(b.dataset.p);document.body.classList.remove('sb-open')});go('sizing');
$('#burger').onclick=()=>document.body.classList.toggle(narrow()?'sb-open':'sb-closed');
$('#scrim').onclick=()=>document.body.classList.remove('sb-open');
addEventListener('keydown',e=>{if(e.key=='Escape')document.body.classList.remove('sb-open')});

const CITY={'Alice Springs':[-23.76,133.87]};
$$('.chips').forEach(c=>Object.entries(CITY).forEach(([k,[a,b]])=>{const x=document.createElement('button');x.textContent=k;x.onclick=()=>{$('#'+c.dataset.p+'Lat').value=a;$('#'+c.dataset.p+'Lon').value=b};c.appendChild(x)}));


const state={forecast:null,anomaly:[],sizing:null}, ids=[];
const number=n=>Number(n).toLocaleString('en-US',{maximumFractionDigits:3});
const raw=r=>`<details><summary>Full response</summary><pre class="raw-result">${escapeHtml(JSON.stringify(r,null,2))}</pre></details>`;
const table=(heads,data)=>`<div style="overflow:auto"><table class="result-table"><thead><tr>${heads.map(h=>`<th>${escapeHtml(h)}</th>`).join('')}</tr></thead><tbody>${data.map(row=>`<tr>${row.map(v=>`<td>${escapeHtml(v)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
async function api(path,payload){return call(path,payload,()=>{throw Error('Backend is required')})}
async function get(path){
 const cfg=window.SOLARAI_CONFIG||{}, base=(cfg.API_BASE_URL||'/api').replace(/\/$/,'');
 const controller=new AbortController(), timer=setTimeout(()=>controller.abort(),10000);
 try{const response=await fetch(base+path,{signal:controller.signal,cache:'no-store'});
 if(!response.ok){let message='Cannot load '+path+' ('+response.status+')';try{const body=await response.json();if(body.detail)message=typeof body.detail==='string'?body.detail:JSON.stringify(body.detail)}catch(_){}throw Error(message)}
 return await response.json()}finally{clearTimeout(timer)}
}
function download(data,name){const a=document.createElement('a'),url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
function finish(target,r,summary){$(target).innerHTML=summary+raw(r);const b=document.createElement('button');b.className='ghost';b.textContent='Download result JSON';b.onclick=()=>download(r,'heliomind-result.json');$(target).append(b)}
function csvParse(text){const lines=[];let row=[],cell='',quoted=false;for(let i=0;i<text.length;i++){const c=text[i];if(c==='"'){if(quoted&&text[i+1]==='"'){cell+='"';i++}else quoted=!quoted}else if(c===','&&!quoted){row.push(cell);cell=''}else if((c==='\n'||c==='\r')&&!quoted){if(c==='\r'&&text[i+1]==='\n')i++;row.push(cell);if(row.some(v=>v.trim()))lines.push(row);row=[];cell=''}else cell+=c}if(quoted)throw Error('Unclosed CSV quote');row.push(cell);if(row.some(v=>v.trim()))lines.push(row);const header=lines.shift()?.map(v=>v.replace(/^\uFEFF/,'').trim());if(!header?.length||new Set(header).size!==header.length)throw Error('Invalid CSV header');return lines.map((values,i)=>{if(values.length!==header.length)throw Error('Invalid CSV row '+(i+2));return Object.fromEntries(header.map((key,j)=>[key,values[j].trim()]))})}
async function records(file){const text=await file.text();if(file.name.toLowerCase().endsWith('.json')){const j=JSON.parse(text);return Array.isArray(j)?j:j.rows}return csvParse(text)}
function featureRows(records, features, nullable) {
 if(!Array.isArray(records)||!records.length||records.length>1000)throw Error('Supply between 1 and 1000 rows');
 if(!features.length)throw Error('Service inputs are not loaded yet. Refresh status and retry.');
 return records.map((row,index)=>{
  if(!row||typeof row!=='object'||Array.isArray(row))throw Error('Row '+(index+1)+' must be an object');
  return Object.fromEntries(features.map(key=>{
   if(!(key in row))throw Error(`Row ${index+1}: missing ${key}`);
   const value=row[key];
   if(value===null||value===''){if(nullable)return[key,null];throw Error(`Row ${index+1}: ${key} is required`);}
   if(typeof value==='boolean'||!['number','string'].includes(typeof value)||!Number.isFinite(Number(value)))throw Error(`Row ${index+1}: ${key} must be numeric`);
   return[key,Number(value)];
  }));
 });
}

let fFeatures=[],aFeatures=[];
let forecastSource='Manual fields', forecastSnapshot='', forecastTimes=[], manualTime='', formSource='Manual fields';
const FIELDS={ghi:['Horizontal irradiance (GHI)','W/m²'],tilted_radiation:['Irradiance on panel plane','W/m²'],temperature:['Ambient temperature','°C'],power_lag_1h:['PV power one hour earlier','kW'],power_lag_24h:['PV power 24 hours earlier','kW'],power_roll_mean_1h:['Prepared rolling mean (1 hour)','kW'],hour:['Hour','0–23'],month:['Month','1–12'],day_of_week:['Weekday','Monday = 0, Sunday = 6'],solar_zenith:['Solar zenith','degrees'],solar_elevation:['Solar elevation','degrees']};
function buildForecastFields(){
 for(const name of ['#fMainFields','#fAdvancedFields'])$(name).innerHTML='';
 for(const key of fFeatures){const label=document.createElement('label');label.textContent=FIELDS[key][0]+' ('+FIELDS[key][1]+')';const input=document.createElement('input');input.id='fm-'+key;input.type='number';input.step='any';input.required=true;input.placeholder='Required';input.oninput=()=>{formSource='Manually entered / edited feature values';manualTime='';$('#fSource').textContent='Input source: '+formSource;$('#fOut').innerHTML='<p>Inputs changed. Click Predict this reading to update the result.</p>';};label.append(input);$(Object.keys(FIELDS).slice(0,6).includes(key)?'#fMainFields':'#fAdvancedFields').append(label);}
}
function clearForecast(){
 state.forecast=null;forecastTimes=[];forecastSnapshot='';manualTime='';formSource='Manual fields';
 $('#fJson').value='';$('#fFile').value='';$('#fCount').textContent='0 rows loaded';$('#fRun').disabled=true;
 $('#fSelect').innerHTML='';$('#fSelectLabel').hidden=true;
 for(const key of fFeatures)$('#fm-'+key).value='';
 $('#fSource').textContent='Input source: manual fields. No values loaded.';$('#fOut').innerHTML='<p>Enter a reading or load historical project data.</p>';
}
function fillReading(index){
 const row=state.forecast?.rows[index];if(!row)return;
 for(const key of fFeatures)$('#fm-'+key).value=row[key];
 manualTime=forecastTimes[index]||'';formSource=forecastSource+' · reading '+(index+1);
 $('#fSource').textContent='Input source: '+formSource;
 $('#fOut').innerHTML='<p>Fields filled from a historical reading. You can edit them, then click Predict this reading.</p>';
}
async function loadForecast(rows,source,times=[]){
 state.forecast={rows:featureRows(rows,fFeatures,false)};forecastSource=source;forecastTimes=times.length===rows.length?times:rows.map(row=>row.timestamp||'');
 forecastSnapshot=JSON.stringify(state.forecast,null,2);$('#fJson').value=forecastSnapshot;
 $('#fCount').textContent=rows.length+' rows loaded';$('#fRun').disabled=false;
 const select=$('#fSelect');select.innerHTML='';state.forecast.rows.forEach((row,index)=>{const option=document.createElement('option');option.value=index;option.textContent=forecastTimes[index]||'Reading '+(index+1);select.append(option)});
 $('#fSelectLabel').hidden=false;const index=state.forecast.rows.findIndex(row=>row.ghi>200);select.value=String(index<0?0:index);fillReading(Number(select.value));
}
function powerChart(values,times){
 if(values.length<2)return '';
 const W=640,H=230,L=60,R=20,T=20,B=45,lo=Math.min(0,...values),hi=Math.max(1,...values),span=hi-lo;
 const x=i=>L+i/(values.length-1)*(W-L-R),y=v=>H-B-(v-lo)/span*(H-T-B);
 let svg=`<svg class="forecast-chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="Predicted PV power across the uploaded readings"><text x="8" y="14">kW</text>`;
 for(let i=0;i<=4;i++){const value=lo+span*i/4;svg+=`<line x1="${L}" x2="${W-R}" y1="${y(value)}" y2="${y(value)}" stroke="#e4eaf0"/><text x="${L-8}" y="${y(value)+4}" text-anchor="end">${number(value)}</text>`}
 svg+=`<polyline fill="none" stroke="#2f6fed" stroke-width="2" points="${values.map((v,i)=>x(i)+','+y(v)).join(' ')}"/>`;
 for(const i of [0,Math.floor((values.length-1)/2),values.length-1])svg+=`<text x="${x(i)}" y="${H-12}" text-anchor="${i===0?'start':i===values.length-1?'end':'middle'}">${escapeHtml(times[i]||'Row '+(i+1))}</text>`;
 return svg+'</svg>';
}
function renderForecast(result,source,times=[]){
 finish('#fOut',result,'<span class="src">Alice Springs / DKASC · XGBoost · power in kW</span><p class="input-note">Input source: '+escapeHtml(source)+'</p><h3>PV power predictions</h3>'+powerChart(result.predictions_kw,times)+table(['Timestamp / reading','Predicted kW'],result.predictions_kw.map((v,i)=>[times[i]||'Reading '+(i+1),number(v)])));
}
$('#fSelect').onchange=event=>fillReading(Number(event.target.value));
$('#fClear').onclick=clearForecast;
$('#fPredict').onclick=async event=>{
 const button=event.currentTarget;busy(button,true);
 try{await ensureService('forecast');const row={};
 for(const key of fFeatures){const value=$('#fm-'+key).value;if(value.trim()===''||!Number.isFinite(Number(value)))throw Error('Enter '+FIELDS[key][0]);row[key]=Number(value)}
 for(const [key,min,max] of [['hour',0,23],['month',1,12],['day_of_week',0,6]])if(!Number.isInteger(row[key])||row[key]<min||row[key]>max)throw Error(FIELDS[key][0]+' must be an integer from '+min+' to '+max);
 const result=await api('/forecast',{rows:[row]});renderForecast(result,formSource,[manualTime]);
 }catch(error){showApiError('#fOut',error)}finally{busy(button,false,'Predict this reading')}
};
$('#fJson').oninput=()=>{$('#fRun').disabled=!$('#fJson').value.trim();};
$('#fFile').onchange=async event=>{const file=event.target.files[0];if(!file)return;try{await ensureService('forecast');await loadForecast(await records(file),'Uploaded file: '+file.name)}catch(error){showApiError('#fOut',error)}};
$('#fRun').onclick=async event=>{
 const button=event.currentTarget;busy(button,true);
 try{await ensureService('forecast');const input=JSON.parse($('#fJson').value||'null');if(!input)throw Error('Load a batch first');const payload={rows:featureRows(Array.isArray(input)?input:input.rows,fFeatures,false)};
 const unchanged=$('#fJson').value===forecastSnapshot;const result=await api('/forecast',payload);renderForecast(result,unchanged?forecastSource:'Edited batch inputs',unchanged?forecastTimes:[]);
 }catch(error){showApiError('#fOut',error)}finally{busy(button,false,'Predict batch')}
};

let anomalySource='Manual fields',anomalyFormSource='Manual fields';
const AINPUTS={DC_POWER:'DC power (training units)',AC_POWER:'AC power (training units)',IRRADIATION:'Irradiation (training units)',AMBIENT_TEMPERATURE:'Ambient temperature (°C)',MODULE_TEMPERATURE:'Module temperature (°C)',DAILY_YIELD:'Daily yield (training units)',TOTAL_YIELD:'Total yield (training units)',hour:'Hour (0–23)',month:'Month (1–12)',previous_dc_power:'Previous DC power (optional)',previous_daily_yield:'Previous daily yield (optional)'};
function buildAnomalyFields(){
 $('#aMainFields').innerHTML='';$('#aSettings').innerHTML='';
 for(const [key,title] of Object.entries(AINPUTS)){
  const label=document.createElement('label');label.textContent=title;const input=document.createElement('input');input.id='am-'+key;input.type='number';input.step='any';input.placeholder=key.startsWith('previous_')?'Blank = imputed':'Required';input.oninput=()=>{anomalyFormSource='Manually entered / edited reading';$('#aSource').textContent='Input source: '+anomalyFormSource;$('#aOut').innerHTML='<p>Inputs changed. Click Analyse this reading to refresh the result.</p>';};label.append(input);$(Object.keys(AINPUTS).slice(0,5).includes(key)?'#aMainFields':'#aSettings').append(label);
 }
}
function updateAnomaly(){$('#aCnt').textContent=state.anomaly.length+' readings loaded'}
function fillAnomaly(index){const row=state.anomaly[index];if(!row)return;for(const key of Object.keys(AINPUTS))$('#am-'+key).value=row[key]??'';$('#aInv').value=ids[index]||'Reading '+(index+1);anomalyFormSource=anomalySource+' · reading '+(index+1);$('#aSource').textContent='Input source: '+anomalyFormSource;$('#aOut').innerHTML='<p>Fields filled from historical data. Edit if needed, then click Analyse this reading.</p>';}
function loadAnomaly(records,source='Uploaded prepared readings'){
 state.anomaly=featureRows(records,aFeatures,true);anomalySource=source;
 ids.splice(0,ids.length,...records.map((row,i)=>row.SOURCE_KEY||row.inverter||row.inv||'Reading '+(i+1)));updateAnomaly();
 const select=$('#aSelect');select.innerHTML='';records.forEach((row,index)=>{const option=document.createElement('option');option.value=index;option.textContent=(index+1)+' · '+ids[index];select.append(option)});$('#aSelectLabel').hidden=false;select.value='0';fillAnomaly(0);
}
function anomalyFromFields(){
 const row={};for(const key of Object.keys(AINPUTS)){const raw=$('#am-'+key).value;if(!raw.trim()){if(key.startsWith('previous_')){row[key]=null;continue}throw Error('Enter '+AINPUTS[key]);}if(!Number.isFinite(Number(raw)))throw Error('Invalid '+AINPUTS[key]);row[key]=Number(raw)}
 if(!Number.isInteger(row.hour)||row.hour<0||row.hour>23)throw Error('Hour must be 0–23');if(!Number.isInteger(row.month)||row.month<1||row.month>12)throw Error('Month must be 1–12');
 row.temperature_difference=row.MODULE_TEMPERATURE-row.AMBIENT_TEMPERATURE;row.power_difference=row.DC_POWER-row.AC_POWER;
 row.zero_dc_power=Number(row.DC_POWER===0);row.zero_irradiation=Number(row.IRRADIATION===0);
 row.dc_power_per_irradiation=row.IRRADIATION===0?null:row.DC_POWER/row.IRRADIATION;
 row.dc_power_change=row.previous_dc_power===null?null:row.DC_POWER-row.previous_dc_power;
 row.daily_yield_change=row.previous_daily_yield===null?null:row.DAILY_YIELD-row.previous_daily_yield;
 return featureRows([row],aFeatures,true)[0];
}
function renderAnomaly(result,source,labels){
 const one=result.predictions.length===1,resultRow=result.predictions[0];
 const why=one&&resultRow.explanation?'<details><summary>Why this result?</summary><p>Positive contributions raise the anomaly score; negative contributions lower it. Values are log-odds, not percentages.</p>'+table(['Feature','Contribution'],resultRow.explanation.slice(0,5).map(x=>[escapeHtml(x.feature),number(x.shap_log_odds)]))+'</details>':'';
 const summary=one?'<div class="reading-result '+(resultRow.is_anomaly?'anomaly':'normal')+'">'+(resultRow.is_anomaly?'Anomaly detected':'Normal reading')+'</div><p>Model anomaly score: '+number(resultRow.anomaly_probability*100)+'%</p>':'';
 finish('#aOut',result,'<span class="src">Kaggle inverter benchmark · XGBoost + fitted imputer</span><p class="input-note">Input source: '+escapeHtml(source)+'</p>'+summary+why+'<p class="input-note">Synthetic fault benchmark; score is not a calibrated real-world failure probability.</p>'+table(['Reading / inverter','Classification','Model score'],result.predictions.map((value,index)=>[labels[index]||index+1,value.is_anomaly?'Anomaly':'Normal',number(value.anomaly_probability*100)+'%'])));
}
$('#aSelect').onchange=event=>fillAnomaly(Number(event.target.value));
$('#aFile').onchange=async event=>{const file=event.target.files[0];if(!file)return;try{await ensureService('anomaly');loadAnomaly(await records(file),'Uploaded file: '+file.name)}catch(error){showApiError('#aOut',error)}};
$('#aClr').onclick=()=>{state.anomaly=[];ids.length=0;updateAnomaly();for(const key of Object.keys(AINPUTS))$('#am-'+key).value='';$('#aInv').value='';$('#aFile').value='';$('#aSelect').innerHTML='';$('#aSelectLabel').hidden=true;$('#aSource').textContent='Input source: manual fields. No readings loaded.';$('#aOut').innerHTML='<p>Enter a reading or load historical data.</p>';};
$('#aPredict').onclick=async event=>{const button=event.currentTarget;busy(button,true);try{await ensureService('anomaly');const row=anomalyFromFields(),result=await api('/anomaly',{rows:[row]});renderAnomaly(result,anomalyFormSource,[$('#aInv').value||'Manual reading'])}catch(error){showApiError('#aOut',error)}finally{busy(button,false,'Analyse this reading')}};
$('#aRun').onclick=async event=>{const button=event.currentTarget;busy(button,true);try{await ensureService('anomaly');if(!state.anomaly.length)throw Error('Upload or load a prepared batch first');const result=await api('/anomaly',{rows:state.anomaly});renderAnomaly(result,anomalySource,ids)}catch(error){showApiError('#aOut',error)}finally{busy(button,false,'Analyse loaded batch')}};

function settings(data){const host=$('#sSettings');host.innerHTML='';for(const [key,v] of Object.entries(data)){if(['monthly_consumption_kwh','usable_roof_m2'].includes(key))continue;const label=document.createElement('label');label.textContent=key.replaceAll('_',' ');let input;if(Array.isArray(v)){input=document.createElement('textarea');input.value=JSON.stringify(v,null,2);input.style.minHeight='85px';input.dataset.type='json'}else{input=document.createElement('input');input.type=typeof v==='number'?'number':typeof v==='boolean'?'checkbox':'text';if(input.type==='checkbox')input.checked=v;else input.value=v;input.step='any'}input.dataset.setting=key;label.append(input);host.append(label)}}
$('#sRun').onclick=async e=>{const b=e.currentTarget;busy(b,true);try{await ensureService('sizing');const payload={...state.sizing,monthly_consumption_kwh:Number($('#sKwh').value),usable_roof_m2:Number($('#sArea').value)};for(const i of $$('[data-setting]'))payload[i.dataset.setting]=i.dataset.type==='json'?JSON.parse(i.value):i.type==='checkbox'?i.checked:i.type==='number'?Number(i.value):i.value;const r=await api('/sizing',payload),budget=Number($('#sBud').value),finance=r.finance;const warnings=r.warnings.map(w=>`<li>${escapeHtml(w)}</li>`).join('');finish('#sOut',r,`<span class="src">Proposed Alice Springs installation · on-grid planning · AUD</span><div class="verdict"><b>${r.panels.selected_count} panels</b> · <b>${number(r.panels.installed_kwp)} kWp</b> · ${number(r.annual_generation_kwh)} kWh/year. No battery included.</div>`+table(['Item','Value'],[['Array area',number(r.panels.selected_area_m2)+' m²'],['Inverter candidate',r.inverter_candidate?.name||'None'],['Estimated cost',finance?number(finance.total_cost_aud)+' AUD':'Unavailable'],['Budget comparison',finance?(finance.total_cost_aud<=budget?'Within entered budget':'Exceeds entered budget'):'Unavailable'],['Status',r.status]])+(finance?table(['Self-use assumption','Net AUD/year','Simple payback'],finance.scenarios.map(s=>[(s.assumed_ratio*100)+'%',number(s.annual_net_savings_aud),s.simple_payback_years===null?'N/A':number(s.simple_payback_years)+' years'])):'')+`<details><summary>Calculation assumptions</summary><ul>${warnings}</ul></details>`)}catch(err){showApiError('#sOut',err)}finally{busy(b,false,'Design my system')}};
const loading={};
async function ensureService(name){
 if(name==='forecast'&&fFeatures.length)return;
 if(name==='anomaly'&&aFeatures.length)return;
 if(name==='sizing'&&state.sizing)return;
 if(loading[name])return loading[name];
 loading[name]=(async()=>{
  if(name==='forecast'){const result=await get('/forecast/features');fFeatures=result.features;buildForecastFields();}
  if(name==='anomaly'){const result=await get('/anomaly/features');aFeatures=result.features;buildAnomalyFields();}
  if(name==='sizing'){const result=await get('/sizing/example');state.sizing=result;settings(result);}
 })();
 try{await loading[name]}finally{delete loading[name]}
}
async function status(){
 try{const result=await get('/services');$('#connection').textContent=Object.entries(result).map(([key,value])=>key+': '+value).join(' · ')+' — ';}
 catch(error){$('#connection').textContent='Gateway unavailable — ';}
 const button=document.createElement('button');button.className='ghost';button.textContent='Refresh status';
 button.onclick=async()=>{await initialize();};$('#connection').append(button);
}
async function initialize(){
 const names=['forecast','anomaly','sizing'];
 await Promise.all(names.map(async name=>{try{await ensureService(name)}catch(error){const target={forecast:'#fOut',anomaly:'#aOut',sizing:'#sOut'}[name];showApiError(target,new Error(name+' is starting or unavailable. Retry the action or refresh status. '+error.message));}}));

 await status();
}
const projectLoading={};
async function loadProjectData(name,force=false){
 if(projectLoading[name])return projectLoading[name];
 if(!force&&((name==='forecast'&&state.forecast)||(name==='anomaly'&&state.anomaly.length)))return;
 projectLoading[name]=(async()=>{
  const target=name==='forecast'?'#fOut':'#aOut';
  try{
   await ensureService(name);
   const response=await fetch(name+'_ready.json',{cache:'no-store'});
   if(!response.ok)throw Error('Project dataset is unavailable. Reload the page or upload your own data.');
   const data=await response.json();
   if(name==='forecast'){
    await loadForecast(data.rows,data.source,data.timestamps||[]);
   }else{
    loadAnomaly(data.rows,data.source);
   }
  }catch(error){showApiError(target,error)}
 })();
 try{await projectLoading[name]}finally{delete projectLoading[name]}
}
$('#fSample').onclick=()=>loadProjectData('forecast',true);
$('#aSample').onclick=()=>loadProjectData('anomaly',true);
const ready=initialize();
