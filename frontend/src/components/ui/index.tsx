"use client";

import { clsx } from "clsx";
import type { ReactNode } from "react";

export function Card({
  children,
  className,
  title,
  subtitle,
}: {
  children: ReactNode;
  className?: string;
  title?: string;
  subtitle?: string;
}) {
  return (
    <div className={clsx("card animate-fade-in", className)}>
      {(title || subtitle) && (
        <div className="mb-4">
          {title && (
            <p className="label mb-1">{title}</p>
          )}
          {subtitle && (
            <p className="text-xs text-zinc-500">{subtitle}</p>
          )}
        </div>
      )}
      {children}
    </div>
  );
}

export function RegimeBadge({ regime }: { regime: string }) {
  const cls =
    regime === "risk_on"
      ? "badge-risk-on"
      : regime === "risk_off"
      ? "badge-risk-off"
      : "badge-transition";
  const label =
    regime === "risk_on" ? "Risk On" : regime === "risk_off" ? "Risk Off" : "Transition";
  return <span className={clsx("badge", cls)}>{label}</span>;
}

export function Spinner({ size = 16 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      className="animate-spin text-zinc-500"
    >
      <circle cx="12" cy="12" r="10" strokeOpacity="0.25" />
      <path d="M12 2a10 10 0 0 1 10 10" strokeLinecap="round" />
    </svg>
  );
}

export function StatBlock({
  label,
  value,
  sub,
  color,
}: {
  label: string;
  value: string | number;
  sub?: string;
  color?: string;
}) {
  return (
    <div>
      <p className="label mb-1">{label}</p>
      <p className="stat-value" style={color ? { color } : undefined}>
        {value}
      </p>
      {sub && <p className="text-xs text-zinc-500 mt-0.5 font-mono">{sub}</p>}
    </div>
  );
}

export function Divider() {
  return <div className="h-px bg-zinc-800 my-4" />;
}
