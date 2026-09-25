import { defineConfig } from "vitest/config";
import path from "path";
import { TEST_DB_URL } from "./tests/testDb";

export default defineConfig({
  test: {
    environment: "node",
    globalSetup: ["./tests/globalSetup.ts"],
    testTimeout: 15000,
    env: {
      DATABASE_URL: TEST_DB_URL,
      DIRECT_URL: TEST_DB_URL,
    },
    // Testes de banco compartilham o mesmo banco Postgres de teste — evita
    // corrida entre arquivos de teste rodando em paralelo.
    fileParallelism: false,
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
});
