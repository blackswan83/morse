import { useEffect, useState } from 'react';
import { tradingApi } from '../services/api';
import { X, Plus, AlertCircle } from 'lucide-react';
import clsx from 'clsx';

interface Order {
  order_id: string;
  symbol: string;
  side: string;
  order_type: string;
  quantity: number;
  price: number | null;
  filled_quantity: number;
  status: string;
  created_at: string;
}

export default function Orders() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [showNewOrder, setShowNewOrder] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // New order form
  const [newOrder, setNewOrder] = useState({
    symbol: 'BTCUSDT',
    side: 'buy',
    order_type: 'market',
    quantity: '',
    price: '',
  });
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    loadOrders();
    const interval = setInterval(loadOrders, 5000);
    return () => clearInterval(interval);
  }, []);

  const loadOrders = async () => {
    try {
      const response = await tradingApi.getOrders();
      setOrders(response.data);
      setError(null);
    } catch (err) {
      setError('Failed to load orders');
    } finally {
      setLoading(false);
    }
  };

  const cancelOrder = async (orderId: string) => {
    if (!confirm('Are you sure you want to cancel this order?')) return;

    try {
      await tradingApi.cancelOrder(orderId);
      await loadOrders();
    } catch (err) {
      setError('Failed to cancel order');
    }
  };

  const submitOrder = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      await tradingApi.createOrder({
        symbol: newOrder.symbol,
        side: newOrder.side,
        order_type: newOrder.order_type,
        quantity: parseFloat(newOrder.quantity),
        price: newOrder.price ? parseFloat(newOrder.price) : undefined,
      });
      setShowNewOrder(false);
      setNewOrder({
        symbol: 'BTCUSDT',
        side: 'buy',
        order_type: 'market',
        quantity: '',
        price: '',
      });
      await loadOrders();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to create order');
    } finally {
      setSubmitting(false);
    }
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleString();
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'filled':
        return 'bg-green-100 text-green-800';
      case 'open':
      case 'pending':
        return 'bg-blue-100 text-blue-800';
      case 'cancelled':
        return 'bg-gray-100 text-gray-800';
      case 'rejected':
        return 'bg-red-100 text-red-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
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
        <h1 className="text-2xl font-bold dark:text-white">Orders</h1>
        <button
          onClick={() => setShowNewOrder(true)}
          className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors"
        >
          <Plus className="h-5 w-5" />
          New Order
        </button>
      </div>

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2 text-red-700">
          <AlertCircle className="h-5 w-5" />
          {error}
        </div>
      )}

      {/* New Order Modal */}
      {showNewOrder && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-md p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold dark:text-white">New Order</h2>
              <button
                onClick={() => setShowNewOrder(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <form onSubmit={submitOrder} className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1 dark:text-gray-300">Symbol</label>
                <select
                  value={newOrder.symbol}
                  onChange={(e) => setNewOrder({ ...newOrder, symbol: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg dark:bg-gray-700 dark:border-gray-600"
                >
                  <option value="BTCUSDT">BTCUSDT</option>
                  <option value="ETHUSDT">ETHUSDT</option>
                  <option value="SOLUSDT">SOLUSDT</option>
                  <option value="BNBUSDT">BNBUSDT</option>
                </select>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-1 dark:text-gray-300">Side</label>
                  <select
                    value={newOrder.side}
                    onChange={(e) => setNewOrder({ ...newOrder, side: e.target.value })}
                    className="w-full px-3 py-2 border rounded-lg dark:bg-gray-700 dark:border-gray-600"
                  >
                    <option value="buy">Buy</option>
                    <option value="sell">Sell</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1 dark:text-gray-300">Type</label>
                  <select
                    value={newOrder.order_type}
                    onChange={(e) => setNewOrder({ ...newOrder, order_type: e.target.value })}
                    className="w-full px-3 py-2 border rounded-lg dark:bg-gray-700 dark:border-gray-600"
                  >
                    <option value="market">Market</option>
                    <option value="limit">Limit</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium mb-1 dark:text-gray-300">Quantity</label>
                <input
                  type="number"
                  step="0.0001"
                  value={newOrder.quantity}
                  onChange={(e) => setNewOrder({ ...newOrder, quantity: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg dark:bg-gray-700 dark:border-gray-600"
                  placeholder="0.001"
                  required
                />
              </div>

              {newOrder.order_type === 'limit' && (
                <div>
                  <label className="block text-sm font-medium mb-1 dark:text-gray-300">Price</label>
                  <input
                    type="number"
                    step="0.01"
                    value={newOrder.price}
                    onChange={(e) => setNewOrder({ ...newOrder, price: e.target.value })}
                    className="w-full px-3 py-2 border rounded-lg dark:bg-gray-700 dark:border-gray-600"
                    placeholder="50000.00"
                    required
                  />
                </div>
              )}

              <div className="flex gap-3 pt-4">
                <button
                  type="button"
                  onClick={() => setShowNewOrder(false)}
                  className="flex-1 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 dark:border-gray-600 dark:hover:bg-gray-700"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className={clsx(
                    'flex-1 px-4 py-2 rounded-lg text-white transition-colors',
                    newOrder.side === 'buy'
                      ? 'bg-green-600 hover:bg-green-700'
                      : 'bg-red-600 hover:bg-red-700',
                    submitting && 'opacity-50 cursor-not-allowed'
                  )}
                >
                  {submitting ? 'Submitting...' : `${newOrder.side === 'buy' ? 'Buy' : 'Sell'}`}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Orders Table */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow overflow-hidden">
        {orders.length === 0 ? (
          <div className="p-12 text-center text-gray-500">
            No orders yet
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50 dark:bg-gray-700">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Time</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Symbol</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Side</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Type</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Qty</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Price</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Filled</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                {orders.map((order) => (
                  <tr key={order.order_id}>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {formatDate(order.created_at)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap font-medium dark:text-white">
                      {order.symbol}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={clsx(
                        'px-2 py-1 rounded text-sm font-medium',
                        order.side === 'buy' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                      )}>
                        {order.side.toUpperCase()}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm dark:text-gray-300">
                      {order.order_type}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm dark:text-gray-300">
                      {order.quantity}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm dark:text-gray-300">
                      {order.price ? `$${order.price.toLocaleString()}` : 'Market'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm dark:text-gray-300">
                      {order.filled_quantity} / {order.quantity}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={clsx('px-2 py-1 rounded text-sm font-medium', getStatusColor(order.status))}>
                        {order.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {['open', 'pending'].includes(order.status) && (
                        <button
                          onClick={() => cancelOrder(order.order_id)}
                          className="text-red-600 hover:text-red-800"
                        >
                          Cancel
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
