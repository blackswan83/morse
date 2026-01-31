import { useEffect, useState } from 'react';
import { tradingApi } from '../services/api';
import { useAuthStore } from '../store/auth';
import { Save, AlertCircle, Check, Shield, Activity, DollarSign } from 'lucide-react';

interface Settings {
  environment: string;
  exchange: {
    name: string;
    testnet: boolean;
  };
  symbols: {
    primary: string[];
    secondary: string[];
  };
  timeframes: {
    macro_primary: string;
    meso_primary: string;
    micro_primary: string;
  };
  risk: {
    max_leverage: number;
    single_position_risk_pct: number;
    total_portfolio_heat_pct: number;
    daily_loss_limit_pct: number;
  };
}

export default function Settings() {
  const { user } = useAuthStore();
  const [settings, setSettings] = useState<Settings | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [passwordForm, setPasswordForm] = useState({
    currentPassword: '',
    newPassword: '',
    confirmPassword: '',
  });
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [passwordSuccess, setPasswordSuccess] = useState(false);

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      const response = await tradingApi.getSettings();
      setSettings(response.data);
    } catch (err) {
      setError('Failed to load settings');
    } finally {
      setLoading(false);
    }
  };

  const handlePasswordChange = async (e: React.FormEvent) => {
    e.preventDefault();
    setPasswordError(null);
    setPasswordSuccess(false);

    if (passwordForm.newPassword !== passwordForm.confirmPassword) {
      setPasswordError('New passwords do not match');
      return;
    }

    if (passwordForm.newPassword.length < 8) {
      setPasswordError('Password must be at least 8 characters');
      return;
    }

    try {
      const response = await fetch('/api/auth/change-password', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${localStorage.getItem('mortar-auth') ? JSON.parse(localStorage.getItem('mortar-auth')!).state?.token : ''}`,
        },
        body: JSON.stringify({
          current_password: passwordForm.currentPassword,
          new_password: passwordForm.newPassword,
        }),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to change password');
      }

      setPasswordSuccess(true);
      setPasswordForm({
        currentPassword: '',
        newPassword: '',
        confirmPassword: '',
      });
    } catch (err: any) {
      setPasswordError(err.message);
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
    <div className="space-y-6 max-w-4xl">
      <h1 className="text-2xl font-bold dark:text-white">Settings</h1>

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2 text-red-700">
          <AlertCircle className="h-5 w-5" />
          {error}
        </div>
      )}

      {/* System Configuration */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
        <div className="p-6 border-b border-gray-200 dark:border-gray-700">
          <h2 className="text-lg font-semibold flex items-center gap-2 dark:text-white">
            <Activity className="h-5 w-5" />
            System Configuration
          </h2>
        </div>
        <div className="p-6 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-500 mb-1">Environment</label>
              <div className="font-medium dark:text-white capitalize">{settings?.environment}</div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-500 mb-1">Exchange</label>
              <div className="font-medium dark:text-white">
                {settings?.exchange.name} {settings?.exchange.testnet && '(Testnet)'}
              </div>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-500 mb-1">Primary Symbols</label>
            <div className="flex flex-wrap gap-2">
              {settings?.symbols.primary.map((symbol) => (
                <span key={symbol} className="px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm">
                  {symbol}
                </span>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-500 mb-1">Secondary Symbols</label>
            <div className="flex flex-wrap gap-2">
              {settings?.symbols.secondary.map((symbol) => (
                <span key={symbol} className="px-3 py-1 bg-gray-100 text-gray-800 rounded-full text-sm">
                  {symbol}
                </span>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-500 mb-1">Macro Timeframe</label>
              <div className="font-medium dark:text-white">{settings?.timeframes.macro_primary}</div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-500 mb-1">Meso Timeframe</label>
              <div className="font-medium dark:text-white">{settings?.timeframes.meso_primary}</div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-500 mb-1">Micro Timeframe</label>
              <div className="font-medium dark:text-white">{settings?.timeframes.micro_primary}</div>
            </div>
          </div>
        </div>
      </div>

      {/* Risk Settings */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
        <div className="p-6 border-b border-gray-200 dark:border-gray-700">
          <h2 className="text-lg font-semibold flex items-center gap-2 dark:text-white">
            <Shield className="h-5 w-5" />
            Risk Management
          </h2>
        </div>
        <div className="p-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="p-4 bg-gray-50 dark:bg-gray-700 rounded-lg">
              <div className="text-sm text-gray-500 mb-1">Max Leverage</div>
              <div className="text-2xl font-bold text-blue-600">{settings?.risk.max_leverage}x</div>
            </div>
            <div className="p-4 bg-gray-50 dark:bg-gray-700 rounded-lg">
              <div className="text-sm text-gray-500 mb-1">Position Risk</div>
              <div className="text-2xl font-bold text-blue-600">{settings?.risk.single_position_risk_pct}%</div>
            </div>
            <div className="p-4 bg-gray-50 dark:bg-gray-700 rounded-lg">
              <div className="text-sm text-gray-500 mb-1">Portfolio Heat</div>
              <div className="text-2xl font-bold text-blue-600">{settings?.risk.total_portfolio_heat_pct}%</div>
            </div>
            <div className="p-4 bg-gray-50 dark:bg-gray-700 rounded-lg">
              <div className="text-sm text-gray-500 mb-1">Daily Loss Limit</div>
              <div className="text-2xl font-bold text-red-600">{settings?.risk.daily_loss_limit_pct}%</div>
            </div>
          </div>
        </div>
      </div>

      {/* User Profile & Password */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
        <div className="p-6 border-b border-gray-200 dark:border-gray-700">
          <h2 className="text-lg font-semibold flex items-center gap-2 dark:text-white">
            <DollarSign className="h-5 w-5" />
            Account Settings
          </h2>
        </div>
        <div className="p-6">
          <div className="mb-6">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-500 mb-1">Username</label>
                <div className="font-medium dark:text-white">{user?.username}</div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-500 mb-1">Role</label>
                <div className="font-medium dark:text-white capitalize">{user?.role}</div>
              </div>
            </div>
          </div>

          <div className="border-t border-gray-200 dark:border-gray-700 pt-6">
            <h3 className="text-md font-semibold mb-4 dark:text-white">Change Password</h3>

            {passwordError && (
              <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2 text-red-700">
                <AlertCircle className="h-5 w-5" />
                {passwordError}
              </div>
            )}

            {passwordSuccess && (
              <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-lg flex items-center gap-2 text-green-700">
                <Check className="h-5 w-5" />
                Password changed successfully
              </div>
            )}

            <form onSubmit={handlePasswordChange} className="space-y-4 max-w-md">
              <div>
                <label className="block text-sm font-medium mb-1 dark:text-gray-300">
                  Current Password
                </label>
                <input
                  type="password"
                  value={passwordForm.currentPassword}
                  onChange={(e) => setPasswordForm({ ...passwordForm, currentPassword: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg dark:bg-gray-700 dark:border-gray-600"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1 dark:text-gray-300">
                  New Password
                </label>
                <input
                  type="password"
                  value={passwordForm.newPassword}
                  onChange={(e) => setPasswordForm({ ...passwordForm, newPassword: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg dark:bg-gray-700 dark:border-gray-600"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1 dark:text-gray-300">
                  Confirm New Password
                </label>
                <input
                  type="password"
                  value={passwordForm.confirmPassword}
                  onChange={(e) => setPasswordForm({ ...passwordForm, confirmPassword: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg dark:bg-gray-700 dark:border-gray-600"
                  required
                />
              </div>
              <button
                type="submit"
                className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors"
              >
                <Save className="h-4 w-4" />
                Change Password
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
