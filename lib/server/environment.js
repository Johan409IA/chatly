export function getServerEnvironment() {
  const required = (name) => {
    const value = process.env[name]?.trim();
    if (!value) {
      throw new Error(`Falta configurar la variable ${name}.`);
    }
    return value;
  };

  const appEnvironment = process.env.APP_ENV || "development";
  if (!["development", "test", "production"].includes(appEnvironment)) {
    throw new Error("APP_ENV debe ser development, test o production.");
  }

  const appDatabaseUrl =
    process.env.APP_DATABASE_URL ||
    (appEnvironment === "test" ? process.env.TEST_DATABASE_URL : "");
  if (!appDatabaseUrl) {
    throw new Error("Configura APP_DATABASE_URL con el rol de ejecución de la aplicación.");
  }

  return {
    appEnvironment,
    appDatabaseUrl,
    frontendUrl: (process.env.RENDER_EXTERNAL_URL || process.env.FRONTEND_URL || "http://localhost:3000")
      .trim()
      .replace(/\/+$/, ""),
    jwtLeewaySeconds: Number(process.env.JWT_LEEWAY_SECONDS || 30),
    supabaseJwksUrl: required("SUPABASE_JWKS_URL"),
    supabasePublishableKey: required("SUPABASE_PUBLISHABLE_KEY"),
    supabaseUrl: required("SUPABASE_URL").replace(/\/+$/, ""),
  };
}
