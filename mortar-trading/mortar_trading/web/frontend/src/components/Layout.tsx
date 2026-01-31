import { useState, useEffect } from 'react';
import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/auth';
import { tradingWs } from '../services/api';
import {
  Activity,
  LayoutDashboard,
  Briefcase,
  FileText,
  Settings,
  LogOut,
  Menu,
  X,
  Wifi,
  WifiOff,
  Bell,
  User,
} from 'lucide-react';
import clsx from 'clsx';

export default function Layout() {
  const navigate = useNavigate();
  const { user, token, logout, fetchUser } = useAuthStore();
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [wsConnected, setWsConnected] = useState(false);
  const [notifications, setNotifications] = useState<string[]>([]);

  useEffect(() => {
    fetchUser();
  }, []);

  useEffect(() => {
    if (token) {
      tradingWs.connect(token);

      tradingWs.on('connected', () => setWsConnected(true));
      tradingWs.on('disconnected', () => setWsConnected(false));

      // Listen for important events
      tradingWs.on('event', (data) => {
        if (['order_filled', 'position_opened', 'position_closed', 'risk_limit_breach'].includes(data.event_type)) {
          setNotifications((prev) => [
            `${data.event_type}: ${data.symbol || 'System'}`,
            ...prev.slice(0, 4),
          ]);
        }
      });

      return () => {
        tradingWs.disconnect();
      };
    }
  }, [token]);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const navItems = [
    { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
    { to: '/positions', icon: Briefcase, label: 'Positions' },
    { to: '/orders', icon: FileText, label: 'Orders' },
    { to: '/settings', icon: Settings, label: 'Settings' },
  ];

  return (
    <div className="min-h-screen bg-gray-100 dark:bg-gray-900">
      {/* Sidebar */}
      <aside
        className={clsx(
          'fixed top-0 left-0 z-40 h-screen transition-transform bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700',
          sidebarOpen ? 'w-64 translate-x-0' : 'w-64 -translate-x-full md:w-20 md:translate-x-0'
        )}
      >
        {/* Logo */}
        <div className="flex items-center justify-between h-16 px-4 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-blue-600 rounded-lg flex items-center justify-center">
              <Activity className="h-6 w-6 text-white" />
            </div>
            {sidebarOpen && (
              <span className="font-bold text-lg dark:text-white">Mortar</span>
            )}
          </div>
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="md:hidden text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
          >
            {sidebarOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-4 space-y-2">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                clsx(
                  'flex items-center gap-3 px-4 py-3 rounded-lg transition-colors',
                  isActive
                    ? 'bg-blue-50 text-blue-600 dark:bg-blue-900/50 dark:text-blue-400'
                    : 'text-gray-600 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-700'
                )
              }
            >
              <item.icon className="h-5 w-5" />
              {sidebarOpen && <span>{item.label}</span>}
            </NavLink>
          ))}
        </nav>

        {/* User section */}
        <div className="p-4 border-t border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-3 px-4 py-2">
            <div className="w-8 h-8 bg-gray-200 dark:bg-gray-700 rounded-full flex items-center justify-center">
              <User className="h-4 w-4 text-gray-500" />
            </div>
            {sidebarOpen && (
              <div className="flex-1">
                <p className="text-sm font-medium dark:text-white">{user?.username || 'User'}</p>
                <p className="text-xs text-gray-500">{user?.role || 'user'}</p>
              </div>
            )}
          </div>
          <button
            onClick={handleLogout}
            className="flex items-center gap-3 w-full px-4 py-3 mt-2 text-gray-600 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-700 rounded-lg transition-colors"
          >
            <LogOut className="h-5 w-5" />
            {sidebarOpen && <span>Logout</span>}
          </button>
        </div>
      </aside>

      {/* Main content */}
      <div className={clsx('transition-all', sidebarOpen ? 'md:ml-64' : 'md:ml-20')}>
        {/* Header */}
        <header className="sticky top-0 z-30 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center justify-between h-16 px-4">
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="hidden md:block text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
            >
              <Menu className="h-6 w-6" />
            </button>

            <div className="flex items-center gap-4">
              {/* Connection status */}
              <div className={clsx(
                'flex items-center gap-2 px-3 py-1 rounded-full text-sm',
                wsConnected ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
              )}>
                {wsConnected ? <Wifi className="h-4 w-4" /> : <WifiOff className="h-4 w-4" />}
                {wsConnected ? 'Connected' : 'Disconnected'}
              </div>

              {/* Notifications */}
              <div className="relative">
                <button className="p-2 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300">
                  <Bell className="h-5 w-5" />
                  {notifications.length > 0 && (
                    <span className="absolute top-0 right-0 w-4 h-4 bg-red-500 text-white text-xs rounded-full flex items-center justify-center">
                      {notifications.length}
                    </span>
                  )}
                </button>
              </div>
            </div>
          </div>
        </header>

        {/* Page content */}
        <main className="p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
