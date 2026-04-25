import type { AgentRecord, BuiltInTool } from "./api";

export const SELLER_CATEGORIES = [
  "General Research",
  "Science & Academic",
  "Business & Finance",
  "News & Monitoring",
  "Geography & Weather",
  "Data & Utilities",
] as const;

const TOOL_CATEGORY_BY_ID: Record<string, (typeof SELLER_CATEGORIES)[number]> = {
  web_search: "General Research",
  tavily_search: "General Research",
  yutori_research: "General Research",
  wikipedia_summary: "General Research",
  page_reader: "General Research",

  arxiv_search: "Science & Academic",
  crossref_lookup: "Science & Academic",
  semantic_scholar_search: "Science & Academic",
  openalex_search: "Science & Academic",

  sec_edgar_filings: "Business & Finance",
  company_ticker_lookup: "Business & Finance",
  world_bank_indicators: "Business & Finance",
  github_repo_inspector: "Business & Finance",

  gdelt_news_search: "News & Monitoring",
  mediastack_news: "News & Monitoring",
  newsapi_dev: "News & Monitoring",
  hacker_news_search: "News & Monitoring",
  rss_reader: "News & Monitoring",
  changelog_reader: "News & Monitoring",

  open_meteo_weather: "Geography & Weather",
  nominatim_geocode: "Geography & Weather",
  timezone_lookup: "Geography & Weather",

  pdf_reader: "Data & Utilities",
  csv_analyzer: "Data & Utilities",
  json_api_fetcher: "Data & Utilities",
  calculator: "Data & Utilities",
  date_time_tool: "Data & Utilities",
};

export function getDefaultSellerCategory(): string {
  return SELLER_CATEGORIES[0];
}

export function normalizeSellerCategory(category: unknown): string {
  if (typeof category !== "string") return getDefaultSellerCategory();
  const trimmed = category.trim();
  return SELLER_CATEGORIES.includes(trimmed as (typeof SELLER_CATEGORIES)[number])
    ? trimmed
    : getDefaultSellerCategory();
}

export function getToolCategory(toolId: string): (typeof SELLER_CATEGORIES)[number] {
  return TOOL_CATEGORY_BY_ID[toolId] ?? "General Research";
}

export function groupToolsByCategory(tools: BuiltInTool[]): Array<{
  category: (typeof SELLER_CATEGORIES)[number];
  tools: BuiltInTool[];
}> {
  const sorted = [...tools].sort((a, b) => a.name.localeCompare(b.name));
  return SELLER_CATEGORIES.map((category) => ({
    category,
    tools: sorted.filter((tool) => getToolCategory(tool.id) === category),
  })).filter((group) => group.tools.length > 0);
}

export function getSellerStatus(agent: AgentRecord): "draft" | "published" | "disabled" {
  const status = typeof agent.metadata.status === "string" ? agent.metadata.status.toLowerCase() : "published";
  if (status === "draft" || status === "published" || status === "disabled") return status;
  return "published";
}

export function isSellerPublished(agent: AgentRecord): boolean {
  return getSellerStatus(agent) === "published";
}

export function getSellerPrice(agent: AgentRecord): string {
  const price = agent.metadata.price_usdc;
  if (typeof price === "string" && price.trim()) return price.trim();
  if (typeof price === "number" && Number.isFinite(price)) return price.toFixed(6);
  return "0.010000";
}

export function getSellerToolIds(agent: AgentRecord): string[] {
  const tools = agent.metadata.built_in_tools;
  if (!Array.isArray(tools)) return [];
  return tools.filter((tool): tool is string => typeof tool === "string" && tool.trim().length > 0);
}

export function formatToolNames(toolIds: string[], availableTools: BuiltInTool[] = []): string {
  const byId = new Map(availableTools.map((tool) => [tool.id, tool.name]));
  const names = toolIds.map((toolId) => byId.get(toolId) ?? toolId.replace(/_/g, " "));
  return names.length > 0 ? names.join(", ") : "No tools";
}
