import React, { createContext, useContext, useState } from 'react';
import { Shop } from '../types';

interface ShopContextType {
  activeShop: Shop | null;
  setActiveShop: (shop: Shop | null) => void;
  shops: Shop[];
  setShops: (shops: Shop[]) => void;
}

const ShopContext = createContext<ShopContextType | undefined>(undefined);

export const ShopProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [activeShop, setActiveShop] = useState<Shop | null>(null);
  const [shops, setShops] = useState<Shop[]>([]);

  return (
    <ShopContext.Provider value={{ activeShop, setActiveShop, shops, setShops }}>
      {children}
    </ShopContext.Provider>
  );
};

export const useShop = () => {
  const context = useContext(ShopContext);
  if (!context) throw new Error('useShop must be used within ShopProvider');
  return context;
};
