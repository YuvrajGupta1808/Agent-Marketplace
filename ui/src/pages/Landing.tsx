import { Link } from "react-router-dom";
import { ArrowRight, ChevronRight } from "lucide-react";

export function Landing() {
  return (
    <div className="relative flex min-h-0 w-full flex-1 flex-col overflow-hidden bg-white">
      <div className="absolute inset-0 z-0 opacity-[0.03] pointer-events-none" style={{ backgroundImage: 'radial-gradient(#000 2px, transparent 2px)', backgroundSize: '32px 32px' }}></div>
      <div className="absolute left-[-20%] top-20 -z-10 h-[40%] w-[60%] rounded-full bg-gray-100 opacity-50 blur-3xl"></div>

      <main className="relative z-10 flex min-h-0 flex-1 flex-col items-center justify-center gap-3 px-4 py-2 text-center sm:gap-4 sm:px-8 sm:py-4">
        <div className="mb-0 inline-flex border-2 border-black bg-black p-3 text-white shadow-[6px_6px_0px_0px_rgba(0,0,0,1)] transition-transform hover:-translate-y-1 sm:border-4 sm:p-3.5">
          <ChevronRight className="h-6 w-6 sm:h-7 sm:w-7" strokeWidth={3} />
        </div>

        <h1 className="max-w-4xl text-2xl font-black uppercase leading-[0.95] tracking-tighter text-black sm:max-w-5xl sm:text-3xl md:text-4xl lg:text-5xl">
          Autonomous Agent Protocol
        </h1>

        <p className="max-w-xl text-[10px] font-bold uppercase leading-snug tracking-widest text-gray-500 sm:max-w-2xl sm:text-xs md:text-sm">
          Deploy, trade, and govern AI worker nodes. Agent.Flow is the definitive decentralized marketplace for
          intelligent automation and smart labor.
        </p>

        <div className="mt-1 flex w-full max-w-md flex-col justify-center gap-3 sm:mt-2 sm:flex-row sm:gap-4">
          <Link
            to="/marketplace"
            className="flex flex-1 items-center justify-center gap-2 border-2 border-black bg-black py-3.5 pl-4 pr-5 text-[10px] font-black uppercase tracking-[0.2em] text-white transition-all hover:-translate-y-0.5 hover:shadow-[6px_6px_0px_0px_rgba(0,0,0,1)] sm:py-4 sm:pl-5 sm:pr-6 sm:text-xs"
          >
            Explore Market <ArrowRight className="h-3.5 w-3.5 sm:h-4 sm:w-4" strokeWidth={3} />
          </Link>
          <Link
            to="/login"
            className="flex flex-1 items-center justify-center gap-2 border-2 border-black bg-white py-3.5 px-4 text-[10px] font-black uppercase tracking-[0.2em] text-black shadow-[3px_3px_0px_0px_rgba(0,0,0,1)] transition-all hover:-translate-y-0.5 hover:shadow-[6px_6px_0px_0px_rgba(0,0,0,1)] sm:py-4 sm:px-5 sm:text-xs"
          >
            Authenticate Node
          </Link>
        </div>
      </main>

      <div className="relative z-10 flex shrink-0 justify-between border-t-2 border-black bg-white p-3 text-[9px] font-black uppercase tracking-widest sm:p-3.5 sm:text-[10px]">
        <div>SYS: ONLINE</div>
        <div className="hidden sm:block">Total Value Locked: Ξ4,291.04</div>
        <div>V 1.0.0</div>
      </div>
    </div>
  );
}
