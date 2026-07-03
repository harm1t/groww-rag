/**
 * Next.js API route: /api/ticker
 *
 * Reads scraped fund JSON files directly from the GitHub repository and
 * returns the same {items: [...]} format as the Python /ticker endpoint.
 * This avoids a dependency on the Render backend for ticker data.
 *
 * Cached via Next.js ISR — revalidates at most once per hour.
 */

export const revalidate = 3600;

const REPO = "harm1t/groww-rag";
const BRANCH = "main";
const GH_API = "https://api.github.com";
const GH_RAW = "https://raw.githubusercontent.com";

const TICKER_FUNDS: Record<string, string> = {
  ppfas_flexi_cap:            "PPFAS Flexi Cap",
  ppfas_large_cap:            "PPFAS Large Cap",
  ppfas_elss:                 "PPFAS ELSS",
  ppfas_conservative_hybrid:  "PPFAS Conservative Hybrid",
  ppfas_arbitrage:            "PPFAS Arbitrage",
  ppfas_liquid:               "PPFAS Liquid",
  ppfas_dynamic_aa:           "PPFAS Dynamic AA",
  jbr_flexi_cap:              "JBR Flexi Cap",
  jbr_nifty_50:               "JBR Nifty 50",
  jbr_nifty_midcap_150:       "JBR Nifty Midcap 150",
  jbr_nifty_smallcap_250:     "JBR Nifty Smallcap 250",
  jbr_nifty_next_50:          "JBR Nifty Next 50",
  jbr_large_cap:              "JBR Large Cap",
  jbr_liquid:                 "JBR Liquid",
  jbr_money_market:           "JBR Money Market",
  jbr_overnight:              "JBR Overnight",
  jbr_arbitrage:              "JBR Arbitrage",
  jbr_nifty_gsec_8_13:        "JBR G-Sec 8-13Y",
  jbr_short_duration:         "JBR Short Duration",
  jbr_low_duration:           "JBR Low Duration",
  jbr_sector_rotation:        "JBR Sector Rotation",
};

interface FundMetrics {
  name: string;
  nav:           string | null;
  change:        string | null;
  aum:           string | null;
  expense_ratio: string | null;
  min_sip:       string | null;
}

interface TickerItem {
  label:  string;
  metric: string;
  value:  string;
  change: string | null;
}

function extractMetrics(content: string): Omit<FundMetrics, "name"> {
  const navM    = content.match(/NAV:[^\n]*\n₹([\d,]+\.[\d]+)/);
  const changeM = content.match(/([+-][\d.]+)\n%\n1D/);
  const aumM    = content.match(/Fund size \(AUM\)\n₹([\d,]+\.[\d]+ Cr)/);
  const expM    = content.match(/Expense ratio\n([\d.]+%)/);
  const sipM    = content.match(/Min\. for SIP\n₹([\d,]+)/);
  return {
    nav:           navM    ? `₹${navM[1]}`    : null,
    change:        changeM ? changeM[1]        : null,
    aum:           aumM    ? `₹${aumM[1]}`    : null,
    expense_ratio: expM    ? expM[1]           : null,
    min_sip:       sipM    ? `₹${sipM[1]}`    : null,
  };
}

async function listBatches(headers: Record<string, string>): Promise<string[]> {
  const res = await fetch(
    `${GH_API}/repos/${REPO}/contents/data/scraped`,
    { headers, next: { revalidate: 3600 } }
  );
  if (!res.ok) return [];
  const entries: Array<{ name: string; type: string }> = await res.json();
  return entries
    .filter((e) => e.type === "dir")
    .map((e) => e.name)
    .sort()
    .reverse(); // newest first
}

async function fetchFundContent(batch: string, fundId: string): Promise<string | null> {
  const url = `${GH_RAW}/${REPO}/${BRANCH}/data/scraped/${batch}/${fundId}.json`;
  try {
    const res = await fetch(url, { next: { revalidate: 3600 } });
    if (!res.ok) return null;
    const data = await res.json();
    return (data.content as string) || null;
  } catch {
    return null;
  }
}

export async function GET() {
  try {
    const headers: Record<string, string> = {
      Accept:       "application/vnd.github.v3+json",
      "User-Agent": "groww-rag-ticker",
    };
    const token = process.env.GITHUB_TOKEN;
    if (token) headers["Authorization"] = `token ${token}`;

    const batches = await listBatches(headers);
    if (batches.length === 0) return Response.json({ items: [] });

    const fundData: Record<string, FundMetrics> = {};
    const allFundIds = Object.keys(TICKER_FUNDS);

    for (const batch of batches) {
      const missing = allFundIds.filter((id) => !(id in fundData));
      if (missing.length === 0) break;

      // Fetch all missing funds in this batch in parallel
      const results = await Promise.all(
        missing.map(async (fundId) => {
          const content = await fetchFundContent(batch, fundId);
          if (!content) return null;
          return { fundId, metrics: extractMetrics(content) };
        })
      );

      for (const r of results) {
        if (r) {
          fundData[r.fundId] = { name: TICKER_FUNDS[r.fundId], ...r.metrics };
        }
      }
    }

    // Interleave PPFAS and JBR funds so both appear immediately in the ticker
    const ppfasIds = allFundIds.filter((id) => id.startsWith("ppfas"));
    const jbrIds   = allFundIds.filter((id) => id.startsWith("jbr"));
    const interleavedIds: string[] = [];
    const maxLen = Math.max(ppfasIds.length, jbrIds.length);
    for (let i = 0; i < maxLen; i++) {
      if (ppfasIds[i]) interleavedIds.push(ppfasIds[i]);
      if (jbrIds[i])   interleavedIds.push(jbrIds[i]);
    }

    const items: TickerItem[] = [];
    for (const fundId of interleavedIds) {
      const fd = fundData[fundId];
      if (!fd) continue;
      if (fd.nav)
        items.push({ label: fd.name, metric: "NAV",           value: fd.nav,           change: fd.change });
      if (fd.aum)
        items.push({ label: fd.name, metric: "AUM",           value: fd.aum,           change: null });
      if (fd.expense_ratio)
        items.push({ label: fd.name, metric: "Expense Ratio", value: fd.expense_ratio, change: null });
      if (fd.min_sip)
        items.push({ label: fd.name, metric: "Min SIP",       value: fd.min_sip,       change: null });
    }

    return Response.json({ items });
  } catch {
    return Response.json({ items: [] });
  }
}
