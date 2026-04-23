export interface Agent {
  id: string;
  name: string;
  description: string;
  category: string;
  price: number;
}

export const MOCK_SELLER_AGENTS: Agent[] = [
  {
    id: "sa-1",
    name: "DataScraper Pro",
    description: "Extracts structured data from any website.",
    category: "Data",
    price: 0.05,
  },
  {
    id: "sa-2",
    name: "CryptoAnalyzer",
    description: "Analyzes market trends and sentiment for major cryptocurrencies.",
    category: "Finance",
    price: 0.12,
  },
  {
    id: "sa-3",
    name: "SupportBot Alpha",
    description: "Handles Tier 1 customer support tickets.",
    category: "Customer Service",
    price: 0.08,
  },
  {
    id: "sa-4",
    name: "CodeReviewer",
    description: "Automated PR reviews and security analysis.",
    category: "Development",
    price: 0.15,
  },
  {
    id: "sa-5",
    name: "LeadGen Expert",
    description: "Discovers and qualifies B2B leads from public internet sources.",
    category: "Sales",
    price: 0.20,
  },
  {
    id: "sa-6",
    name: "SocialManager",
    description: "Schedules and creates content for social media channels.",
    category: "Marketing",
    price: 0.10,
  },
];
