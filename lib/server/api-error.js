export class ApiError extends Error {
  constructor(code, message, status = 400, details = undefined) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

export function apiErrorResponse(error) {
  if (error instanceof ApiError) {
    const body = { code: error.code, message: error.message };
    if (error.details && Object.keys(error.details).length > 0) {
      body.details = error.details;
    }
    return Response.json(
      { error: body },
      { status: error.status },
    );
  }
  console.error("Error no controlado en API", error?.name || "Error");
  return Response.json(
    {
      error: {
        code: "internal_error",
        message: "Ocurrió un error inesperado. Inténtalo de nuevo.",
      },
    },
    { status: 500 },
  );
}
