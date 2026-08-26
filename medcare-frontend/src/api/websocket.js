import { useState, useEffect, useRef, useCallback } from 'react';

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/api/ws';

export function useWebSocket(onMessage) {
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState(null);
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  
  // Keep a fresh reference to onMessage without triggering effect re-runs
  const onMessageRef = useRef(onMessage);
  useEffect(() => {
    onMessageRef.current = onMessage;
  }, [onMessage]);

  useEffect(() => {
    let isComponentMounted = true;

    function connect() {
      // Prevent duplicate connections if one is already open or connecting
      if (
        wsRef.current &&
        (wsRef.current.readyState === WebSocket.OPEN ||
          wsRef.current.readyState === WebSocket.CONNECTING)
      ) {
        return;
      }

      try {
        const ws = new WebSocket(WS_URL);
        wsRef.current = ws;

        ws.onopen = () => {
          if (isComponentMounted) {
            setIsConnected(true);
          }
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (isComponentMounted) {
              setLastMessage(data);
            }
            if (onMessageRef.current) {
              onMessageRef.current(data);
            }
          } catch (err) {
            console.error('Failed to parse WebSocket message:', err);
          }
        };

        ws.onclose = () => {
          if (!isComponentMounted) return;
          setIsConnected(false);
          wsRef.current = null;

          // Schedule reconnect safely
          if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
          reconnectTimeoutRef.current = setTimeout(connect, 3000);
        };

        ws.onerror = (err) => {
          console.warn('WebSocket connection error (will retry):', err);
          // Let onclose handle the reconnect naturally; don't call close() manually here
        };
      } catch (err) {
        console.warn('WebSocket setup error:', err);
        if (isComponentMounted) {
          if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
          reconnectTimeoutRef.current = setTimeout(connect, 3000);
        }
      }
    }

    connect();

return () => {
      isComponentMounted = false;

      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }

      if (wsRef.current) {
        const ws = wsRef.current;

        // Wipe handlers to prevent unmount side-effects or reconnect loops
        ws.onopen = null;
        ws.onmessage = null;
        ws.onerror = null;
        ws.onclose = null;

        // Gracefully handle closing based on connection state
        if (ws.readyState === WebSocket.OPEN) {
          ws.close();
        } else if (ws.readyState === WebSocket.CONNECTING) {
          // Wait for connection to open before calling close to prevent browser warnings
          ws.onopen = () => ws.close();
        }

        wsRef.current = null;
      }
    };
  }, []);

  const sendMessage = useCallback((msg) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(typeof msg === 'string' ? msg : JSON.stringify(msg));
    }
  }, []);

  return { isConnected, lastMessage, sendMessage };
}