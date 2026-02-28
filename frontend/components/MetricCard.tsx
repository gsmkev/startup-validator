export function MetricCard({
  label,
  value,
  source,
}: {
  label: string;
  value: number;
  source: string;
}) {
  return (
    <div className="border border-gray-200 rounded-xl p-4 bg-white text-center">
      <p className="text-2xl font-bold text-gray-900">{value}</p>
      <p className="text-xs font-medium text-gray-700 mt-1">{label}</p>
      <p className="text-xs text-gray-400 mt-0.5">{source}</p>
    </div>
  );
}
