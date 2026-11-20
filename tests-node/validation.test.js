import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";
import test from "node:test";
import { ApiError } from "../lib/server/api-error.js";
import {
  parseBody,
  profileUpdateSchema,
  registrationSchema,
} from "../lib/shared/validation.js";

function validRegistration(overrides = {}) {
  const date = new Date();
  date.setUTCFullYear(date.getUTCFullYear() - 25);
  return {
    email: "  User@Example.com ",
    password: "Strong!Pass1",
    alias: "Test_user",
    display_name: "  Ana   Martínez ",
    birth_date: date.toISOString().slice(0, 10),
    gender: "femenino",
    interest_ids: [],
    ...overrides,
  };
}

test("registration normalizes email, alias, and display name", () => {
  const parsed = registrationSchema.parse(validRegistration());
  assert.equal(parsed.email, "user@example.com");
  assert.equal(parsed.alias, "test_user");
  assert.equal(parsed.display_name, "Ana Martínez");
});

test("registration rejects an underage user", () => {
  const date = new Date();
  date.setUTCFullYear(date.getUTCFullYear() - 17);
  assert.throws(
    () => registrationSchema.parse(validRegistration({ birth_date: date.toISOString().slice(0, 10) })),
  );
});

test("invalid password keeps the weak_password API code", () => {
  assert.throws(
    () => parseBody(registrationSchema, validRegistration({ password: "weak" })),
    (error) => error instanceof ApiError && error.code === "weak_password",
  );
});

test("more than ten interests uses the contract error code", () => {
  const interest_ids = Array.from({ length: 11 }, () => randomUUID());
  assert.throws(
    () => parseBody(registrationSchema, validRegistration({ interest_ids })),
    (error) => error instanceof ApiError && error.code === "interest_limit_exceeded",
  );
});

test("an empty profile patch is rejected", () => {
  assert.equal(profileUpdateSchema.safeParse({}).success, false);
});
