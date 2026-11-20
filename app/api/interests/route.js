import { NextResponse } from "next/server";
import { ApiError, apiErrorResponse } from "../../../lib/server/api-error.js";
import { getPool } from "../../../lib/server/database.js";

export async function GET() {
  try {
    const result = await getPool().query("SELECT * FROM app.catalogo_intereses()");
    const categories = new Map();
    for (const row of result.rows) {
      const categoryId = String(row.categoria_id || "");
      const interestId = String(row.interes_id || "");
      const categoryName = row.categoria_nombre;
      const interestName = row.interes_nombre;
      if (!categoryId || !interestId || !categoryName || !interestName) {
        throw new ApiError("internal_error", "El catálogo de intereses no tiene un formato válido.", 500);
      }
      if (!categories.has(categoryId)) {
        categories.set(categoryId, { id: categoryId, name: categoryName, interests: [] });
      }
      categories.get(categoryId).interests.push({ id: interestId, name: interestName });
    }
    return NextResponse.json([...categories.values()], {
      headers: { "Cache-Control": "public, max-age=3600" },
    });
  } catch (error) {
    return apiErrorResponse(error);
  }
}
