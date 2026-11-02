import type { CapacitorConfig } from "@capacitor/cli";

const config: CapacitorConfig = {
  appId: "sg.edu.e014.firefightertracking",
  appName: "E014 Firefighter Tracking",
  webDir: "dist",
  server: {
    androidScheme: "https",
    allowNavigation: ["*.trycloudflare.com"],
    cleartext: true,
  },
};

export default config;
