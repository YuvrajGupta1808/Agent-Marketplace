import React, { useState } from "react";
import { Link } from "react-router-dom";
import { Bot } from "lucide-react";
import { useAppState } from "../lib/app-state";

export function Register() {
  const { registerNewUser } = useAppState();
  const [isRegistered, setIsRegistered] = useState(false);
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [createdUserId, setCreatedUserId] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError(null);
    try {
      const user = await registerNewUser(displayName, email);
      setIsRegistered(true);
      setCreatedUserId(user.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="mx-auto max-w-xl pt-24 px-8 w-full flex items-center justify-center">
      <div className="border-2 border-black bg-white p-10 sm:p-12 shadow-[8px_8px_0px_0px_rgba(0,0,0,1)] w-full">
        <div className="mb-10 flex flex-col items-center text-center">
          <div className="mb-6 flex h-16 w-16 items-center justify-center bg-black text-white">
            <Bot size={32} />
          </div>
          <h1 className="text-3xl font-black uppercase tracking-tighter text-black">Join Agent.Flow</h1>
          <p className="mt-3 text-[10px] font-bold uppercase tracking-widest text-gray-400">
            Create a backend user record. Buyer wallets are created when you build a buyer agent.
          </p>
        </div>

        {!isRegistered ? (
          <form onSubmit={handleRegister} className="space-y-6">
            <div>
              <label className="mb-2 block text-[10px] font-black uppercase tracking-[0.2em] text-gray-500">Username</label>
              <input
                required
                type="text"
                value={displayName}
                onChange={(event) => setDisplayName(event.target.value)}
                placeholder="AGENT_MASTER_99"
                className="w-full bg-white border-2 border-black px-4 py-3 text-xs font-bold uppercase tracking-widest outline-none transition-all focus:shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]"
              />
            </div>
            <div>
              <label className="mb-2 block text-[10px] font-black uppercase tracking-[0.2em] text-gray-500">Email</label>
              <input
                required
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="HELLO@EXAMPLE.COM"
                className="w-full bg-white border-2 border-black px-4 py-3 text-xs font-bold uppercase tracking-widest outline-none transition-all focus:shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]"
              />
            </div>
            {error ? (
              <div className="border-2 border-red-500 bg-red-50 p-4 text-[10px] font-bold uppercase tracking-widest text-red-700">
                {error}
              </div>
            ) : null}
            <button
              type="submit"
              disabled={isSubmitting}
              className="mt-8 w-full bg-black py-4 text-[10px] font-black uppercase tracking-[0.2em] text-white transition-colors hover:bg-gray-800"
            >
              {isSubmitting ? "Creating Account..." : "Create Account"}
            </button>
          </form>
        ) : (
          <div className="space-y-8 text-center">
            <div className="border-2 border-green-500 bg-green-50 p-4">
              <h3 className="text-xs font-black uppercase tracking-[0.1em] text-green-900">Registration Successful</h3>
              <p className="mt-1 text-[10px] font-bold uppercase tracking-widest text-green-700">Your backend user is ready.</p>
            </div>
            <div className="w-full border-2 border-black bg-gray-50 p-4 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] text-left">
              <p className="text-[10px] font-black uppercase tracking-[0.15em] text-gray-500">User ID</p>
              <code className="mt-2 block text-xs md:text-sm font-mono font-bold text-black break-all">{createdUserId}</code>
            </div>
            <div className="w-full border-2 border-black bg-white p-4 text-left">
              <p className="text-[10px] font-black uppercase tracking-[0.15em] text-gray-500">Next Step</p>
              <p className="mt-2 text-xs font-bold uppercase tracking-widest text-black">
                Build a buyer agent to provision its wallet and connect seller agents.
              </p>
            </div>
            <div className="pt-2">
              <Link
                to="/builder"
                className="inline-flex items-center justify-center w-full bg-black py-4 text-[10px] font-black uppercase tracking-[0.2em] text-white transition-colors hover:bg-gray-800"
              >
                Go to Builder
              </Link>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
