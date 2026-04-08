"use client";

interface ICRow {
  ticker: string;
  horizon: number;
  ic: number;
  ic_pvalue: number;
  ir: number | null;
  hit_rate: number;
  n_obs: number;
}

export function TearsheetTable({ data }: { data: ICRow[] }) {
  if (!data.length) {
    return <p className="text-xs text-zinc-600 font-mono">No validation data available.</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs font-mono">
        <thead>
          <tr className="border-b border-zinc-800 text-zinc-500">
            <th className="text-left py-2 pr-4">Ticker</th>
            <th className="text-right py-2 px-3">Horizon</th>
            <th className="text-right py-2 px-3">IC</th>
            <th className="text-right py-2 px-3">p-value</th>
            <th className="text-right py-2 px-3">IR</th>
            <th className="text-right py-2 px-3">Hit Rate</th>
            <th className="text-right py-2 pl-3">n_obs</th>
          </tr>
        </thead>
        <tbody>
          {data.map((row) => (
            <tr
              key={`${row.ticker}-${row.horizon}`}
              className="border-b border-zinc-800/50 hover:bg-zinc-900/50"
            >
              <td className="py-2 pr-4 text-zinc-200 font-semibold">{row.ticker}</td>
              <td className="text-right py-2 px-3 text-zinc-400">{row.horizon}d</td>
              <td
                className="text-right py-2 px-3 font-semibold"
                style={{
                  color:
                    row.ic > 0.05
                      ? "#34d399"
                      : row.ic < -0.05
                      ? "#f87171"
                      : "#a1a1aa",
                }}
              >
                {row.ic.toFixed(4)}
              </td>
              <td className="text-right py-2 px-3 text-zinc-400">
                {row.ic_pvalue.toFixed(4)}
              </td>
              <td className="text-right py-2 px-3 text-zinc-300">
                {row.ir != null ? row.ir.toFixed(2) : "—"}
              </td>
              <td className="text-right py-2 px-3 text-zinc-300">
                {(row.hit_rate * 100).toFixed(1)}%
              </td>
              <td className="text-right py-2 pl-3 text-zinc-500">{row.n_obs.toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
