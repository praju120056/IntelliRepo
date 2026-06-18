import React from 'react';
import { Layout } from './components/Layout/Layout';
import { HomeView } from './components/HomeView/HomeView';
import { GraphView } from './components/GraphView/GraphView';
import { SearchView } from './components/SearchView/SearchView';
import { TreeView } from './components/TreeView/TreeView';
import { useRepoStore } from './store/repoStore';

function App() {
  const { activeView } = useRepoStore();

  const renderView = () => {
    switch (activeView.type) {
      case 'home':
        return <HomeView />;
      case 'tree':
        return <TreeView />;
      case 'deps':
        return <GraphView mode="deps" />;
      case 'calls':
        return <GraphView mode="calls" />;
      case 'search':
        return <SearchView />;
      default:
        return <HomeView />;
    }
  };

  return (
    <Layout>
      {renderView()}
    </Layout>
  );
}

export default App;
