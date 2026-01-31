import { useEffect, useState } from 'react';
import { tradingApi } from '../services/api';
import { X, TrendingUp, TrendingDown, AlertCircle } from 'lucide-react';
import clsx from 'clsx';

interface Position {
  symbol: string;
  side: string;
  quantity: number;
  entry_price: number;
  current_price: number | null;
  unrealized_pnl: number;
  realized_pnl: number;
  leverage: number;
  stop_loss: number | null;
  take_profit: number | null;
  liquidation_price: number | null;
  opened_at: string;
}

export default function Positions() {
  const [positions, setPositions] = useState<Position[]>([]);
  const [loading, setLoading] = useState(true);
  const [closing, setClosing] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadPositions();
    const interval = setInterval(loadPositions, 5000);
    return () => clearInterval(interval);
  }, []);

  const loadPositions = async () => {
    try {
      const response = await tradingApi.getPositions();
      setPositions(response.data);
      setError(null);
    } catch (err) {
      setError('Failed to load positions');
    } finally {
      setLoading(false);
    }
  };

  const closePosition = async (symbol: string) => {
    if (!confirm(`Are you sure you want to close the ${symbol} position?`)) {
      return;
    }

    setClosing(symbol);
    try {
      await tradingApi.closePosition(symbol);
      await loadPositions();
    } catch (err) {
      setError('Failed to close position');
    } finally {
      setClosing(null);
    }
  };

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
    }).format(value);
  };

  const formatPercent = (pnl: number, entryPrice: number, quantity: number) => {
    const notional = entryPrice * quantity;
    if (notional === 0) return '0.00%';
    const percent = (pnl / notional) * 100;
    return `${percent >= 0 ? '+' : ''}${percent.toFixed(2)}%`;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold dark:text-white">Positions</h1>
        <div className="text-sm text-gray-500">
          {positions.length} open position{positions.length !== 1 ? 's' : ''}
        </div>
      </div>

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2 text-red-700">
          <AlertCircle className="h-5 w-5" />
          {error}
        </div>
      )}

      {positions.length === 0 ? (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-12 text-center">
          <div className="text-gray-400 mb-2">No open positions</div>
          <p className="text-sm text-gray-500">
            Positions will appear here when the trading engine opens them.
          </p>
        </div>
      ) : (
        <div className="grid gap-4">
          {positions.map((position) => (
            <div
              key={position.symbol}
              className="bg-white dark:bg-gray-800 rounded-lg shadow p-6"
            >
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className={clsx(
                    'w-10 h-10 rounded-full flex items-center justify-center',
                    position.side === 'long' ? 'bg-green-100' : 'bg-red-100'
                  )}>
                    {position.side === 'long' ? (
                      <TrendingUp className="h-5 w-5 text-green-600" />
                    ) : (
                      <TrendingDown className="h-5 w-5 text-red-600" />
                    )}
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold dark:text-white">{position.symbol}</h3>
                    <span className={clsx(
                      'text-sm font-medium',
                      position.side === 'long' ? 'text-green-600' : 'text-red-600'
                    )}>
                      {position.side.toUpperCase()} {position.leverage}x
                    </span>
                  </div>
                </div>

                <button
                  onClick={() => closePosition(position.symbol)}
                  disabled={closing === position.symbol}
                  className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors disabled:opacity-50"
                >
                  {closing === position.symbol ? (
                    <div className="animate-spin h-5 w-5 border-2 border-red-500 border-t-transparent rounded-full" />
                  ) : (
                    <X className="h-5 w-5" />
                  )}
                </button>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <div className="text-sm text-gray-500 mb-1">Quantity</div>
                  <div className="font-medium dark:text-white">{position.quantity.toFixed(4)}</div>
                </div>
                <div>
                  <div className="text-sm text-gray-500 mb-1">Entry Price</div>
                  <div className="font-medium dark:text-white">{formatCurrency(position.entry_price)}</div>
                </div>
                <div>
                  <div className="text-sm text-gray-500 mb-1">Current Price</div>
                  <div className="font-medium dark:text-white">
                    {position.current_price ? formatCurrency(position.current_price) : '-'}
                  </div>
                </div>
                <div>
                  <div className="text-sm text-gray-500 mb-1">Unrealized P&L</div>
                  <div className={clsx(
                    'font-medium',
                    position.unrealized_pnl >= 0 ? 'text-green-600' : 'text-red-600'
                  )}>
                    {formatCurrency(position.unrealized_pnl)}
                    <span className="text-sm ml-1">
                      ({formatPercent(position.unrealized_pnl, position.entry_price, position.quantity)})
                    </span>
                  </div>
                </div>
              </div>

              {(position.stop_loss || position.take_profit || position.liquidation_price) && (
                <div className="mt-4 pt-4 border-t border-gray-100 dark:border-gray-700 grid grid-cols-3 gap-4">
                  {position.stop_loss && (
                    <div>
                      <div className="text-sm text-gray-500 mb-1">Stop Loss</div>
                      <div className="font-medium text-red-600">{formatCurrency(position.stop_loss)}</div>
                    </div>
                  )}
                  {position.take_profit && (
                    <div>
                      <div className="text-sm text-gray-500 mb-1">Take Profit</div>
                      <div className="font-medium text-green-600">{formatCurrency(position.take_profit)}</div>
                    </div>
                  )}
                  {position.liquidation_price && (
                    <div>
                      <div className="text-sm text-gray-500 mb-1">Liquidation</div>
                      <div className="font-medium text-orange-600">{formatCurrency(position.liquidation_price)}</div>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
