"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTheme } from "@/components/ThemeProvider";
import { Moon, Sun, BarChart3, Users, History, LayoutDashboard } from "lucide-react";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/candidates", label: "Candidates", icon: Users },
  { href: "/history", label: "History", icon: History },
];

export function NavBar() {
  const { theme, toggleTheme } = useTheme();
  const pathname = usePathname();

  return (
    <nav className="border-b border-border bg-card/80 backdrop-blur-xl sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-6 flex items-center justify-between h-16">
        <div className="flex items-center gap-8">
          <Link href="/" className="flex items-center gap-2.5 font-bold text-lg">
            <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center">
              <BarChart3 className="w-4.5 h-4.5 text-primary" />
            </div>
            <span className="gradient-text">IPO Radar</span>
          </Link>
          <div className="flex items-center gap-1">
            {NAV_ITEMS.map((item) => {
              const isActive = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`relative flex items-center gap-2 px-3.5 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${
                    isActive
                      ? "text-primary bg-primary/10"
                      : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
                  }`}
                >
                  <item.icon className="w-4 h-4" />
                  {item.label}
                  {isActive && (
                    <span className="absolute -bottom-[calc(0.5rem+1px)] left-3 right-3 h-0.5 gradient-border rounded-full" />
                  )}
                </Link>
              );
            })}
          </div>
        </div>
        <button
          onClick={toggleTheme}
          className="p-2.5 rounded-xl bg-muted/50 text-foreground hover:bg-muted transition-colors"
          aria-label="Toggle dark mode"
        >
          {theme === "dark" ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
        </button>
      </div>
    </nav>
  );
}
