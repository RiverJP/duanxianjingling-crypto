import Link from "next/link";
import { Activity, RefreshCw } from "lucide-react";

export function Header() {
  return (
    <header className="border-b border-ink/10 bg-white">
      <div className="mx-auto flex max-w-7xl flex-col gap-3 px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
        <Link href="/" className="flex items-center gap-3 font-semibold">
          <span className="grid h-9 w-9 place-items-center rounded bg-mint text-white">
            <Activity size={19} />
          </span>
          短线精灵
        </Link>
        <div className="flex w-full flex-wrap items-center justify-between gap-3 text-sm text-ink/60 sm:w-auto sm:justify-start sm:gap-5">
          <Link href="/paper" className="font-medium hover:text-ink">
            模拟观察
          </Link>
          <Link href="/backtest" className="font-medium hover:text-ink">
            回测
          </Link>
          <div className="flex items-center gap-2">
            <RefreshCw size={16} />
            15分钟自动刷新
          </div>
        </div>
      </div>
    </header>
  );
}
