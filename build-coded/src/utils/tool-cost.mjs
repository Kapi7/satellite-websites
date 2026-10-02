// Pure arithmetic only; callers supply prices in the same currency.
export function compareToolCosts(values) {
  if (values.length !== 5 || values.some(v => !Number.isFinite(v) || v < 0 || v > 1e7)) return null;
  const cents = values.map(v => Math.round(v * 100));
  const bare = cents[0] + cents[1] + cents[2];
  const kit = cents[3] + cents[4];
  return { bare: bare / 100, kit: kit / 100, difference: Math.abs(bare - kit) / 100, lower: bare === kit ? 'equal' : bare < kit ? 'bare' : 'kit' };
}
