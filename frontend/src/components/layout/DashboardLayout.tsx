import React from 'react';
import { Outlet } from 'react-router-dom';
import { Navbar } from './Navbar';
import { Footer } from './Footer';

export const DashboardLayout: React.FC<{ children?: React.ReactNode }> = ({ children }) => {
  return (
    <div className="app-container">
      <Navbar />
      <main className="main-content" id="main-content">
        {children || <Outlet />}
      </main>
      <Footer />
    </div>
  );
};
