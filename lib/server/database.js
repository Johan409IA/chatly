import pg from "pg";
import { getServerEnvironment } from "./environment.js";

const { Pool } = pg;
let pool;

export function getPool() {
  if (!pool) {
    const { appDatabaseUrl } = getServerEnvironment();
    pool = new Pool({
      connectionString: appDatabaseUrl.replace(
        /^postgresql\+psycopg:\/\//,
        "postgresql://",
      ),
      max: Number(process.env.DB_POOL_SIZE || 5),
      idleTimeoutMillis: Number(process.env.DB_POOL_RECYCLE || 1800000),
      connectionTimeoutMillis: Number(process.env.DB_POOL_TIMEOUT || 30000),
    });
  }
  return pool;
}

export async function withActorTransaction(actorId, callback) {
  if (typeof actorId !== "string" || !/^[0-9a-f-]{36}$/i.test(actorId)) {
    throw new TypeError("El identificador del actor no es un UUID válido.");
  }

  const client = await getPool().connect();
  try {
    await client.query("BEGIN");
    await client.query("SELECT set_config('app.current_user_id', $1, true)", [actorId]);
    const result = await callback(client);
    await client.query("COMMIT");
    return result;
  } catch (error) {
    await client.query("ROLLBACK");
    throw error;
  } finally {
    client.release();
  }
}
