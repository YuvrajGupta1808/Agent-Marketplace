import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Key } from "lucide-react";
import { useAppState } from "../lib/app-state";
import { listUsers, UserRecord } from "../lib/api";

export function Login() {
  const { loginAsUser } = useAppState();
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [users, setUsers] = useState<UserRecord[]>([]);
  const [selectedUserId, setSelectedUserId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isLoadingUsers, setIsLoadingUsers] = useState(false);
  const navigate = useNavigate();

  React.useEffect(() => {
    let mounted = true;
    const loadUsers = async () => {
      setIsLoadingUsers(true);
      try {
        const payload = await listUsers();
        if (!mounted) return;
        setUsers(payload);
        setSelectedUserId(payload[0]?.id ?? "");
      } catch (err) {
        if (!mounted) return;
        setError(err instanceof Error ? err.message : "Failed to load users.");
      } finally {
        if (mounted) setIsLoadingUsers(false);
      }
    };
    void loadUsers();
    return () => {
      mounted = false;
    };
  }, []);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    const user = users.find((entry) => entry.id === selectedUserId);
    if (!user) {
      setError("Select a registered user first.");
      return;
    }
    setIsAuthenticated(true);
    await loginAsUser(user);
    setTimeout(() => navigate("/dashboard"), 600);
  };

  return (
    <div className="mx-auto max-w-xl pt-24 px-8 w-full flex items-center justify-center flex-1">
      <div className="border-2 border-black bg-white p-10 sm:p-12 shadow-[8px_8px_0px_0px_rgba(0,0,0,1)] w-full">
        <div className="mb-10 flex flex-col items-center text-center">
          <div className="mb-6 flex h-16 w-16 items-center justify-center bg-black text-white">
            <Key size={32} />
          </div>
          <h1 className="text-3xl font-black uppercase tracking-tighter text-black">Auth.Node</h1>
          <p className="mt-3 text-[10px] font-bold uppercase tracking-widest text-gray-400">
            Open a local session from registered backend users.
          </p>
        </div>

        {!isAuthenticated ? (
          <form onSubmit={handleLogin} className="space-y-6">
            <div>
              <label className="mb-2 block text-[10px] font-black uppercase tracking-[0.2em] text-gray-500">Registered User</label>
              <select
                required
                value={selectedUserId}
                onChange={(event) => setSelectedUserId(event.target.value)}
                className="w-full bg-white border-2 border-black px-4 py-3 text-xs font-bold uppercase tracking-widest outline-none transition-all focus:shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]"
              >
                <option value="" disabled>
                  {isLoadingUsers ? "Loading users..." : "Select user"}
                </option>
                {users.map((user) => (
                  <option key={user.id} value={user.id}>
                    {user.display_name} ({user.id.slice(0, 8)})
                  </option>
                ))}
              </select>
            </div>
            {error ? (
              <div className="border-2 border-red-500 bg-red-50 p-4 text-[10px] font-bold uppercase tracking-widest text-red-700">
                {error}
              </div>
            ) : null}
            <button
              type="submit"
              disabled={!selectedUserId || isLoadingUsers}
              className="mt-8 w-full bg-black py-5 text-[10px] font-black uppercase tracking-[0.2em] text-white transition-colors hover:bg-gray-800"
            >
              Initiate Session
            </button>
          </form>
        ) : (
          <div className="space-y-8 text-center pt-4">
            <div className="border-2 border-black bg-black text-white p-6 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]">
              <h3 className="text-xs font-black uppercase tracking-[0.1em]">Authentication Valid</h3>
              <p className="mt-2 text-[10px] font-bold uppercase tracking-widest text-gray-400">Session restored. Rerouting to command center...</p>
            </div>
            
            <div className="w-full bg-gray-100 h-1 mt-6 overflow-hidden relative border-y border-black">
              <div className="absolute left-0 top-0 bottom-0 bg-black animate-[ping_1.5s_cubic-bezier(0,0,0.2,1)_infinite]"></div>
              <div className="absolute left-0 top-0 bottom-0 bg-black w-full origin-left animate-pulse"></div>
            </div>
          </div>
        )}

        <div className="mt-10 text-center border-t-2 border-dashed border-gray-200 pt-8">
          <p className="text-[10px] font-bold uppercase tracking-[0.15em] text-gray-500">
            NO IDENTITY DEPLOYED?{" "}
            <Link to="/register" className="text-black underline underline-offset-4 hover:bg-black hover:text-white transition-colors px-1">
              REGISTER NODE
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
