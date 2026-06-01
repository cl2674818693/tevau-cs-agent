import prettier from "eslint-config-prettier";
import react from "eslint-plugin-react";
import reactHooks from "eslint-plugin-react-hooks";
import tseslint from "typescript-eslint";

export default [
  ...tseslint.configs.recommended,
  {
    files: ["src/**/*.{ts,tsx}", "tests/**/*.{ts,tsx}"],
    plugins: { react, "react-hooks": reactHooks },
    rules: {
      "@typescript-eslint/no-explicit-any": "error",
      "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_" }],
      "react/jsx-uses-react": "off",
      "react/react-in-jsx-scope": "off",
      "react-hooks/rules-of-hooks": "error",
      "react-hooks/exhaustive-deps": "warn",
      "max-lines": ["warn", { max: 400, skipBlankLines: true, skipComments: true }],
      "max-lines-per-function": ["warn", { max: 150, skipBlankLines: true, skipComments: true }],
      complexity: ["warn", 15],
    },
    settings: { react: { version: "detect" } },
  },
  {
    files: ["src/components/ui/*.tsx"],
    rules: {
      "max-lines-per-function": "off",
      "max-lines": "off",
    },
  },
  {
    // Admin/staff route files combine DataTable + Sheet forms + data loading in one page component.
    // These are legitimately larger than a generic component; limits are raised accordingly.
    files: [
      "src/routes/admin/*.tsx",
      "src/routes/staff/*.tsx",
      "src/api/staff.ts",
    ],
    rules: {
      "max-lines": ["warn", { max: 700, skipBlankLines: true, skipComments: true }],
      "max-lines-per-function": ["warn", { max: 250, skipBlankLines: true, skipComments: true }],
      complexity: ["warn", 20],
    },
  },
  prettier,
  { ignores: ["dist", "node_modules", "coverage", "*.config.js", "*.config.ts"] },
];
