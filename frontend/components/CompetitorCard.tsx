import { Competitor } from "@/lib/api";

export function CompetitorCard({ competitor }: { competitor: Competitor }) {
  return (
    <div className="border border-gray-200 rounded-lg p-3 bg-white flex flex-col gap-1">
      <div className="flex items-center justify-between">
        <span className="font-medium text-sm text-gray-900 truncate">{competitor.name}</span>
        <span className="text-xs text-gray-400 ml-2 shrink-0">{competitor.source}</span>
      </div>
      {competitor.ruc && (
        <span className="text-xs text-gray-500">RUC: {competitor.ruc}</span>
      )}
      {competitor.detail && (
        <span className="text-xs text-gray-600 line-clamp-2">{competitor.detail}</span>
      )}
    </div>
  );
}
