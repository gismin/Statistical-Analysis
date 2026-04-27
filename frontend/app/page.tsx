import Link from "next/link";
import { Button } from "@/components/ui/button";

const features = [
  {
    href: "/time",
    title: "Time",
    description: "When are highs & lows typically set? Reversal probability by session time.",
    status: "coming-soon",
  },
  {
    href: "/distance",
    title: "Distance",
    description: "How far has price moved vs. history? Extension vs. reversal probability.",
    status: "coming-soon",
  },
  {
    href: "/summary",
    title: "Summary",
    description: "Combined Time + Distance across two timeframes. Confidence Targets.",
    status: "coming-soon",
  },
  {
    href: "/overview",
    title: "Overview",
    description: "All assets × all stats in one sortable table.",
    status: "coming-soon",
  },
];

export default function Home() {
  return (
    <main className="min-h-screen bg-background text-foreground">
      <div className="mx-auto max-w-5xl px-6 py-20">
        <div className="mb-16 space-y-4">
          <h1 className="text-4xl font-bold tracking-tight">Statistical Analysis</h1>
          <p className="max-w-xl text-lg text-muted-foreground">
            Probabilistic insights for crypto markets — know when highs and lows are likely to hold,
            and how far price is statistically likely to move.
          </p>
        </div>

        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
          {features.map((f) => (
            <div
              key={f.href}
              className="rounded-xl border bg-card p-6 shadow-sm transition-shadow hover:shadow-md"
            >
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-xl font-semibold">{f.title}</h2>
                {f.status === "coming-soon" && (
                  <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                    Coming soon
                  </span>
                )}
              </div>
              <p className="mb-5 text-sm text-muted-foreground">{f.description}</p>
              <Button variant="outline" size="sm" disabled={f.status === "coming-soon"}>
                {f.title} →
              </Button>
            </div>
          ))}
        </div>
      </div>
    </main>
  );
}
