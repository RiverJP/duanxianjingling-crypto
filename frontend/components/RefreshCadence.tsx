import { Clock3 } from "lucide-react";
import { SchedulerStatus } from "@/types/asset";

export function RefreshCadence({ status, compact = false }: { status: SchedulerStatus; compact?: boolean }) {
  const items = [
    { label: "全市场扫描", value: `${status.tasks.market_scan_minutes} 分钟` },
    { label: "候选机会", value: `${status.tasks.candidate_scan_minutes} 分钟` },
    { label: "持仓盈亏", value: `${status.tasks.paper_position_minutes} 分钟` },
    { label: "止盈止损", value: `${status.tasks.paper_position_minutes} 分钟` },
    { label: "4H 指标", value: `${status.tasks.technical_refresh_minutes} 分钟` },
    { label: "收益快照", value: status.tasks.daily_snapshot },
  ];

  return (
    <section className={`rounded border border-ink/10 bg-white ${compact ? "p-4" : "p-4 sm:p-5"}`}>
      <div className="mb-3 flex items-start gap-3">
        <span className="rounded bg-mint/15 p-2 text-mint">
          <Clock3 size={18} />
        </span>
        <div>
          <h2 className="text-sm font-semibold text-ink">数据刷新节奏</h2>
          <p className="mt-1 text-xs leading-5 text-ink/55">
            后台分层刷新：先扫全市场，再高频跟踪候选机会和模拟持仓。
          </p>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-2 md:grid-cols-3 xl:grid-cols-6">
        {items.map((item) => (
          <div key={item.label} className="rounded bg-panel p-3">
            <p className="text-xs text-ink/45">{item.label}</p>
            <p className="mt-1 text-sm font-semibold tabular-nums text-ink">{item.value}</p>
          </div>
        ))}
      </div>
      <p className="mt-3 text-xs leading-5 text-ink/50">
        观察池门槛 {status.candidate_min_opportunity_score} 分，模拟开单门槛 {status.paper_min_opportunity_score} 分；价格不是逐秒行情。
      </p>
    </section>
  );
}
