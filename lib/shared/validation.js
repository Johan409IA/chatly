import { z } from "zod";
import { ApiError } from "../server/api-error.js";

const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const aliasPattern = /^[a-z][a-z0-9_]{2,19}$/;

export const emailSchema = z
  .string()
  .trim()
  .toLowerCase()
  .regex(emailPattern, "Escribe un correo electrónico válido.");

export const loginSchema = z.object({
  email: emailSchema,
  password: z.string().min(1, "Escribe tu contraseña."),
});

export const registrationSchema = z.object({
  email: emailSchema,
  password: z
    .string()
    .min(8, "La contraseña debe tener al menos 8 caracteres.")
    .refine((value) => /[A-Z]/.test(value), "Incluye una mayúscula.")
    .refine((value) => /[a-z]/.test(value), "Incluye una minúscula.")
    .refine((value) => /[^a-zA-Z0-9]/.test(value), "Incluye un carácter especial."),
  alias: z
    .string()
    .trim()
    .toLowerCase()
    .regex(aliasPattern, "El alias debe tener 3–20 caracteres y comenzar por una letra."),
  display_name: z
    .string()
    .trim()
    .transform((value) => value.replace(/\s+/g, " "))
    .refine((value) => value.length >= 2 && value.length <= 60, {
      message: "El nombre debe tener entre 2 y 60 caracteres.",
    }),
  birth_date: z
    .string()
    .regex(/^\d{4}-\d{2}-\d{2}$/, "Indica una fecha válida.")
    .refine((value) => !Number.isNaN(Date.parse(`${value}T00:00:00Z`)), "Indica una fecha válida.")
    .refine((value) => {
      const date = new Date(`${value}T00:00:00Z`);
      return date.toISOString().slice(0, 10) === value;
    }, "Indica una fecha válida.")
    .refine((value) => {
      const birthday = new Date(`${value}T00:00:00Z`);
      const today = new Date();
      let age = today.getUTCFullYear() - birthday.getUTCFullYear();
      if (
        today.getUTCMonth() < birthday.getUTCMonth() ||
        (today.getUTCMonth() === birthday.getUTCMonth() &&
          today.getUTCDate() < birthday.getUTCDate())
      ) {
        age -= 1;
      }
      return age >= 18 && age <= 120;
    }, "Debes tener entre 18 y 120 años."),
  gender: z.enum(["femenino", "masculino"]),
  interest_ids: z.array(z.string().uuid()).default([]),
}).superRefine((value, context) => {
  if (value.interest_ids.length > 10) {
    context.addIssue({
      code: "custom",
      path: ["interest_ids"],
      message: "Puedes elegir hasta 10 intereses.",
    });
  }
  if (new Set(value.interest_ids).size !== value.interest_ids.length) {
    context.addIssue({
      code: "custom",
      path: ["interest_ids"],
      message: "No repitas intereses en la selección.",
    });
  }
});

export const profileUpdateSchema = z
  .object({
    display_name: z
      .string()
      .trim()
      .transform((value) => value.replace(/\s+/g, " "))
      .refine((value) => value.length >= 2 && value.length <= 60, {
        message: "El nombre debe tener entre 2 y 60 caracteres.",
      })
      .nullable()
      .optional(),
    alias: z
      .string()
      .trim()
      .toLowerCase()
      .regex(aliasPattern, "El alias debe tener 3–20 caracteres y comenzar por una letra.")
      .nullable()
      .optional(),
    birth_date: registrationSchema.shape.birth_date.nullable().optional(),
    gender: z.enum(["femenino", "masculino"]).nullable().optional(),
    is_public: z.boolean().nullable().optional(),
  })
  .superRefine((value, context) => {
    if (Object.values(value).every((field) => field === undefined || field === null)) {
      context.addIssue({
        code: "custom",
        message: "Indica al menos un campo para actualizar.",
      });
    }
  });

export const interestsUpdateSchema = z
  .object({
    interest_ids: z.array(z.string().uuid()),
  })
  .superRefine((value, context) => {
    if (value.interest_ids.length > 10) {
      context.addIssue({
        code: "custom",
        path: ["interest_ids"],
        message: "Puedes elegir hasta 10 intereses.",
      });
    }
    if (new Set(value.interest_ids).size !== value.interest_ids.length) {
      context.addIssue({
        code: "custom",
        path: ["interest_ids"],
        message: "No repitas intereses en la selección.",
      });
    }
  });

export function parseBody(schema, value) {
  const parsed = schema.safeParse(value);
  if (parsed.success) return parsed.data;
  const fields = parsed.error.issues.map((issue) => ({
    field: issue.path.length ? issue.path.join(".") : null,
    message: issue.message,
  }));
  const details = { fields };
  if (fields.length === 1 && fields[0].field) details.field = fields[0].field;
  if (fields.some((field) => field.field === "interest_ids" && field.message.includes("hasta 10"))) {
    throw new ApiError(
      "interest_limit_exceeded",
      "Puedes elegir hasta 10 intereses.",
      422,
      details,
    );
  }
  if (fields.some((field) => field.field === "password")) {
    throw new ApiError(
      "weak_password",
      "La contraseña necesita 8 caracteres, una mayúscula, una minúscula y un símbolo.",
      422,
      details,
    );
  }
  throw new ApiError("validation_error", "Revisa los datos enviados.", 422, details);
}
