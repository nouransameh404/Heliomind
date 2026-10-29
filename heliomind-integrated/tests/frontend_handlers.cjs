const fs=require('fs'),vm=require('vm'),assert=require('assert');
const root=require('path').resolve(__dirname,'..');
class El{constructor(){this.dataset={};this.style={};this.children=[];this.value='';this.innerHTML='';this.classList={toggle(){},remove(){},add(){}};}append(e){this.children.push(e)}closest(){return this}click(){}}
const els={};const all=[];const el=q=>els[q]||(els[q]=new El());
for(const [id,v] of Object.entries({sKwh:600,sArea:40,sBud:150000,aInv:1,aAct:119.275,aGhi:.0953944536}))el('#'+id).value=v;
let calls=[],errors=[];
const context={document:{querySelector:el,querySelectorAll:q=>q==='[data-setting]'?all.filter(e=>e.dataset.setting):[],createElement:()=>{const e=new El();all.push(e);return e},body:new El()},window:{SOLARAI_CONFIG:{MOCK_MODE:false,API_BASE_URL:'/api'}},console:{log:console.log,error:e=>errors.push(e)},addEventListener(){},matchMedia:()=>({matches:false}),navigator:{},setTimeout:()=>0,clearTimeout(){},AbortController,Blob,URL,fetch:async(url,opt)=>{let data;if(url==='/api/forecast/features'){data={features:Object.keys(JSON.parse(fs.readFileSync(root+'/examples/forecast.json')).rows[0])}}else if(url==='/api/anomaly/features'){data={features:Object.keys(JSON.parse(fs.readFileSync(root+'/examples/anomaly.json')).rows[0])}}else if(url==='/api/sizing/example'){data=JSON.parse(fs.readFileSync(root+'/examples/sizing.json'))}else if(url==='/api/services'){data={forecast:'ok',sizing:'ok',anomaly:'ok'}}else if(opt){calls.push({url,body:JSON.parse(opt.body)});data=JSON.parse(fs.readFileSync(root+'/examples/'+url.split('/').pop()+'_response.json'))}else data=JSON.parse(fs.readFileSync(root+'/examples/'+url));return{ok:true,json:async()=>data}}};
vm.createContext(context);vm.runInContext(fs.readFileSync(root+'/web/assets/app.js','utf8'),context);
(async()=>{await vm.runInContext('ready',context);
await el('#fSample').onclick();await el('#fRun').onclick({currentTarget:el('#fRun')});assert(calls.at(-1).url==='/api/forecast');assert(el('#fOut').innerHTML.includes('218.464'));
await el('#aSample').onclick();await el('#aRun').onclick({currentTarget:el('#aRun')});assert(calls.at(-1).url==='/api/anomaly');assert(el('#aOut').innerHTML.includes('Normal'));
await el('#sRun').onclick({currentTarget:el('#sRun')});assert(calls.at(-1).url==='/api/sizing');assert(calls.at(-1).body.monthly_consumption_kwh===600);assert(el('#sOut').innerHTML.includes('EGP'));
assert(vm.runInContext('csvParse(\'a,b\\n"x,y",2\')[0].a',context)==='x,y');
const before=calls.length;el('#fJson').value='{"rows":[{"ghi":1}]}';await el('#fRun').onclick({currentTarget:el('#fRun')});assert(calls.length===before);assert(el('#fOut').innerHTML.includes('missing'));
console.log('PASS frontend handler simulation: all three examples route and render; full feature requests; CSV quoting; invalid input blocked. Not a real browser test.');})().catch(e=>{console.error(e);process.exit(1)});
