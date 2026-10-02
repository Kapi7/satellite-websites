import accounts from '../data/retailer-accounts.json' with { type: 'json' };
export function amazonLink(raw, account = accounts.amazonUS) {
 const url = new URL(raw);
 if (url.protocol !== 'https:' || !['amazon.com','www.amazon.com'].includes(url.hostname)) throw new Error('Expected Amazon US URL');
 url.searchParams.delete('tag');
 if (account.status === 'verified' && account.websiteVerified === true && /^[a-zA-Z0-9-]+-20$/.test(account.trackingId || '')) url.searchParams.set('tag', account.trackingId);
 return url.href;
}
export const amazonActive = accounts.amazonUS.status === 'verified' && accounts.amazonUS.websiteVerified === true && /^[a-zA-Z0-9-]+-20$/.test(accounts.amazonUS.trackingId || '');
