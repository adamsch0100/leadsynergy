"use client";

import { createContext, useContext, useState } from "react";
import { PlanId, BasePlanId } from "@/lib/plans";

interface PricingContextType {
  // Legacy plan support
  selectedPlan: PlanId;
  setSelectedPlan: (plan: PlanId) => void;
  // New modular plan support
  selectedBasePlan: BasePlanId;
  setSelectedBasePlan: (plan: BasePlanId) => void;
}

const PricingContext = createContext<PricingContextType | undefined>(undefined);

export function PricingProvider({ children }: { children: React.ReactNode }) {
  // Legacy plan state (for backward compatibility)
  const [selectedPlan, setSelectedPlan] = useState<PlanId>("solo");
  // New modular plan state
  const [selectedBasePlan, setSelectedBasePlan] = useState<BasePlanId>("growth");

  return (
    <PricingContext.Provider value={{
      selectedPlan,
      setSelectedPlan,
      selectedBasePlan,
      setSelectedBasePlan,
    }}>
      {children}
    </PricingContext.Provider>
  );
}

export function usePricing() {
  const context = useContext(PricingContext);
  if (!context) {
    throw new Error("usePricing must be used within a PricingProvider");
  }
  return context;
}
