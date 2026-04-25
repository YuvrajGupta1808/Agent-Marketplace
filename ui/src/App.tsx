/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { BrowserRouter, Route, Routes, useLocation } from "react-router-dom";
import { Navbar } from "./components/layout/Navbar";
import { Builder } from "./pages/Builder";
import { Dashboard } from "./pages/Dashboard";
import { Home as Marketplace } from "./pages/Home";
import { Landing } from "./pages/Landing";
import { Login } from "./pages/Login";
import { Register } from "./pages/Register";
import { SellerTest } from "./pages/SellerTest";
import { Wallet } from "./pages/Wallet";

function AppShell() {
  const location = useLocation();
  const isDashboardRoute = location.pathname === "/dashboard";

  return (
    <div className="h-screen overflow-hidden bg-white text-gray-900 flex flex-col font-sans">
      <Navbar />
      <main className={`flex min-h-0 flex-1 flex-col ${isDashboardRoute ? "overflow-hidden" : "overflow-y-auto"}`}>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/marketplace" element={<Marketplace />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/builder" element={<Builder />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/wallet" element={<Wallet />} />
          <Route path="/seller-test" element={<SellerTest />} />
        </Routes>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppShell />
    </BrowserRouter>
  );
}
