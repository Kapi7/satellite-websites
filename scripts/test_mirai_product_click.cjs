const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const handlers = {}, calls = [];
const document = {
  readyState:'loading', title:'Guide', body:{},
  querySelector:()=>null, getElementById:()=>null,
  addEventListener:(name,fn)=>(handlers[name] ||= []).push(fn)
};
vm.runInNewContext(fs.readFileSync('cosmetics/public/js/tracking.js','utf8'), {
 URL, document, location:{hostname:'glow-coded.com',pathname:'/shop/'},
 window:{addEventListener:()=>{}}, setInterval:()=>{},setTimeout:()=>{},clearTimeout:()=>{},
 gtag:(...args)=>calls.push(args)
});
function click(href) {
 calls.length=0;
 const link={href,textContent:'Check at Mirai',tagName:'A',parentElement:null,getAttribute:()=> 'buying-hub'};
 const target={closest:selector=>selector==='a[href]'?link:null};
 for (const fn of handlers.click) fn({target});
 return calls.filter(c=>c[1]==='mirai_product_click');
}
let events=click('https://mirai-skin.com/products/test?variant=123&email=private@example.com');
assert.equal(events.length,1);
assert.equal(events[0][2].link_url,'https://mirai-skin.com/products/test');
assert.equal(events[0][2].placement,'buying-hub');
assert.equal(events[0][2].source_page,'/shop/');
assert(calls.some(c=>c[1]==='product_click'),'Legacy series preserved');
for(const href of ['https://mirai-skin.com/','https://mirai-skin.com/collections/all','https://mirai-skin.com.evil.example/products/test','http://mirai-skin.com/products/test']) assert.equal(click(href).length,0,href);
assert.equal(click('https://www.mirai-skin.com/products/test/').length,1);
console.log('Product intent proxy: exact HTTPS hosts/product paths, no destination query data, placement and legacy continuity verified.');
