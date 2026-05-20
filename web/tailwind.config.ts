import type { Config } from "tailwindcss";
import animate from "tailwindcss-animate";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          DEFAULT: "#C8F833",
          dark: "#042834",
          tab: "#D9F490",
          press: "#305500",
          disabled: "#F0F1F3",
        },
        ink: {
          primary: "#121212",
          secondary: "#8C939C",
          placeholder: "#4B5563",
          subtle: "#6C737C",
          footnote: "#AEB3BA",
        },
        surface: {
          page: "#FEFEFE",
          card: "#FFFFFF",
          subtle: "#F6F6F6",
          container: "#F0F1F3",
          disabled: "#EFEFEF",
          hover: "#F6F6F6",
        },
        line: "#E0E3E7",
        status: {
          error: "#ED3241",
          success: "#51B832",
          warning: "#F59E0B",
        },
        background: "#FEFEFE",
        foreground: "#121212",
        primary: { DEFAULT: "#C8F833", foreground: "#121212" },
        secondary: { DEFAULT: "#042834", foreground: "#FFFFFF" },
        muted: { DEFAULT: "#F0F1F3", foreground: "#8C939C" },
        accent: { DEFAULT: "#D9F490", foreground: "#121212" },
        destructive: { DEFAULT: "#ED3241", foreground: "#FFFFFF" },
        border: "#E0E3E7",
        input: "#E0E3E7",
        ring: "#C8F833",
        card: { DEFAULT: "#FFFFFF", foreground: "#121212" },
      },
      fontFamily: {
        sans: ['"Source Sans 3"', "-apple-system", "PingFang SC", "sans-serif"],
      },
      fontSize: {
        h0: ["32px", { lineHeight: "36px", fontWeight: "800" }],
        h1: ["32px", { lineHeight: "36px", fontWeight: "800" }],
        h2: ["28px", { lineHeight: "32px", fontWeight: "700" }],
        sh0: ["24px", { lineHeight: "28px", fontWeight: "700" }],
        sh1: ["18px", { lineHeight: "28px", fontWeight: "700" }],
        sh2: ["16px", { lineHeight: "20px", fontWeight: "700" }],
        sh3: ["16px", { lineHeight: "20px", fontWeight: "600" }],
        body0: ["14px", { lineHeight: "18px", fontWeight: "700" }],
        body1: ["14px", { lineHeight: "18px", fontWeight: "600" }],
        body2: ["14px", { lineHeight: "18px", fontWeight: "400" }],
        body3: ["12px", { lineHeight: "16px", fontWeight: "600" }],
        body4: ["12px", { lineHeight: "16px", fontWeight: "500" }],
        body5: ["12px", { lineHeight: "16px", fontWeight: "400" }],
        footnote: ["10px", { lineHeight: "12px", fontWeight: "400" }],
      },
      borderRadius: {
        sm: "8px",
        DEFAULT: "12px",
        lg: "16px",
      },
      spacing: {
        page: "16px",
        "block-sm": "8px",
        "block-lg": "16px",
        "input-x": "12px",
        "input-y": "16px",
      },
      transitionDuration: {
        250: "250ms",
        300: "300ms",
        400: "400ms",
      },
      transitionTimingFunction: {
        "out-cubic": "cubic-bezier(0.215, 0.61, 0.355, 1)",
        "in-cubic": "cubic-bezier(0.55, 0.055, 0.675, 0.19)",
        "out-back": "cubic-bezier(0.34, 1.56, 0.64, 1)",
      },
      boxShadow: {
        focus: "0 0 8px 0 rgba(200, 248, 51, 0.15)",
      },
      backgroundImage: {
        "page-gradient": "linear-gradient(180deg, #F6F6F6 0%, #FEFEFE 100%)",
      },
    },
  },
  plugins: [animate],
} satisfies Config;
