"""Read-only Shopify aggregate report; never changes analytics or contacts customers.
Default period is seven completed STORE-timezone days. Latest days may be provisional.
Existing credentials only; output contains no customer identifiers or full customer URLs.
"""
import argparse,json,os
from datetime import datetime,timedelta,date
from pathlib import Path
from zoneinfo import ZoneInfo
import requests

def main():
    p=argparse.ArgumentParser();p.add_argument('--start');p.add_argument('--end');p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    cfg={}
    config=Path('/Users/kapi7/shopify-theme/.env')
    for line in config.read_text().splitlines():
        if '=' in line and not line.lstrip().startswith('#'):
            k,v=line.split('=',1);cfg[k.strip()]=v.strip().strip('\"\'')
    shop=cfg['SHOPIFY_STORE'].removeprefix('https://').rstrip('/')
    if shop!='9dkd2w-g3.myshopify.com':raise RuntimeError('Unexpected shop; refusing to query')
    session=requests.Session();session.headers['X-Shopify-Access-Token']=cfg['SHOPIFY_ACCESS_TOKEN']
    def gql(query,variables=None):
        r=session.post('https://'+shop+'/admin/api/2026-07/graphql.json',json={'query':query,'variables':variables or {}},timeout=50)
        if r.status_code!=200:raise RuntimeError('Shopify reporting unavailable: HTTP '+str(r.status_code))
        body=r.json()
        if body.get('errors'):raise RuntimeError('Shopify denied or could not execute the report')
        return body['data']
    timezone=gql('{shop{ianaTimezone}}')['shop']['ianaTimezone']
    today=datetime.now(ZoneInfo(timezone)).date();end=date.fromisoformat(a.end) if a.end else today-timedelta(days=1);start=date.fromisoformat(a.start) if a.start else end-timedelta(days=6)
    if start>end or (end-start).days>90:raise ValueError('Choose an ordered period of at most 91 days')
    sources=['glow-coded.com','rooted-glow.com','build-coded.com']
    terms=[f"{field} = '{prefix}{source}'" for source in sources for prefix in ['', 'www.'] for field in ['utm_source','referrer_site']]
    q="FROM sessions SHOW sessions, pageviews, bounces, average_session_duration, sessions_with_cart_additions, sessions_that_reached_checkout, sessions_that_completed_checkout WHERE "+' OR '.join(terms)+f' GROUP BY day, utm_source, referrer_site, human_or_bot_session SINCE {start} UNTIL {end} ORDER BY day ASC LIMIT 1000'
    data=gql('query($q:String!){shopifyqlQuery(query:$q){tableData{columns{name dataType} rows}parseErrors}}',{'q':q})['shopifyqlQuery']
    if data.get('parseErrors'):raise RuntimeError('Shopify report rejected: '+str(data['parseErrors']))
    if data.get('tableData') is None:raise RuntimeError('Shopify returned no report table; not zero traffic')
    rows=data['tableData']['rows']
    if len(rows)>=1000:raise RuntimeError('Report may be truncated; narrow the period')
    out={'start':str(start),'end':str(end),'timezone':timezone,'includesPartialToday':end>=today,'status':'available','rows':rows,'limits':['Latest reporting days may be provisional.','Bot/human is Shopify classification, not verified identity or buying intent.','Tagged sessions are not equivalent to Glow click events or incremental customers.','Completed-checkout sessions are not reconciled order/revenue totals.']}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,indent=2));print('Saved aggregate Shopify quality report:',a.output)
if __name__=='__main__':main()
