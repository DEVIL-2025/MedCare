import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { api } from '../api/client';
import { useWebSocket } from '../api/websocket';

const ControlTowerContext = createContext();

export function ControlTowerProvider({ children }) {
  const [selectedWarehouse, setSelectedWarehouse] = useState('All');
  const [warehouses, setWarehouses] = useState([]);
  const [activeAlertCount, setActiveAlertCount] = useState(0);
  const [refreshKey, setRefreshKey] = useState(0);

  const triggerRefresh = useCallback(() => {
    setRefreshKey((k) => k + 1);
  }, []);

  const loadGlobalMetadata = useCallback(async () => {
    try {
      const [whs, alertsRes] = await Promise.all([
        api.getWarehouses(),
        api.getAlerts()
      ]);
      
      const whList = Array.isArray(whs) ? whs : (whs?.overview || []);
      setWarehouses(whList);

      if (alertsRes && alertsRes.counts) {
        setActiveAlertCount(alertsRes.counts.total || 0);
      }
    } catch (err) {
      console.warn('Failed to load global control tower metadata:', err);
    }
  }, []);

  useEffect(() => {
    loadGlobalMetadata();
  }, [loadGlobalMetadata, refreshKey]);

  // Listen to WebSocket events to update global alert count and trigger refreshes
  useWebSocket((msg) => {
    if (
      msg.event === 'INVENTORY_TRANSACTION' ||
      msg.event === 'TRANSFER_EXECUTED' ||
      msg.event === 'ALERT_STATUS_UPDATED' ||
      msg.event === 'ALERT_CREATED' ||
      msg.event === 'ALERT_ACTION_PROCESSED' ||
      msg.event === 'PRODUCT_ARCHIVED' ||
      msg.event === 'PRODUCT_CREATED' ||
      msg.event === 'PRODUCT_DELETED' ||
      msg.event === 'WAREHOUSE_DECOMMISSIONED' ||
      msg.event === 'WAREHOUSE_CREATED' ||
      msg.event === 'WAREHOUSE_UPDATED' ||
      msg.event === 'REPLENISHMENT_UPDATED'
    ) {
      loadGlobalMetadata();
      triggerRefresh();
    }
  });

  return (
    <ControlTowerContext.Provider
      value={{
        selectedWarehouse,
        setSelectedWarehouse,
        warehouses,
        activeAlertCount,
        refreshKey,
        triggerRefresh,
        loadGlobalMetadata,
      }}
    >
      {children}
    </ControlTowerContext.Provider>
  );
}

export function useControlTower() {
  const context = useContext(ControlTowerContext);
  if (!context) {
    throw new Error('useControlTower must be used within a ControlTowerProvider');
  }
  return context;
}
