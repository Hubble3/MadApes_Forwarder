interface StatCardProps {
  label: string;
  value: string | number;
  subtext?: string;
  color?: 'green' | 'red' | 'blue' | 'yellow' | 'default';
}

const colorMap = {
  green: 'text-green-400',
  red: 'text-red-400',
  blue: 'text-blue-400',
  yellow: 'text-yellow-400',
  default: 'text-white',
};

export default function StatCard({ label, value, subtext, color = 'default' }: StatCardProps) {
  return (
    <div className="bg-[#1e293b] rounded-lg p-4 border border-[#334155]">
      <p className="text-xs text-slate-400 uppercase tracking-wide">{label}</p>
      <p className={`text-2xl font-bold mt-1 ${colorMap[color]}`}>{value}</p>
      {subtext && <p className="text-xs text-slate-500 mt-1">{subtext}</p>}
    </div>
  );
}
