import Link from "next/link";

const features = [
  {
    href: "/time",
    title: "Time",
    description: "When are highs & lows typically set? Reversal probability by session time.",
    status: "live",
  },
  {
    href: "/distance",
    title: "Distance",
    description: "How far has price moved vs. history? Extension vs. reversal probability.",
    status: "live",
  },
  {
    href: "/p1p2/summary",
    title: "P1/P2 Summary",
    description: "Flip risk · P2 likelihood by time & distance · Early-P1 warnings.",
    status: "live",
  },
  {
    href: "/p1p2/distance",
    title: "Confidence Targets",
    description: "Long & short price targets at 90/80/70/60/50% confidence, from historical P2 moves.",
    status: "live",
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
                {f.status === "coming-soon" ? (
                  <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                    Coming soon
                  </span>
                ) : (
                  <span className="rounded-full bg-green-500/20 border border-green-500/40 px-2 py-0.5 text-xs text-green-400">
                    Live
                  </span>
                )}
              </div>
              <p className="mb-5 text-sm text-muted-foreground">{f.description}</p>
              {f.status === "coming-soon" ? (
                <span className="inline-flex h-7 items-center rounded-[min(var(--radius-md),12px)] border border-border bg-background px-2.5 text-[0.8rem] font-medium text-muted-foreground opacity-50 cursor-not-allowed">
                  {f.title} →
                </span>
              ) : (
                <Link
                  href={f.href}
                  className="inline-flex h-7 items-center rounded-[min(var(--radius-md),12px)] border border-border bg-background px-2.5 text-[0.8rem] font-medium transition-colors hover:bg-muted hover:text-foreground"
                >
                  {f.title} →
                </Link>
              )}
            </div>
          ))}
        </div>
      </div>
    </main>
  );
}
