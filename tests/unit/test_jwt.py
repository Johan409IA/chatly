"""Pruebas de verificación de JWT de Supabase (sin red ni credenciales)."""

import json
import time
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from jwt.algorithms import ECAlgorithm

from Chatly.backend.core.jwt import Actor, JWTVerifier, allowed_audiences

ISSUER = "https://ref123.supabase.co/auth/v1"
AUDIENCES = ["authenticated", "ref123"]


def _make_verifier() -> tuple[JWTVerifier, ec.EllipticCurvePrivateKey]:
    private_key = ec.generate_private_key(ec.SECP256R1())
    jwk_dict = json.loads(ECAlgorithm.to_jwk(private_key.public_key()))
    signing_key = jwt.PyJWK.from_dict(jwk_dict, algorithm="ES256")

    class _FixedKeyClient:
        def get_signing_key_from_jwt(self, token: str):
            return signing_key

    verifier = JWTVerifier(
        jwks_url="https://no-se-usa/.well-known/jwks.json",
        issuer=ISSUER,
        audiences=AUDIENCES,
        jwks_client=_FixedKeyClient(),  # type: ignore[arg-type]
    )
    return verifier, private_key


def _make_token(private_key, claims: dict) -> str:
    return jwt.encode(claims, private_key, algorithm="ES256")


def _base_claims(**overrides) -> dict:
    now = int(time.time())
    claims = {
        "sub": str(uuid4()),
        "aud": "authenticated",
        "iss": ISSUER,
        "iat": now,
        "exp": now + 600,
        "session_id": str(uuid4()),
        "email": "johan@example.com",
    }
    claims.update(overrides)
    return claims


def test_token_valido_devuelve_el_actor() -> None:
    verifier, private_key = _make_verifier()
    claims = _base_claims()
    token = _make_token(private_key, claims)

    actor = verifier.verify(token)

    assert isinstance(actor, Actor)
    assert str(actor.id) == claims["sub"]
    assert actor.email == "johan@example.com"


def test_acepta_audience_del_ref_del_proyecto() -> None:
    verifier, private_key = _make_verifier()
    token = _make_token(private_key, _base_claims(aud="ref123"))

    assert isinstance(verifier.verify(token), Actor)


def test_rechaza_token_expirado() -> None:
    verifier, private_key = _make_verifier()
    token = _make_token(private_key, _base_claims(exp=int(time.time()) - 60))

    with pytest.raises(jwt.ExpiredSignatureError):
        verifier.verify(token)


def test_rechaza_issuer_ajeno() -> None:
    verifier, private_key = _make_verifier()
    token = _make_token(private_key, _base_claims(iss="https://otro.supabase.co/auth/v1"))

    with pytest.raises(jwt.InvalidIssuerError):
        verifier.verify(token)


def test_rechaza_audience_desconocida() -> None:
    verifier, private_key = _make_verifier()
    token = _make_token(private_key, _base_claims(aud="otra-app"))

    with pytest.raises(jwt.InvalidAudienceError):
        verifier.verify(token)


def test_rechaza_token_sin_sub() -> None:
    verifier, private_key = _make_verifier()
    claims = _base_claims()
    del claims["sub"]
    token = _make_token(private_key, claims)

    with pytest.raises(jwt.MissingRequiredClaimError):
        verifier.verify(token)


def test_rechaza_sub_que_no_es_uuid() -> None:
    verifier, private_key = _make_verifier()
    token = _make_token(private_key, _base_claims(sub="no-es-un-uuid"))

    with pytest.raises(ValueError):
        verifier.verify(token)


def test_rechaza_firma_de_otra_clave() -> None:
    verifier, _ = _make_verifier()
    otra_clave = ec.generate_private_key(ec.SECP256R1())
    token = _make_token(otra_clave, _base_claims())

    with pytest.raises(jwt.InvalidSignatureError):
        verifier.verify(token)


def test_rechaza_alg_no_permitido() -> None:
    verifier, _ = _make_verifier()
    token = jwt.encode(_base_claims(), "secreto-simetrico", algorithm="HS256")

    with pytest.raises(jwt.InvalidAlgorithmError):
        verifier.verify(token)


def test_resultado_se_guarda_en_cache_por_token() -> None:
    verifier, private_key = _make_verifier()
    token = _make_token(private_key, _base_claims())

    primer = verifier.verify(token)
    llamadas = 0
    decode_original = verifier._decode

    def decode_contado(t: str) -> dict:
        nonlocal llamadas
        llamadas += 1
        return decode_original(t)

    verifier._decode = decode_contado  # type: ignore[method-assign]
    segundo = verifier.verify(token)

    assert primer == segundo
    assert llamadas == 0


def test_audiences_permitidas_derivan_de_la_url() -> None:
    assert allowed_audiences("https://ref123.supabase.co") == [
        "authenticated",
        "ref123",
    ]
