/**
 * AI Provider and Model Configuration (2025)
 * All models support tool/function calling
 */

export interface Provider {
  id: string;
  name: string;
  models: Model[];
}

export interface Model {
  id: string;
  name: string;
  description?: string;
}

export const AI_PROVIDERS: Provider[] = [
  {
    id: "openai",
    name: "OpenAI",
    models: [
      // GPT-5 Family (Latest - August 2025)
      {
        id: "gpt-5",
        name: "GPT-5",
        description: "Flagship model for coding & agentic tasks ($1.25/$10 per 1M tokens)",
      },
      {
        id: "gpt-5-mini",
        name: "GPT-5 Mini",
        description: "Smaller, faster GPT-5 variant",
      },

      // GPT-4.1 Family (April 2025) - 1M token context
      {
        id: "gpt-4.1",
        name: "GPT-4.1",
        description: "Most capable 4.1 model, 1M context ($2/$8 per 1M tokens)",
      },
      {
        id: "gpt-4.1-mini",
        name: "GPT-4.1 Mini",
        description: "Best value - 83% cheaper than GPT-4o, 1M context",
      },
      {
        id: "gpt-4.1-nano",
        name: "GPT-4.1 Nano",
        description: "Ultra-cheap, 1M context",
      },

      // GPT-4o Family (Legacy but still available)
      {
        id: "gpt-4o",
        name: "GPT-4o",
        description: "Previous flagship, multimodal ($5/$20 per 1M tokens)",
      },
      {
        id: "gpt-4o-mini",
        name: "GPT-4o Mini",
        description: "Previous budget option ($0.60/$2.40 per 1M tokens)",
      },
    ],
  },
  {
    id: "gemini",
    name: "Google Gemini",
    models: [
      {
        id: "gemini-2.0-flash-exp",
        name: "Gemini 2.0 Flash (Experimental)",
        description: "Latest experimental model with fast responses",
      },
      {
        id: "gemini-1.5-pro",
        name: "Gemini 1.5 Pro",
        description: "Most capable, 2M token context",
      },
      {
        id: "gemini-1.5-flash",
        name: "Gemini 1.5 Flash",
        description: "Fast and efficient, 1M token context",
      },
      {
        id: "gemini-1.5-flash-8b",
        name: "Gemini 1.5 Flash-8B",
        description: "Smallest and fastest",
      },
    ],
  },
  {
    id: "fireworks",
    name: "Fireworks AI",
    models: [
      {
        id: "accounts/fireworks/models/qwen3-30b-a3b",
        name: "Qwen 3 30B",
        description: "Alibaba's Qwen 3 model (30B parameters)",
      },
      {
        id: "accounts/fireworks/models/llama-v3p1-70b-instruct",
        name: "Llama 3.1 70B Instruct",
        description: "Meta's Llama 3.1 70B, 131K context",
      },
      {
        id: "accounts/fireworks/models/llama-v3p1-8b-instruct",
        name: "Llama 3.1 8B Instruct",
        description: "Smaller, faster Llama model",
      },
      {
        id: "accounts/fireworks/models/qwen2p5-72b-instruct",
        name: "Qwen 2.5 72B Instruct",
        description: "Latest Qwen model, very capable",
      },
    ],
  },
];

/**
 * Get models for a specific provider
 */
export function getModelsForProvider(providerId: string): Model[] {
  const provider = AI_PROVIDERS.find((p) => p.id === providerId);
  return provider?.models || [];
}

/**
 * Get provider name by ID
 */
export function getProviderName(providerId: string): string {
  const provider = AI_PROVIDERS.find((p) => p.id === providerId);
  return provider?.name || providerId;
}

/**
 * Get default model for a provider
 */
export function getDefaultModel(providerId: string): string {
  const models = getModelsForProvider(providerId);
  return models[0]?.id || "";
}
