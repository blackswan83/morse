import { useEffect } from 'react';
import { useAppStore } from './store';
import { Welcome } from './components/Welcome';
import { Chat } from './components/Chat';
import { LoadingScreen } from './components/LoadingScreen';

function App() {
  const { initialize, isLoading, isAuthenticated } = useAppStore();

  useEffect(() => {
    initialize();
  }, [initialize]);

  if (isLoading) {
    return <LoadingScreen />;
  }

  if (!isAuthenticated) {
    return <Welcome />;
  }

  return <Chat />;
}

export default App;
