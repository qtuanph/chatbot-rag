/* eslint-disable react-hooks/exhaustive-deps, react-hooks/refs */

"use client";

import type { HTMLAttributes, ReactElement } from "react";
import {
  Children,
  createContext,
  isValidElement,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";
import { Check, Loader2 } from "lucide-react";

import { cn } from "@/lib/utils";

// ==========================================
// Types
// ==========================================

export type StepperOrientation = "horizontal" | "vertical";
export type StepState = "active" | "completed" | "inactive" | "loading";

export type StepIndicators = {
  active?: React.ReactNode;
  completed?: React.ReactNode;
  inactive?: React.ReactNode;
  loading?: React.ReactNode;
};

export interface StepItem {
  title: string;
  description?: string;
  icon?: React.ComponentType<{ className?: string }>;
  optional?: boolean;
}

export interface StepperContextValue {
  activeStep: number;
  setActiveStep: (step: number) => void;
  nextStep: () => void;
  prevStep: () => void;
  isFirst: boolean;
  isLast: boolean;
  stepsCount: number;
  orientation: StepperOrientation;
  registerTrigger: (node: HTMLButtonElement | null) => void;
  triggerNodes: HTMLButtonElement[];
  focusNext: (currentIdx: number) => void;
  focusPrev: (currentIdx: number) => void;
  focusFirst: () => void;
  focusLast: () => void;
  indicators: StepIndicators;
}

export interface StepItemContextValue {
  step: number;
  state: StepState;
  isDisabled: boolean;
  isLoading: boolean;
}

// ==========================================
// Contexts & Hooks
// ==========================================

const StepperContext = createContext<StepperContextValue | undefined>(undefined);
const StepItemContext = createContext<StepItemContextValue | undefined>(undefined);

export function useStepper() {
  const ctx = useContext(StepperContext);
  if (!ctx) throw new Error("useStepper must be used within a Stepper");
  return ctx;
}

export function useStepItem() {
  const ctx = useContext(StepItemContext);
  if (!ctx) throw new Error("useStepItem must be used within a StepperItem");
  return ctx;
}

// ==========================================
// Primitive 1: Stepper Root
// ==========================================

export interface StepperProps extends HTMLAttributes<HTMLDivElement> {
  defaultValue?: number;
  value?: number;
  onValueChange?: (value: number) => void;
  orientation?: StepperOrientation;
  indicators?: StepIndicators;
  totalSteps?: number;
}

export function Stepper({
  defaultValue = 1,
  value,
  onValueChange,
  orientation = "horizontal",
  className,
  children,
  indicators = {},
  totalSteps,
  ...props
}: StepperProps) {
  const [activeStep, setActiveStep] = useState(defaultValue);
  const [triggerNodes, setTriggerNodes] = useState<HTMLButtonElement[]>([]);

  const registerTrigger = useCallback((node: HTMLButtonElement | null) => {
    setTriggerNodes((prev) => {
      if (node && !prev.includes(node)) {
        return [...prev, node];
      } else if (!node && prev.includes(node!)) {
        return prev.filter((n) => n !== node);
      }
      return prev;
    });
  }, []);

  const handleSetActiveStep = useCallback(
    (step: number) => {
      if (value === undefined) {
        setActiveStep(step);
      }
      onValueChange?.(step);
    },
    [value, onValueChange]
  );

  const currentStep = value ?? activeStep;

  // Keyboard navigation logic
  const focusTrigger = (idx: number) => {
    if (triggerNodes[idx]) triggerNodes[idx].focus();
  };
  const focusNext = (currentIdx: number) =>
    focusTrigger((currentIdx + 1) % triggerNodes.length);
  const focusPrev = (currentIdx: number) =>
    focusTrigger((currentIdx - 1 + triggerNodes.length) % triggerNodes.length);
  const focusFirst = () => focusTrigger(0);
  const focusLast = () => focusTrigger(triggerNodes.length - 1);

  const count =
    totalSteps ??
    Children.toArray(children).filter(
      (child): child is ReactElement =>
        isValidElement(child) &&
        (child.type as { displayName?: string })?.displayName === "StepperItem"
    ).length;

  const nextStep = useCallback(() => {
    handleSetActiveStep(Math.min(currentStep + 1, count || 99));
  }, [currentStep, count, handleSetActiveStep]);

  const prevStep = useCallback(() => {
    handleSetActiveStep(Math.max(currentStep - 1, 1));
  }, [currentStep, handleSetActiveStep]);

  const contextValue = useMemo<StepperContextValue>(
    () => ({
      activeStep: currentStep,
      setActiveStep: handleSetActiveStep,
      nextStep,
      prevStep,
      isFirst: currentStep === 1,
      isLast: count > 0 && currentStep === count,
      stepsCount: count,
      orientation,
      registerTrigger,
      focusNext,
      focusPrev,
      focusFirst,
      focusLast,
      triggerNodes,
      indicators,
    }),
    [
      currentStep,
      handleSetActiveStep,
      nextStep,
      prevStep,
      count,
      orientation,
      registerTrigger,
      triggerNodes,
      indicators,
    ]
  );

  return (
    <StepperContext.Provider value={contextValue}>
      <div
        role="tablist"
        aria-orientation={orientation}
        data-slot="stepper"
        className={cn("w-full", className)}
        data-orientation={orientation}
        {...props}
      >
        {children}
      </div>
    </StepperContext.Provider>
  );
}

// ==========================================
// Primitive 2: StepperItem
// ==========================================

export interface StepperItemProps extends React.HTMLAttributes<HTMLDivElement> {
  step: number;
  completed?: boolean;
  disabled?: boolean;
  loading?: boolean;
}

export function StepperItem({
  step,
  completed = false,
  disabled = false,
  loading = false,
  className,
  children,
  ...props
}: StepperItemProps) {
  const { activeStep } = useStepper();

  const state: StepState =
    completed || step < activeStep
      ? "completed"
      : activeStep === step
        ? "active"
        : "inactive";

  const isLoading = loading && step === activeStep;

  return (
    <StepItemContext.Provider
      value={{ step, state, isDisabled: disabled, isLoading }}
    >
      <div
        data-slot="stepper-item"
        className={cn(
          "group/step flex items-center justify-center not-last:flex-1 group-data-[orientation=horizontal]/stepper-nav:flex-row group-data-[orientation=vertical]/stepper-nav:flex-col",
          className
        )}
        data-state={state}
        {...(isLoading ? { "data-loading": true } : {})}
        {...props}
      >
        {children}
      </div>
    </StepItemContext.Provider>
  );
}
StepperItem.displayName = "StepperItem";

// ==========================================
// Primitive 3: StepperTrigger
// ==========================================

export type StepperTriggerProps = useRender.ComponentProps<"button">;

export function StepperTrigger({
  className,
  children,
  tabIndex,
  render,
  ...props
}: StepperTriggerProps) {
  const { state, isLoading } = useStepItem();
  const stepperCtx = useStepper();
  const {
    setActiveStep,
    activeStep,
    registerTrigger,
    triggerNodes,
    focusNext,
    focusPrev,
    focusFirst,
    focusLast,
  } = stepperCtx;
  const { step, isDisabled } = useStepItem();
  const isSelected = activeStep === step;
  const id = `stepper-tab-${step}`;
  const panelId = `stepper-panel-${step}`;

  const btnRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (btnRef.current) {
      registerTrigger(btnRef.current);
    }
  }, [registerTrigger]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLButtonElement>) => {
    const myIdx = triggerNodes.findIndex((n: HTMLButtonElement) => n === btnRef.current);
    switch (e.key) {
      case "ArrowRight":
      case "ArrowDown":
        e.preventDefault();
        if (myIdx !== -1 && focusNext) focusNext(myIdx);
        break;
      case "ArrowLeft":
      case "ArrowUp":
        e.preventDefault();
        if (myIdx !== -1 && focusPrev) focusPrev(myIdx);
        break;
      case "Home":
        e.preventDefault();
        if (focusFirst) focusFirst();
        break;
      case "End":
        e.preventDefault();
        if (focusLast) focusLast();
        break;
      case "Enter":
      case " ":
        e.preventDefault();
        setActiveStep(step);
        break;
    }
  };

  const defaultProps = {
    role: "tab",
    id,
    "aria-selected": isSelected,
    "aria-controls": panelId,
    tabIndex: typeof tabIndex === "number" ? tabIndex : isSelected ? 0 : -1,
    "data-slot": "stepper-trigger",
    "data-state": state,
    "data-loading": isLoading,
    className: cn(
      "focus-visible:border-ring focus-visible:ring-ring/50 inline-flex cursor-pointer items-center outline-none focus-visible:z-10 focus-visible:ring-3 disabled:pointer-events-none disabled:opacity-60 select-none",
      "gap-2.5 rounded-full transition-colors",
      className
    ),
    onClick: () => setActiveStep(step),
    onKeyDown: handleKeyDown,
    disabled: isDisabled,
    children,
  };

  return useRender({
    defaultTagName: "button",
    render,
    ref: btnRef,
    props: mergeProps<"button">(defaultProps, props),
  });
}

// ==========================================
// Primitive 4: StepperIndicator
// ==========================================

export function StepperIndicator({
  children,
  className,
}: React.ComponentProps<"div">) {
  const { state, isLoading } = useStepItem();
  const { indicators } = useStepper();

  return (
    <div
      data-slot="stepper-indicator"
      data-state={state}
      className={cn(
        "border-background bg-accent text-accent-foreground data-[state=completed]:bg-primary data-[state=completed]:text-primary-foreground data-[state=active]:bg-primary data-[state=active]:text-primary-foreground relative flex size-7 shrink-0 items-center justify-center overflow-hidden transition-all",
        "rounded-full text-xs font-semibold shadow-xs",
        className
      )}
    >
      <div className="flex items-center justify-center">
        {isLoading ? (
          <Loader2 className="size-3.5 animate-spin" />
        ) : state === "completed" ? (
          indicators.completed ?? <Check className="size-3.5 stroke-[2.5]" />
        ) : state === "active" ? (
          indicators.active ?? children
        ) : (
          indicators.inactive ?? children
        )}
      </div>
    </div>
  );
}

// ==========================================
// Primitive 5: StepperSeparator
// ==========================================

export function StepperSeparator({ className }: React.ComponentProps<"div">) {
  const { state } = useStepItem();

  return (
    <div
      data-slot="stepper-separator"
      data-state={state}
      className={cn(
        "bg-border data-[state=completed]:bg-primary rounded-full m-1 group-data-[orientation=horizontal]/stepper-nav:h-0.5 group-data-[orientation=horizontal]/stepper-nav:flex-1 group-data-[orientation=vertical]/stepper-nav:h-12 group-data-[orientation=vertical]/stepper-nav:w-0.5 transition-colors",
        className
      )}
    />
  );
}

// ==========================================
// Primitive 6: StepperTitle & Description
// ==========================================

export function StepperTitle({ children, className }: React.ComponentProps<"h3">) {
  const { state } = useStepItem();

  return (
    <h3
      data-slot="stepper-title"
      data-state={state}
      className={cn(
        "text-xs leading-none font-medium transition-colors",
        state === "active" && "font-semibold text-foreground",
        state === "completed" && "text-foreground",
        state === "inactive" && "text-muted-foreground",
        className
      )}
    >
      {children}
    </h3>
  );
}

export function StepperDescription({
  children,
  className,
}: React.ComponentProps<"div">) {
  const { state } = useStepItem();

  return (
    <div
      data-slot="stepper-description"
      data-state={state}
      className={cn("text-muted-foreground text-[10px] mt-0.5", className)}
    >
      {children}
    </div>
  );
}

// ==========================================
// Primitive 7: StepperNav, Panel & Content
// ==========================================

export function StepperNav({ children, className }: React.ComponentProps<"nav">) {
  const { activeStep, orientation } = useStepper();

  return (
    <nav
      data-slot="stepper-nav"
      data-state={activeStep}
      data-orientation={orientation}
      className={cn(
        "group/stepper-nav inline-flex data-[orientation=horizontal]:w-full data-[orientation=horizontal]:flex-row data-[orientation=vertical]:flex-col items-center",
        className
      )}
    >
      {children}
    </nav>
  );
}

export function StepperPanel({ children, className }: React.ComponentProps<"div">) {
  const { activeStep } = useStepper();

  return (
    <div
      data-slot="stepper-panel"
      data-state={activeStep}
      className={cn("w-full", className)}
    >
      {children}
    </div>
  );
}

export interface StepperContentProps extends React.ComponentProps<"div"> {
  value: number;
  forceMount?: boolean;
}

export function StepperContent({
  value,
  forceMount,
  children,
  className,
}: StepperContentProps) {
  const { activeStep } = useStepper();
  const isActive = value === activeStep;

  if (!forceMount && !isActive) {
    return null;
  }

  return (
    <div
      data-slot="stepper-content"
      data-state={activeStep}
      className={cn("w-full animate-in fade-in-50 duration-200", className, !isActive && forceMount && "hidden")}
      hidden={!isActive && forceMount}
    >
      {children}
    </div>
  );
}

// ==============================================================================
// High-Level Helper: StepBar (Cực tiện cho form chỉ cần truyền props mảng steps)
// ==============================================================================

export interface StepBarProps {
  steps: StepItem[];
  activeStep: number; // 1-indexed (1, 2, 3...) hoặc 0-indexed (sẽ tự chuẩn hoá)
  onStepClick?: (step: number) => void;
  className?: string;
}

export function StepBar({ steps, activeStep, onStepClick, className }: StepBarProps) {
  // Chuẩn hoá: nếu activeStep là 0-indexed (ví dụ 0, 1, 2), chuyển thành 1-indexed cho ReUI
  const normalizedStep = activeStep === 0 ? 1 : activeStep;

  return (
    <Stepper
      value={normalizedStep}
      onValueChange={(val) => {
        onStepClick?.(val);
      }}
      totalSteps={steps.length}
      className={cn("w-full select-none", className)}
    >
      <StepperNav>
        {steps.map((step, idx) => {
          const stepNumber = idx + 1;
          const Icon = step.icon;

          return (
            <StepperItem key={stepNumber} step={stepNumber}>
              <StepperTrigger className="group">
                <StepperIndicator>
                  {Icon ? <Icon className="size-3.5" /> : stepNumber}
                </StepperIndicator>
                <div className="flex flex-col text-left">
                  <StepperTitle>{step.title}</StepperTitle>
                  {step.description && (
                    <StepperDescription className="hidden sm:inline">
                      {step.description}
                    </StepperDescription>
                  )}
                </div>
              </StepperTrigger>
              {idx < steps.length - 1 && <StepperSeparator />}
            </StepperItem>
          );
        })}
      </StepperNav>
    </Stepper>
  );
}
