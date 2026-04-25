import { Link, useLocation } from "react-router-dom";
import { cn } from "../../lib/utils";
import { Bot, Home, PenTool, LayoutDashboard, Key, UserPlus, Wallet as WalletIcon, User } from "lucide-react";
import { useAppState } from "../../lib/app-state";

export function Navbar() {
  const location = useLocation();
  const { currentUser, currentBuyer, logout } = useAppState();

  const navItems = [
    { name: "Marketplace", path: "/marketplace", icon: Home },
    { name: "Builder", path: "/builder", icon: PenTool },
    { name: "Wallet", path: "/wallet", icon: WalletIcon },
    { name: "Dashboard", path: "/dashboard", icon: LayoutDashboard },
  ];

  const authItems = currentUser
    ? []
    : [
        { name: "Login", path: "/login", icon: Key },
        { name: "Register", path: "/register", icon: UserPlus },
      ];

  const userBadge = currentUser?.display_name.slice(0, 2).toUpperCase() ?? "JD";
  const walletLabel = currentBuyer?.wallet.address
    ? `${currentBuyer.wallet.address.slice(0, 6)}...${currentBuyer.wallet.address.slice(-4)}`
    : "No buyer wallet";

  return (
    <nav className="sticky top-0 z-50 w-full border-b border-gray-100 bg-white backdrop-blur-md">
      <div className="flex items-center justify-between px-8 py-4">
        <div className="flex items-center gap-8">
          <Link to="/" className="flex items-center gap-2">
            <Bot size={24} className="text-black" />
            <h1 className="text-2xl font-black tracking-tighter uppercase text-black hidden sm:block">Agent.Flow</h1>
          </Link>
          
          <div className="hidden md:flex gap-6 text-sm font-medium text-gray-500 uppercase tracking-widest">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = location.pathname === item.path;
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={cn(
                    "flex items-center gap-2 transition-colors hover:text-black",
                    isActive ? "text-black" : "text-gray-500"
                  )}
                >
                  <Icon size={16} />
                  <span>{item.name}</span>
                </Link>
              );
            })}
          </div>
        </div>
        
        <div className="flex items-center gap-4">
          <div className="hidden lg:flex gap-6 text-sm font-medium text-gray-500 uppercase tracking-widest pr-4 border-r-2 border-dashed border-gray-200">
            {authItems.map((item) => {
              const Icon = item.icon;
              const isActive = location.pathname === item.path;
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={cn(
                    "flex items-center gap-2 transition-colors hover:text-black",
                    isActive ? "text-black" : "text-gray-500"
                  )}
                >
                  <Icon size={14} />
                  <span className="text-[10px] sm:text-xs font-black">{item.name}</span>
                </Link>
              );
            })}
          </div>
          {currentUser ? (
            <button
              onClick={logout}
              className="min-w-10 h-10 px-3 bg-black text-white flex items-center justify-center font-bold border-2 border-black hover:bg-white hover:text-black transition-colors rounded-none"
            >
              {userBadge}
            </button>
          ) : (
            <Link className="w-10 h-10 bg-black text-white flex items-center justify-center font-bold border-2 border-black hover:bg-white hover:text-black transition-colors rounded-none" to="/login">
              <User size={18} />
            </Link>
          )}
        </div>
      </div>
    </nav>
  );
}
