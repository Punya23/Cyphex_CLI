import { loadFont as loadMono } from "@remotion/google-fonts/JetBrainsMono";
import { loadFont as loadDisplay } from "@remotion/google-fonts/SpaceGrotesk";

const mono = loadMono("normal", { weights: ["400", "500", "700"], subsets: ["latin"] });
const display = loadDisplay("normal", { weights: ["500", "700"], subsets: ["latin"] });

export const FONT_MONO = mono.fontFamily;
export const FONT_DISPLAY = display.fontFamily;

// Palette lifted from the CYPHEX banner / mascot: coral-red on near-black.
export const C = {
  bg: "#070708",
  panel: "#0e0f12",
  panelHi: "#14161b",
  line: "#23262d",
  text: "#ECEDEF",
  dim: "#8A8F98",
  faint: "#4a4e57",
  coral: "#F0524D",
  red: "#FF3B3B",
  deep: "#D63447",
  purple: "#6D28D9",
  violet: "#A78BFA",
  green: "#34D399",
  amber: "#FBBF24",
} as const;

export const CLAMP = {
  extrapolateLeft: "clamp",
  extrapolateRight: "clamp",
} as const;
