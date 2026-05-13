import React from "react";
import { motion, AnimatePresence } from "framer-motion";
import { twMerge } from "tailwind-merge";
import { FileWarning, Bug, Lock, Eye, Activity, Shield } from "lucide-react";

export const Circle = ({ className, children, idx, ...rest }: any) => {
  return (
    <motion.div
      {...rest}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ delay: idx * 0.1, duration: 0.2 }}
      className={twMerge(
        "absolute inset-0 left-1/2 top-1/2 h-10 w-10 -translate-x-1/2 -translate-y-1/2 transform rounded-full border border-slate-900",
        className
      )}
    />
  );
};

export const Radar = ({ className, children }: { className?: string, children?: React.ReactNode }) => {
  const circles = new Array(8).fill(1);
  return (
    <div
      className={twMerge(
        "relative flex h-[600px] w-full items-center justify-center rounded-full overflow-hidden",
        className
      )}
    >
      <style>{`
        @keyframes radar-spin {
          from { transform: rotate(0deg); }
          to   { transform: rotate(360deg); }
        }
        .animate-radar-spin {
          animation: radar-spin 8s linear infinite;
        }
      `}</style>
      
      {/* Background circles */}
      {circles.map((_, idx) => (
        <Circle
          style={{
            height: `${(idx + 1) * 6}rem`,
            width: `${(idx + 1) * 6}rem`,
            border: `1px solid rgba(139, 92, 246, ${Math.max(0.02, 0.2 - idx * 0.02)})`,
          }}
          key={`circle-${idx}`}
          idx={idx}
        />
      ))}

      {/* Radial sweep - more subtle and thin */}
      <div
        style={{ transformOrigin: "right center" }}
        className="animate-radar-spin absolute right-1/2 top-1/2 z-40 flex h-[150px] w-[50%] items-end justify-center overflow-hidden bg-transparent"
      >
        <div className="relative z-40 h-[0.5px] w-full bg-gradient-to-r from-transparent via-purple-500/30 to-transparent" />
      </div>

      {children}
    </div>
  );
};

export const IconContainer = ({
  icon: Icon,
  text,
  delay,
  position = { top: "50%", left: "50%" }
}: {
  icon: any;
  text?: string;
  delay?: number;
  position?: { top: string, left: string };
}) => {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0, x: "-50%", y: "-50%" }}
      animate={{ opacity: 1, scale: 1, x: "-50%", y: "-50%" }}
      transition={{ 
        type: "spring",
        stiffness: 260,
        damping: 20,
        delay: 0.1
      }}
      style={{
        position: "absolute",
        top: position.top,
        left: position.left,
      }}
      className="z-50 flex flex-col items-center justify-center space-y-2"
    >
      <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-purple-500/40 bg-black shadow-[0_0_20px_rgba(139,92,246,0.4)]">
        <Icon className="text-purple-400" size={20} />
      </div>
      <div className="rounded-md px-2 py-1 bg-black/90 border border-purple-500/20 backdrop-blur-sm">
        <div className="text-center text-[10px] font-bold text-purple-400 font-mono tracking-tighter uppercase">
          {text}
        </div>
      </div>
    </motion.div>
  );
};

// Helper function to get icon from string
export const getDiscoveryIcon = (type: string) => {
  switch (type) {
    case 'file-warning': return FileWarning;
    case 'bug': return Bug;
    case 'lock': return Lock;
    case 'eye': return Eye;
    case 'activity': return Activity;
    case 'shield': return Shield;
    default: return Activity;
  }
};
