const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
for (const [site, domain] of [['cosmetics', 'glow-coded.com'], ['wellness', 'rooted-glow.com']]) {
const source = fs.readFileSync(site + '/public/js/tracking.js', 'utf8');
const links = [
  {href:'https://mirai-skin.com/products/cleanser?variant=123#details'},
  {href:'https://mirai-skin.com/products/serum?utm_source=partner&ref=existing'},
  {href:'https://mirai-skin.com.evil.example/products/fake'},
  {href:'https://other.example/product'}
];
const events = {};
vm.runInNewContext(source, {URL, document:{readyState:'loading',
  querySelector:()=>({href:'https://glow-coded.com/example-guide/?email=private@example.com'}),
  querySelectorAll:()=>links,
  addEventListener:(name,callback)=>{events[name]=callback;}
}});
assert.equal(new URL(links[0].href).searchParams.has('utm_source'),false);
events.DOMContentLoaded();
const actual = new URL(links[0].href);
assert.equal(actual.searchParams.get('utm_source'),domain);
assert.equal(actual.searchParams.get('utm_medium'),'affiliate');
assert.equal(actual.searchParams.get('utm_campaign'),'mirai_skin');
assert.equal(actual.searchParams.get('utm_content'),'/example-guide/');
assert.equal(actual.searchParams.get('variant'),'123');
assert.equal(actual.hash,'#details');
assert(!actual.href.includes('private'));
assert.equal(new URL(links[1].href).searchParams.get('utm_source'),'partner');
assert.equal(new URL(links[1].href).searchParams.get('ref'),'existing');
assert.equal(links[2].href,'https://mirai-skin.com.evil.example/products/fake');
assert.equal(links[3].href,'https://other.example/product');
const dynamic={href:'https://www.mirai-skin.com/products/new'};
events.click({target:{closest:()=>dynamic}});
assert.equal(new URL(dynamic.href).searchParams.get('utm_source'),domain);
const once=dynamic.href;events.auxclick({target:{closest:()=>dynamic}});assert.equal(dynamic.href,once);
console.log('Mirai attribution: static/dynamic links, existing tags, exact hosts, no Analytics dependency, no query leakage and idempotence passed.');

}
