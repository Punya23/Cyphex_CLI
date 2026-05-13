import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import type { MetricState } from '../../types';

export function RiskChart({ data }: { data: MetricState['riskHistory'] }) {
  return (
    <div style={{ width: '100%', height: '100%', minHeight: '180px', position: 'relative' }}>
      <div style={{
        position: 'absolute',
        top: 10, right: 10,
        fontFamily: 'var(--font-mono)',
        fontSize: '0.58rem',
        color: 'var(--neon-green)',
        opacity: 0.5,
        pointerEvents: 'none',
        zIndex: 1,
        letterSpacing: '1px',
      }}>
        [ DATA_STREAM: ACTIVE ]<br/>
        [ TRACE_NODE: 0x4f2 ]
      </div>
      <ResponsiveContainer>
        <AreaChart data={data} margin={{ top: 20, right: 30, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="riskGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor="#39ff14" stopOpacity={0.28}/>
              <stop offset="95%" stopColor="#39ff14" stopOpacity={0}/>
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(124,58,237,0.08)" vertical={false} />
          <XAxis dataKey="time" hide />
          <YAxis domain={[0, 100]} hide />
          <Tooltip
            contentStyle={{
              backgroundColor: 'rgba(7,0,16,0.95)',
              border: '1px solid rgba(57,255,20,0.3)',
              borderRadius: '8px',
              color: '#39ff14',
              fontFamily: 'var(--font-mono)',
              fontSize: '0.68rem',
            }}
            itemStyle={{ color: '#39ff14' }}
          />
          <Area
            type="monotone"
            dataKey="risk"
            stroke="#39ff14"
            strokeWidth={2}
            fillOpacity={1}
            fill="url(#riskGrad)"
            animationDuration={1000}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
