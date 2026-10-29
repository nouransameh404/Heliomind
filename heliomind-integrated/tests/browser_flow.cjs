/* Real DOM + HTTP flow (jsdom). Not a graphical-browser or Docker test.
   HELIOMIND_TEST_URL must point to a running UI proxy, e.g. http://127.0.0.1:18100.
   Install dev-only dependency: npm install --no-save jsdom@26.1.0
*/
const assert=require('node:assert/strict');
const {JSDOM,ResourceLoader,VirtualConsole}=require('jsdom');
const base=process.env.HELIOMIND_TEST_URL||'http://127.0.0.1:18100';
class LocalResources extends ResourceLoader{fetch(url,options){if(!url.startsWith(base))return null;return super.fetch(url,options)}}
async function run(degraded){
 let blocked=degraded, calls=[];
 const errors=[];
 const dom=await JSDOM.fromURL(base+'/',{
  runScripts:'dangerously',resources:new LocalResources(),pretendToBeVisual:true,
  virtualConsole:new VirtualConsole().on('jsdomError',error=>errors.push(error.message)),
  beforeParse(window){
   window.matchMedia=()=>({matches:false});window.AbortController=global.AbortController;
   window.fetch=async(url,options)=>{
    const absolute=new URL(url,base+'/').href;
    if(absolute.endsWith('/api/anomaly/features')&&blocked){blocked=false;return new Response(JSON.stringify({detail:'Anomaly is starting'}),{status:503,headers:{'content-type':'application/json'}})}
    if(options?.method==='POST')calls.push(absolute);
    return global.fetch(absolute,options);
   };
  }
 });
 try{
  await new Promise((resolve,reject)=>{if(dom.window.document.readyState==='complete')return resolve();dom.window.addEventListener('load',resolve,{once:true});setTimeout(()=>reject(Error('Page load timeout')),15000).unref()});
  const w=dom.window,d=w.document;
  await w.eval('ready');
  assert.equal(calls.length,0,'Opening pages must not run saved readings automatically');
  assert.equal(d.querySelector('#fLat'),null);
  assert.equal(d.querySelectorAll('#fMainFields input').length,6);
  assert.equal(d.querySelectorAll('#fAdvancedFields input').length,5);
  await d.querySelector('#fPredict').onclick({currentTarget:d.querySelector('#fPredict')});
  assert.equal(calls.length,0);assert.match(d.querySelector('#fOut').textContent,/Enter/);
  await d.querySelector('#fSample').onclick();
  assert.equal(d.querySelector('#fSelect').options.length,288);
  assert.equal(calls.length,0,'Example fills fields but does not predict');
  await d.querySelector('#fPredict').onclick({currentTarget:d.querySelector('#fPredict')});
  assert.equal(d.querySelectorAll('#fOut tbody tr').length,1);
  d.querySelector('#fm-temperature').value='35';d.querySelector('#fm-temperature').dispatchEvent(new w.Event('input'));
  await d.querySelector('#fPredict').onclick({currentTarget:d.querySelector('#fPredict')});
  assert.match(d.querySelector('#fOut').textContent,/Manually entered/);
  await d.querySelector('#fRun').onclick({currentTarget:d.querySelector('#fRun')});
  assert.equal(d.querySelectorAll('#fOut tbody tr').length,288);
  assert(d.querySelector('#fOut svg'));
  assert.match(d.querySelector('#fOut tbody').textContent,/2025-01-01/);
  await d.querySelector('#aSample').onclick();
  assert.equal(d.querySelector('#aSelect').options.length,120);
  await d.querySelector('#aPredict').onclick({currentTarget:d.querySelector('#aPredict')});
  assert.equal(Array.from(d.querySelectorAll('#aOut table')).at(-1).querySelectorAll('tbody tr').length,1);
  assert.match(d.querySelector('#aOut').textContent,/Normal reading/);
  const row=w.eval('anomalyFromFields()');
  assert.equal(Object.keys(row).length,18);
  assert(Math.abs(row.power_difference-(row.DC_POWER-row.AC_POWER))<1e-8);
  d.querySelector('#am-IRRADIATION').value='0';
  assert.equal(w.eval('anomalyFromFields().dc_power_per_irradiation'),null);
  await d.querySelector('#aRun').onclick({currentTarget:d.querySelector('#aRun')});
  assert.equal(Array.from(d.querySelectorAll('#aOut table')).at(-1).querySelectorAll('tbody tr').length,120);
  d.querySelector('#sKwh').value='600';d.querySelector('#sArea').value='40';
  await d.querySelector('#sRun').onclick({currentTarget:d.querySelector('#sRun')});
  assert.match(d.querySelector('#sOut').textContent,/AUD/);
  d.querySelector('#fClear').click();d.querySelector('#aClr').click();
  assert.equal(d.querySelector('#fm-ghi').value,'');assert.equal(d.querySelector('#am-DC_POWER').value,'');
  assert.equal(d.querySelector('#fJson').value,'');assert.equal(d.querySelector('#fRun').disabled,true);
  await d.querySelector('#fwExample').onclick();
  const h=JSON.parse(d.querySelector('#fwHistory').value);assert.equal(h.length,48);
  for(const horizon of [24,48]){
   d.querySelector('#fwHorizon').value=String(horizon);
   await d.querySelector('#fwRun').onclick();
   assert.equal(d.querySelectorAll('#fOut tbody tr').length,horizon);
   assert.match(d.querySelector('#fOut').textContent,/future hourly intervals/);
   assert(d.querySelector('#fOut svg'));
  }
  assert.equal(errors.length,0,errors.join('\n'));
  console.log('PASS forms + real HTTP:',degraded?'service retry and all manual/batch flows':'empty validation, explicit examples, edited values, single-row inference, automatic anomaly features, timestamp chart, batches and clear');
 } finally{dom.window.close()}
}
(async()=>{await run(false);await run(true)})().catch(error=>{console.error(error);process.exitCode=1});
