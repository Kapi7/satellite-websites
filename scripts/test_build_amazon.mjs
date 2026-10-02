import assert from 'node:assert/strict';
import vm from 'node:vm';
import fs from 'node:fs';
import { compareToolCosts } from '../build-coded/src/utils/tool-cost.mjs';
assert.deepEqual(compareToolCosts([100,70,10,160,10]),{bare:180,kit:170,difference:10,lower:'kit'});
assert.equal(compareToolCosts([100,0,0,160,0]).lower,'bare');
assert.equal(compareToolCosts([0.1,0.2,0,0.3,0]).lower,'equal');
for (const invalid of [[NaN,0,0,0,0],[-1,0,0,0,0],[Infinity,0,0,0,0],[1e8,0,0,0,0],[]]) assert.equal(compareToolCosts(invalid),null);
const source=fs.readFileSync('build-coded/public/js/amazon-clicks.js','utf8');
function scenario({host='build-coded.com',gpc=false,dnt='0',disabled=false,gtag=true}={}) {
 const events=[],handlers={};
 const window={'ga-disable-G-MP5LPFNBN5':disabled};
 if(gtag)window.gtag=(...args)=>events.push(args);
 vm.runInNewContext(source,{window,navigator:{globalPrivacyControl:gpc,doNotTrack:dnt},location:{hostname:host,pathname:'/guide/'},URL,document:{addEventListener:(n,fn)=>handlers[n]=fn,querySelector:()=>({href:'https://build-coded.com/guide/'})}});
 const link={href:'https://www.amazon.com/dp/B09YY8RZJ9?tag=buildcoded-20',dataset:{product:'DCD800D2',placement:'package-card'}};
 const fire=(type='click',button=0,isTrusted=true)=>handlers[type]?.({type,button,isTrusted,target:{closest:()=>link}});
 return {events,fire,link};
}
const good=scenario();good.fire();assert.equal(good.events.length,1);assert.equal(good.events[0][1],'amazon_product_click');assert.equal(good.events[0][2].link_url,'https://www.amazon.com/dp/B09YY8RZJ9');good.fire('auxclick',1);assert.equal(good.events.length,2);good.fire('auxclick',2);good.fire('click',0,false);assert.equal(good.events.length,2);
for(const options of [{host:'localhost'},{gpc:true},{dnt:'1'},{disabled:true},{gtag:false}]){const s=scenario(options);s.fire();assert.equal(s.events.length,0);}
const foreign=scenario();foreign.link.href='https://www.amazon.com.br/dp/B09YY8RZJ9';foreign.fire();assert.equal(foreign.events.length,0);
console.log('PASS: complete-cost arithmetic, invalid inputs, production-only clicks, opt-out signals, no synthetic or right-click events, no query-string collection');
