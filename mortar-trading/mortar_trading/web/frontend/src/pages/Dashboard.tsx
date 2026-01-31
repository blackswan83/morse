import { useEffect, useState } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { Activity, TrendingUp, TrendingDown, AlertTriangle, DollarSign, Percent, BarChart3 } from 'lucide-react';
import { tradingApi } from '../services/api';
import { useAuthStore } from '../store/auth';
import clsx from 'clsx';

interface StatusData {
  running: boolean;
  environment: string;
  master_bias: {
    direction: string;
    confidence: string;
    time_horizon: string;
  };
}

interface AccountData {
  balance: number;
  available_balance: number;
  equity: number;
  unrealized_pnl: number;
  realized_pnl_today: number;
}

interface RiskData {
  circuit_breaker_active: boolean;
  daily_pnl: number;
  weekly_pnl: number;
  monthly_pnl: number;
  regime_adjustment: number;
}

interface PerformanceData {
  total_trades: number;
  win_rate: number;
  total_pnl: number;
  profit_factor: number;
}

interface Position {
  symbol: string;
  side: string;
  quantity: number;
  entry_price: number;
  unrealized_pnl: number;
}

export default function Dashboard() {
  const { token } = useAuthStore();
  const [status, setStatus] = useState<StatusData | null>(null);
  const [account, setAccount] = useState<AccountData | null>(null);
  const [risk, setRisk] = useState<RiskData | null>(null);
  const [performance, setPerformance] = useState<PerformanceData | null>(null);
  const [positions, setPositions] = useState<Position[]>([]);
  const [loading, setLoading] = useState(true);

  const [masterDirection, setMasterDirection] = useState('neutral');
  const [masterConfidence, setMasterConfidence] = useState('medium');

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 5000);
    return () => clearInterval(interval);
  }, []);

  const loadData = async () => {
    try {
      const [statusRes, accountRes, riskRes, perfRes, posRes] = await Promise.all([
        tradingApi.getStatus(),
        tradingApi.getAccount(),
        tradingApi.getRiskStatus(),
        tradingApi.getPerformance(),
        tradingApi.getPositions(),
      ]);

      setStatus(statusRes.data);
      setAccount(accountRes.data);
      setRisk(riskRes.data);
      setPerformance(perfRes.data);
      setPositions(posRes.data);

      if (statusRes.data.master_bias) {
        setMasterDirection(statusRes.data.master_bias.direction);
        setMasterConfidence(statusRes.data.master_bias.confidence);
      }
    } catch (error) {
      console.error('Failed to load data:', error);
    } finally {
      setLoading(false);
    }
  };

  const updateMasterInput = async () => {
    try {
      await tradingApi.updateMasterInput(masterDirection, masterConfidence);
      loadData();
    } catch (error) {
      console.error('Failed to update master input:', error);
    }
  };

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
    }).format(value);
  };

  const formatPercent = (value: number) => {
    return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Equity"
          value={formatCurrency(account?.equity || 0)}
          icon={<DollarSign className="h-6 w-6" />}
          trend={account?.unrealized_pnl || 0}
        />
        <StatCard
          title="Daily P&L"
          value={formatCurrency(risk?.daily_pnl || 0)}
          icon={<TrendingUp className="h-6 w-6" />}
          trend={risk?.daily_pnl || 0}
        />
        <StatCard
          title="Win Rate"
          value={formatPercent((performance?.win_rate || 0) * 100)}
          icon={<Percent className="h-6 w-6" />}
        />
        <StatCard
          title="Open Positions"
          value={positions.length.toString()}
          icon={<BarChart3 className="h-6 w-6" />}
        />
      </div>

      {/* Status and Master Input */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* System Status */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <Activity className="h-5 w-5" />
            System Status
          </h3>
          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-gray-600 dark:text-gray-400">Engine</span>
              <span className={clsx(
                'px-2 py-1 rounded text-sm font-medium',
                status?.running ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
              )}>
                {status?.running ? 'Running' : 'Stopped'}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-600 dark:text-gray-400">Environment</span>
              <span className="font-medium">{status?.environment}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-600 dark:text-gray-400">Circuit Breaker</span>
              <span className={clsx(
                'px-2 py-1 rounded text-sm font-medium',
                risk?.circuit_breaker_active ? 'bg-red-100 text-red-800' : 'bg-green-100 text-green-800'
              )}>
                {risk?.circuit_breaker_active ? 'Active' : 'Normal'}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-600 dark:text-gray-400">Regime Adjustment</span>
              <span className="font-medium">{((risk?.regime_adjustment || 1) * 100).toFixed(0)}%</span>
            </div>
          </div>
        </div>

        {/* Master Input Control */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold mb-4">Master Input Control</h3>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Direction
              </label>
              <select
                value={masterDirection}
                onChange={(e) => setMasterDirection(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600"
              >
                <option value="strong_bear">Strong Bear</option>
                <option value="bear">Bear</option>
                <option value="neutral">Neutral</option>
                <option value="bull">Bull</option>
                <option value="strong_bull">Strong Bull</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Confidence
              </label>
              <select
                value={masterConfidence}
                onChange={(e) => setMasterConfidence(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600"
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
              </select>
            </div>
            <button
              onClick={updateMasterInput}
              className="w-full bg-blue-600 text-white py-2 px-4 rounded-lg hover:bg-blue-700 transition-colors"
            >
              Update Master Input
            </button>
          </div>
        </div>
      </div>

      {/* Positions Table */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
        <div className="p-6 border-b border-gray-200 dark:border-gray-700">
          <h3 className="text-lg font-semibold">Open Positions</h3>
        </div>
        <div className="overflow-x-auto">
          {positions.length === 0 ? (
            <div className="p-8 text-center text-gray-500">
              No open positions
            </div>
          ) : (
            <table className="w-full">
              <thead className="bg-gray-50 dark:bg-gray-700">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Symbol
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Side
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Quantity
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Entry Price
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Unrealized P&L
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                {positions.map((position) => (
                  <tr key={position.symbol}>
                    <td className="px-6 py-4 whitespace-nowrap font-medium">
                      {position.symbol}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={clsx(
                        'px-2 py-1 rounded text-sm font-medium',
                        position.side === 'long' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                      )}>
                        {position.side.toUpperCase()}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {position.quantity.toFixed(4)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {formatCurrency(position.entry_price)}
                    </td>
                    <td className={clsx(
                      'px-6 py-4 whitespace-nowrap font-medium',
                      position.unrealized_pnl >= 0 ? 'text-green-600' : 'text-red-600'
                    )}>
                      {formatCurrency(position.unrealized_pnl)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Risk Warning */}
      {risk?.circuit_breaker_active && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center gap-3">
          <AlertTriangle className="h-6 w-6 text-red-600" />
          <div>
            <h4 className="font-semibold text-red-800">Circuit Breaker Active</h4>
            <p className="text-red-600 text-sm">
              Trading is paused due to loss limits being reached.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

function StatCard({
  title,
  value,
  icon,
  trend,
}: {
  title: string;
  value: string;
  icon: React.ReactNode;
  trend?: number;
}) {
  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-600 dark:text-gray-400">{title}</p>
          <p className="text-2xl font-bold mt-1">{value}</p>
          {trend !== undefined && (
            <p className={clsx(
              'text-sm mt-1 flex items-center gap-1',
              trend >= 0 ? 'text-green-600' : 'text-red-600'
            )}>
              {trend >= 0 ? <TrendingUp className="h-4 w-4" /> : <TrendingDown className="h-4 w-4" />}
              {trend >= 0 ? '+' : ''}{trend.toFixed(2)}
            </p>
          )}
        </div>
        <div className="text-gray-400">{icon}</div>
      </div>
    </div>
  );
}
