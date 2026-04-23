import {StrictMode} from 'react';
import {createRoot} from 'react-dom/client';
import App from './App.tsx';
import { AppStateProvider } from './lib/app-state.tsx';
import './index.css';

// Suppress resize observer loop errors
const originalError = console.error;
console.error = (...args) => {
  if (args[0] && typeof args[0] === 'string' && (args[0].includes('ResizeObserver loop') || args[0].includes('ResizeObserver'))) {
    return;
  }
  originalError.call(console, ...args);
};

window.addEventListener('error', (e) => {
  if (e.message.includes('ResizeObserver loop')) {
    e.preventDefault();
    e.stopImmediatePropagation();
  }
});

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AppStateProvider>
      <App />
    </AppStateProvider>
  </StrictMode>,
);
