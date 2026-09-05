"use client";

import { useCallback, useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { analyticsApi } from "@/lib/api-client";
import type { AnalyticsStats } from "@/types/api";

export type ModelPricingConfig = {
  llmInput: number;
  llmOutput: number;
  embInput: number;
  rerankInput: number;
  preset: string;
};

export const DEFAULT_PRICING: ModelPricingConfig = {
  llmInput: 1308,     // FPT Cloud LLM (gpt-oss-20b)
  llmOutput: 5233,
  embInput: 291,      // FPT AI Factory
  rerankInput: 0,
  preset: "fpt",
};

export const DATE_RANGES = [
  { label: "1 ngày", value: 1 },
  { label: "7 ngày", value: 7 },
  { label: "30 ngày", value: 30 },
  { label: "90 ngày", value: 90 },
];

export function useAnalyticsStats(initialDays = 30, initialStats: AnalyticsStats | null = null) {
  const { data: session } = useSession();
  const [days, setDays] = useState(initialDays);
  const [stats, setStats] = useState<AnalyticsStats | null>(initialStats);
  const [loading, setLoading] = useState(!initialStats);
  const [error, setError] = useState<string | null>(null);
  const [pricing, setPricing] = useState<ModelPricingConfig>(DEFAULT_PRICING);

  useEffect(() => {
    try {
      const saved = localStorage.getItem("chatbot_custom_model_pricing_v2");
      if (saved) {
        const parsed = JSON.parse(saved);
        setPricing({
          llmInput: typeof parsed.llmInput === "number" ? parsed.llmInput : DEFAULT_PRICING.llmInput,
          llmOutput: typeof parsed.llmOutput === "number" ? parsed.llmOutput : DEFAULT_PRICING.llmOutput,
          embInput: typeof parsed.embInput === "number" ? parsed.embInput : DEFAULT_PRICING.embInput,
          rerankInput: typeof parsed.rerankInput === "number" ? parsed.rerankInput : DEFAULT_PRICING.rerankInput,
          preset: parsed.preset || "custom",
        });
      }
    } catch {
      // Ignore localStorage errors
    }
  }, []);

  const updatePricing = (newP: Partial<ModelPricingConfig>) => {
    setPricing((prev) => {
      const updated = { ...prev, ...newP };
      try {
        localStorage.setItem("chatbot_custom_model_pricing_v2", JSON.stringify(updated));
      } catch {
        // Ignore
      }
      return updated;
    });
  };

  const loadStats = useCallback(async (silent = false) => {
    if (!session) return;
    try {
      if (!silent) setLoading(true);
      setError(null);
      const nextStats = await analyticsApi.getStats(days);
      setStats(nextStats);
    } catch (err) {
      if (!silent) {
        setError(err instanceof Error ? err.message : "Không thể tải thống kê");
      }
    } finally {
      if (!silent) setLoading(false);
    }
  }, [days, session]);

  useEffect(() => {
    void loadStats();
  }, [loadStats]);

  // Background polling every 8 seconds when visible
  useEffect(() => {
    const interval = setInterval(() => {
      if (document.visibilityState === "visible") {
        void loadStats(true);
      }
    }, 8000);
    return () => clearInterval(interval);
  }, [loadStats]);

  const llmCostVnd = stats ? Math.round((stats.by_model_type.llm.tokens_in * pricing.llmInput) / 1000000 + (stats.by_model_type.llm.tokens_out * pricing.llmOutput) / 1000000) : 0;
  const embCostVnd = stats ? Math.round((stats.by_model_type.embedding.tokens_in * pricing.embInput) / 1000000) : 0;
  const rerankCostVnd = stats ? Math.round((stats.by_model_type.reranker.tokens_in * pricing.rerankInput) / 1000000) : 0;
  const totalCalculatedCostVnd = llmCostVnd + embCostVnd + rerankCostVnd;

  return {
    days,
    setDays,
    stats,
    loading,
    error,
    pricing,
    updatePricing,
    loadStats,
    llmCostVnd,
    embCostVnd,
    rerankCostVnd,
    totalCalculatedCostVnd,
  };
}
